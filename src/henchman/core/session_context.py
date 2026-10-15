"""Tier 2 helpers for inspecting and mutating session context."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from henchman.providers.base import Message
from henchman.utils.tokens import TokenCounter

from .session_data import Session
from .session_export import export_as_markdown
from .session_helpers import _now_iso
from .session_manager import SessionManager
from .session_memory import SessionMemoryService
from .session_models import SessionMessage, TurnSummaryRecord


@dataclass(slots=True)
class ToolUsageSummary:
    """Structured summary of tool use recorded in a session."""

    total_calls: int
    total_results: int
    calls_by_name: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        """Serialize the tool-usage summary."""

        return {
            "total_calls": self.total_calls,
            "total_results": self.total_results,
            "calls_by_name": dict(self.calls_by_name),
        }


@dataclass(slots=True)
class SessionContextSnapshot:
    """High-level current-context snapshot for one session."""

    session_id: str
    tag: str | None
    message_count: int
    turn_count: int
    turn_summary_count: int
    plan_mode: bool
    token_estimate: int
    tool_usage: ToolUsageSummary
    memory_count: int
    last_updated: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize the context snapshot."""

        return {
            "session_id": self.session_id,
            "tag": self.tag,
            "message_count": self.message_count,
            "turn_count": self.turn_count,
            "turn_summary_count": self.turn_summary_count,
            "plan_mode": self.plan_mode,
            "token_estimate": self.token_estimate,
            "tool_usage": self.tool_usage.to_dict(),
            "memory_count": self.memory_count,
            "last_updated": self.last_updated,
        }


@dataclass(slots=True)
class SessionCompactionResult:
    """Result of compacting older turns in a session."""

    changed: bool
    removed_turns: int
    removed_messages: int
    preserved_turns: int

    def to_dict(self) -> dict[str, Any]:
        """Serialize the compaction result."""

        return {
            "changed": self.changed,
            "removed_turns": self.removed_turns,
            "removed_messages": self.removed_messages,
            "preserved_turns": self.preserved_turns,
        }


@dataclass(slots=True)
class SessionRewindResult:
    """Result of rewinding turns from a session."""

    removed_turns: int
    removed_messages: int
    remaining_turns: int

    def to_dict(self) -> dict[str, Any]:
        """Serialize the rewind result."""

        return {
            "removed_turns": self.removed_turns,
            "removed_messages": self.removed_messages,
            "remaining_turns": self.remaining_turns,
        }


def _flatten(turns: list[list[SessionMessage]]) -> list[SessionMessage]:
    """Flatten grouped turns into one message list."""

    return [message for turn in turns for message in turn]


def _split_prefix_and_turns(messages: list[SessionMessage]) -> tuple[list[SessionMessage], list[list[SessionMessage]]]:
    """Split one session into a non-user prefix and user-anchored turns."""

    prefix: list[SessionMessage] = []
    turns: list[list[SessionMessage]] = []
    current_turn: list[SessionMessage] = []
    seen_user = False

    for message in messages:
        if message.role == "user":
            seen_user = True
            if current_turn:
                turns.append(current_turn)
            current_turn = [message]
            continue

        if not seen_user:
            prefix.append(message)
            continue

        if current_turn:
            current_turn.append(message)
        else:
            prefix.append(message)

    if current_turn:
        turns.append(current_turn)

    return prefix, turns


def _message_to_provider_message(message: SessionMessage) -> Message:
    """Convert a persisted session message into a token-counting message."""

    from henchman.providers.base import ToolCall

    tool_calls = None
    if message.tool_calls:
        tool_calls = [
            ToolCall(
                id=tc.get("id", ""),
                name=tc.get("name", ""),
                arguments=tc.get("arguments", {}),
            )
            for tc in message.tool_calls
        ]

    return Message(
        role=message.role,
        content=message.content,
        tool_calls=tool_calls,
        tool_call_id=message.tool_call_id,
        reasoning_content=message.reasoning_content,
    )


def _turn_preview(turn: list[SessionMessage]) -> str:
    """Build a one-line summary preview for one turn."""

    user_content = next((message.content for message in turn if message.role == "user" and message.content), "")
    assistant_content = next(
        (
            message.content
            for message in turn
            if message.role == "assistant" and message.content and not message.tool_calls
        ),
        "",
    )
    tool_names = [
        str(tool_call.get("name"))
        for message in turn
        for tool_call in (message.tool_calls or [])
        if isinstance(tool_call, dict) and isinstance(tool_call.get("name"), str)
    ]

    parts = [user_content.strip()]
    if assistant_content:
        parts.append(assistant_content.strip())
    if tool_names:
        parts.append(f"tools={', '.join(tool_names)}")

    preview = " | ".join(part for part in parts if part)
    return preview[:200]


def _build_compaction_summary(dropped_turns: list[list[SessionMessage]], removed_messages: int) -> str:
    """Render a deterministic compaction summary for dropped turns."""

    lines = [f"Compacted {len(dropped_turns)} earlier turn(s) across {removed_messages} message(s)."]
    for index, turn in enumerate(dropped_turns, start=1):
        preview = _turn_preview(turn)
        if preview:
            lines.append(f"- Turn {index}: {preview}")
    return "\n".join(lines)


