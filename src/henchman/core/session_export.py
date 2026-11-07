"""Export and import helpers for session persistence.

Provides functions to serialise sessions to JSON or Markdown and
to import sessions from serialised representations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeAlias

from henchman.utils.tool_results import tool_message_content

from .session_memory import SessionMemoryService

if TYPE_CHECKING:
    from .session_data import Session
    from .session_models import SessionMessage, TurnSummaryRecord

# ---------------------------------------------------------------------------
# Semantic type aliases
# ---------------------------------------------------------------------------

SessionId: TypeAlias = str
IsoTimestamp: TypeAlias = str


# ---------------------------------------------------------------------------
# Markdown export helpers
# ---------------------------------------------------------------------------


def _escape_angle_brackets(text: str) -> str:
    """Escape angle brackets so literal placeholders survive Markdown/HTML rendering."""
    return text.replace("<", "\\<").replace(">", "\\>")


def _render_metadata(session: Session) -> list[str]:
    """Render session metadata as Markdown lines."""
    lines = [
        f"# Session: {session.tag or session.id}",
        "",
        "## Metadata",
        f"- **ID**: `{session.id}`",
        f"- **Project Hash**: `{session.project_hash}`",
        f"- **Started**: {session.started}",
        f"- **Last Updated**: {session.last_updated}",
        f"- **Messages**: {len(session.messages)}",
    ]
    if session.tag:
        lines.append(f"- **Tag**: {session.tag}")
    if session.parent_id:
        lines.append(f"- **Parent Session**: `{session.parent_id}`")
    if session.template_id:
        lines.append(f"- **Template**: `{session.template_id}`")
    lines.append("")
    return lines


def _render_message(index: int, msg: SessionMessage) -> list[str]:
    """Render a single message as Markdown lines."""
    lines = [f"### Turn {index + 1}: {msg.role}", ""]
    if msg.agent_id:
        lines.append(f"*Agent: {msg.agent_id}*  ")
    content = tool_message_content(msg.content, msg.tool_result) if msg.role == "tool" else msg.content
    if content:
        lines.extend([_escape_angle_brackets(content), ""])
    if msg.tool_calls:
        lines.append("**Tool Calls:**")
        for tc in msg.tool_calls:
            name = tc.get("name", "unknown")
            args: dict[str, Any] = tc.get("arguments", {})
            lines.append(f"- `{name}`: {args}")
        lines.append("")
    lines.extend(["---", ""])
    return lines


def _render_summaries(summaries: list[TurnSummaryRecord]) -> list[str]:
    """Render turn summaries as Markdown lines.

    Compaction records additionally render the absolute turn numbers they
    cover and their retained original messages, so compacted turns stay
    visible in the export.
    """
    if not summaries:
        return []
    lines = ["## Turn Summaries", ""]
    for ts in summaries:
        lines.extend(
            [
                f"### Turn {ts.turn_number}",
                f"*{ts.timestamp}*  ",
                "",
                ts.summary_text,
                "",
            ],
        )
        if ts.kind == "compaction":
            if ts.source_turns:
                lines.extend(
                    [f"**Covers turns:** {', '.join(str(turn) for turn in ts.source_turns)}", ""]
                )
            if ts.retained_messages:
                lines.extend(["**Retained messages:**", ""])
                for msg in ts.retained_messages:
                    lines.extend(_render_retained_message(msg))
    return lines


def _render_retained_message(msg: SessionMessage) -> list[str]:
    """Render one message retained by a compaction record as Markdown lines."""
    lines = [f"#### {msg.role}", ""]
    content = tool_message_content(msg.content, msg.tool_result) if msg.role == "tool" else msg.content
    if content:
        lines.extend([_escape_angle_brackets(content), ""])
    if msg.tool_calls:
        lines.append("**Tool Calls:**")
        for tc in msg.tool_calls:
            name = tc.get("name", "unknown")
            args: dict[str, Any] = tc.get("arguments", {})
            lines.append(f"- `{name}`: {args}")
        lines.append("")
    return lines


def _render_memories(session: Session) -> list[str]:
    """Render stored session memories as Markdown lines (empty when none)."""
    memories = SessionMemoryService().list_memories(session)
    if not memories:
        return []
    lines = ["## Session Memories", ""]
    for memory in memories:
        content = _escape_angle_brackets(memory.content)
        first_line, *continuation = content.splitlines()
        lines.append(
            f"- **{memory.kind}** ({memory.source}, {memory.created_at}): {first_line}"
        )
        # Indent continuation lines so each memory stays a single list item.
        for line in continuation:
            lines.append(f"  {line}")
    lines.append("")
    return lines


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def export_as_markdown(
    session: Session,
    *,
    include_metadata: bool = True,
) -> str:
    """Export a session as a Markdown string.

    Args:
        session: Session to export.
        include_metadata: Whether to include the metadata section.

    Returns:
        Markdown representation of the session.
    """
    # Project a copy before rendering so marked fields and their echoes share
    # the same policy as disk/JSON export without altering execution history.
    from .session_data import session_from_dict

    session = session_from_dict(session.to_dict())
    lines: list[str] = []
    if include_metadata:
        lines.extend(_render_metadata(session))
    lines.extend(["## Conversation", ""])
    for i, msg in enumerate(session.messages):
        lines.extend(_render_message(i, msg))
    lines.extend(_render_summaries(session.turn_summaries))
    lines.extend(_render_memories(session))
    return "\n".join(lines)


def import_json_session(
    session: Session,
    tag: str | None,
    new_id: SessionId,
    now: IsoTimestamp,
) -> None:
    """Mutate *session* so it represents a freshly-imported copy.

    Args:
        session: Session parsed from JSON to adjust.
        tag: Optional new tag.
        new_id: New unique ID for the imported session.
        now: ISO timestamp.

    Returns:
        None
    """
    session.id = new_id
    session.last_updated = now
    if tag:
        session.tag = tag
    session.export_metadata["imported_at"] = now
    session.export_metadata["original_id"] = session.id