class SessionContextService:
    """Inspect and mutate the persisted context of one saved session."""

    def __init__(self, manager: SessionManager) -> None:
        """Initialize the service with a backing session manager."""

        self._manager = manager
        self._memory_service = SessionMemoryService()

    def resolve_active_session(self, project_root: Path) -> tuple[str, Session]:
        """Resolve the current project session, falling back to the latest saved session."""

        project_hash = self._manager.compute_project_hash(project_root)
        current_session_id = self._manager.get_project_current(project_hash)

        if current_session_id is not None:
            try:
                session = self._manager.load(current_session_id)
            except FileNotFoundError:
                self._manager.clear_project_current(project_hash)
            else:
                self._manager.set_current(session)
                return project_hash, session

        sessions = self._manager.list_sessions(project_hash=project_hash)
        if not sessions:
            msg = "No saved sessions for the current project."
            raise ValueError(msg)

        session = self._manager.load(sessions[0].id)
        self._manager.set_project_current(project_hash, session.id)
        self._manager.set_current(session)
        return project_hash, session

    def get_turn_count(self, session: Session) -> int:
        """Return the number of user-anchored turns in the session."""

        return len(_split_prefix_and_turns(session.messages)[1])

    def summarize_tool_use(self, session: Session) -> ToolUsageSummary:
        """Summarize tool calls and tool-result messages recorded in the session."""

        call_counts: Counter[str] = Counter()
        total_results = 0

        for message in session.messages:
            for tool_call in message.tool_calls or []:
                if isinstance(tool_call, dict) and isinstance(tool_call.get("name"), str):
                    call_counts[str(tool_call["name"])] += 1
            if message.role == "tool":
                total_results += 1

        return ToolUsageSummary(
            total_calls=sum(call_counts.values()),
            total_results=total_results,
            calls_by_name=dict(call_counts),
        )

    def estimate_tokens(self, session: Session) -> int:
        """Estimate token usage for the current persisted session."""

        messages = [_message_to_provider_message(message) for message in session.messages]
        return TokenCounter.count_messages(messages)

    def render_transcript(self, session: Session) -> str:
        """Render the current session transcript as Markdown."""

        return export_as_markdown(session, include_metadata=True)

    def build_snapshot(self, session: Session) -> SessionContextSnapshot:
        """Build a structured snapshot of session/context state."""

        return SessionContextSnapshot(
            session_id=session.id,
            tag=session.tag,
            message_count=len(session.messages),
            turn_count=self.get_turn_count(session),
            turn_summary_count=len(session.turn_summaries),
            plan_mode=session.plan_mode,
            token_estimate=self.estimate_tokens(session),
            tool_usage=self.summarize_tool_use(session),
            memory_count=len(self._memory_service.list_memories(session)),
            last_updated=session.last_updated,
        )

    def compact_session(self, session: Session, *, preserve_turns: int = 2) -> SessionCompactionResult:
        """Compact older session turns into a persisted summary record."""

        if preserve_turns < 0:
            msg = "preserve_turns must be non-negative"
            raise ValueError(msg)

        prefix, turns = _split_prefix_and_turns(session.messages)
        if len(turns) <= preserve_turns:
            return SessionCompactionResult(
                changed=False,
                removed_turns=0,
                removed_messages=0,
                preserved_turns=len(turns),
            )

        dropped_turns = turns[:-preserve_turns] if preserve_turns else turns
        kept_turns = turns[-preserve_turns:] if preserve_turns else []
        removed_messages = len(_flatten(dropped_turns))
        summary = _build_compaction_summary(dropped_turns, removed_messages)

        session.turn_summaries.append(
            TurnSummaryRecord(
                turn_number=len(session.turn_summaries) + 1,
                summary_text=summary,
                timestamp=_now_iso(),
            ),
        )
        session.messages = [*prefix, *_flatten(kept_turns)]
        session.last_updated = _now_iso()

        return SessionCompactionResult(
            changed=True,
            removed_turns=len(dropped_turns),
            removed_messages=removed_messages,
            preserved_turns=len(kept_turns),
        )

    def rewind_session(self, session: Session, *, turns: int = 1) -> SessionRewindResult:
        """Remove the last *turns* user exchanges from the session in place."""

        if turns < 1:
            msg = "turns must be at least 1"
            raise ValueError(msg)

        prefix, grouped_turns = _split_prefix_and_turns(session.messages)
        if turns > len(grouped_turns):
            msg = "Cannot rewind beyond the start of the session."
            raise ValueError(msg)

        kept_turns = grouped_turns[:-turns]
        removed_turns = grouped_turns[-turns:]
        removed_messages = len(_flatten(removed_turns))

        session.messages = [*prefix, *_flatten(kept_turns)]
        session.last_updated = _now_iso()

        return SessionRewindResult(
            removed_turns=turns,
            removed_messages=removed_messages,
            remaining_turns=len(kept_turns),
        )

    def branch_for_turn(self, session: Session, *, turn_number: int, tag: str | None = None) -> Session:
        """Create a branched session that keeps turns up to *turn_number* inclusive."""

        prefix, turns = _split_prefix_and_turns(session.messages)
        if turn_number < 0 or turn_number > len(turns):
            msg = "Turn number is out of range."
            raise ValueError(msg)

        branch_point = len(prefix) + len(_flatten(turns[:turn_number]))
        return self._manager.branch_session(session.id, branch_point, tag=tag)


__all__ = [
    "SessionCompactionResult",
    "SessionContextService",
    "SessionContextSnapshot",
    "SessionRewindResult",
    "ToolUsageSummary",
]
