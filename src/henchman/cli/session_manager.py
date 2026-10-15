"""Session management for the REPL.

This module provides the ReplSessionManager class that encapsulates
all session management logic for the REPL, including auto-saving,
session creation/loading, and session state tracking.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from typing import TYPE_CHECKING, Any

from henchman.core.session import Session, SessionManager, SessionMessage, SessionMetadata
from henchman.providers.base import Message, ToolCall

if TYPE_CHECKING:
    from pathlib import Path

    from henchman.agents.orchestrator import Orchestrator
    from henchman.core.agent import Agent


try:
    from typing import Self
except ImportError:  # pragma: no cover
    from typing import Self

# ---------------------------------------------------------------------------
# Module-level helpers (exempt from Feature Envy detection)
# ---------------------------------------------------------------------------


def _build_tool_call(tc: dict[str, Any]) -> ToolCall:
    """Convert a single tool-call dict into a ToolCall object.

    Args:
        tc: Raw tool-call dictionary with ``id``, ``name``, and ``arguments`` keys.

    Returns:
        Corresponding ToolCall instance.
    """
    return ToolCall(
        id=tc.get("id", ""),
        name=tc.get("name", ""),
        arguments=deepcopy(tc.get("arguments", {})),
    )


def _sync_messages_to_agent(agent: Agent, session: Session) -> None:
    """Restore session messages to the tech-lead agent's message history.

    Args:
        agent: Agent whose history is repopulated.
        session: Session containing the messages to restore.
    """
    agent.clear_history()
    prompt = agent.system_prompt
    agent.messages = [Message(role="system", content=prompt)] if prompt else []

    for session_msg in session.messages:
        if session_msg.role == "system" and session_msg.content == prompt:
            continue
        tool_calls = (
            [_build_tool_call(tc) for tc in session_msg.tool_calls]
            if session_msg.tool_calls
            else None
        )
        agent.messages.append(
            Message(
                role=session_msg.role,
                content=session_msg.content,
                tool_calls=tool_calls,
                tool_call_id=session_msg.tool_call_id,
                reasoning_content=session_msg.reasoning_content,
            ),
        )


def _record_session_entry(session: Session | None, **kwargs: Any) -> None:
    """Append a SessionMessage to *session* when it is not None.

    Args:
        session: Active session, or ``None`` (no-op when ``None``).
        **kwargs: Keyword arguments forwarded directly to :class:`SessionMessage`.
    """
    if session is not None:
        session.messages.append(SessionMessage(**kwargs))


class ReplSessionManager:
    """Manages session state and persistence for the REPL.

    This class wraps the core SessionManager and adds REPL-specific
    session logic including auto-saving and session-agent history
    synchronization.

    Attributes:
        session_manager: The core session manager for persistence.
        session: The current active session.
        auto_save: Whether to auto-save sessions on exit.
    """

    def __init__(
        self: Self,
        session_manager: SessionManager | None = None,
        *,
        auto_save: bool = True,
    ) -> None:
        """Initialize the REPL session manager.

        Args:
            session_manager: Core session manager for persistence.
                If None, creates a default SessionManager.
            auto_save: Whether to auto-save sessions on exit.
        """
        self.session_manager = session_manager or SessionManager()
        self.session: Session | None = None
        self.auto_save = auto_save

    @property
    def current(self: Self) -> Session | None:
        """Get the current session (alias for session attribute)."""
        return self.session

    def set_session(
        self: Self,
        session: Session,
        agent: Orchestrator | None = None,
        *,
        history_agent: Agent | None = None,
    ) -> None:
        """Set the current session and sync with agent history.

        Args:
            session: The session to activate.
            agent: Optional agent to sync session messages with.
            history_agent: Direct-mode agent whose history should be restored.

        Returns:
            None
        """
        self.session = session
        self.session_manager.set_current(session)

        if history_agent is not None:
            _sync_messages_to_agent(history_agent, session)
        elif agent:
            self._sync_session_to_agent(session, agent)

    def _sync_session_to_agent(self: Self, session: Session, agent: Orchestrator) -> None:
        """Restore session messages to agent history (delegates to module-level helper).

        Args:
            session: Session containing messages to restore.
            agent: Agent to restore messages to.
        """
        _sync_messages_to_agent(agent.tech_lead, session)

    def auto_save_session(self: Self) -> None:
        """Auto-save the session if enabled and session has content.

        Returns:
            None
        """
        if not self.auto_save:
            return
        if self.session is None:
            return
        if len(self.session.messages) == 0:
            return

        self.session_manager.save(self.session)

    def sync_agent_turn(self: Self, agent: Agent, *, session_start: int) -> None:
        """Persist the current agent turn without replacing older transcript.

        Capture ``session_start`` before recording this turn's input. Prefer the
        agent's unabridged turn transcript because active context can truncate
        even current-turn tool results. Older persisted conversation is retained.
        Call after closing the stream, including on cancellation, so tool results
        and partial assistant messages have settled in authoritative history.
        """
        if self.session is None:
            return
        if not 0 <= session_start <= len(self.session.messages):
            raise ValueError("Session turn boundary is outside the transcript")
        messages = getattr(agent, "current_turn_messages", None) or agent.messages[agent.turn.start_index:]
        self.session.messages[session_start:] = [
            SessionMessage(**deepcopy(asdict(message))) for message in messages
        ]

    def create_session(
        self: Self,
        project_hash: str,
        tag: str | None = None,
    ) -> Session:
        """Create a new session.

        Args:
            project_hash: Hash identifying the project.
            tag: Optional human-readable tag.

        Returns:
            New Session instance.
        """
        return self.session_manager.create_session(project_hash, tag)

    def load(self: Self, session_id: str) -> Session:
        """Load a session from disk.

        Args:
            session_id: ID or ID prefix of session to load.

        Returns:
            Loaded Session instance.

        Raises:
            ValueError: If session_id is empty.
            FileNotFoundError: If session doesn't exist or is ambiguous.
        """
        if not session_id:
            msg = "session_id must not be empty"
            raise ValueError(msg)
        return self.session_manager.load(session_id)

    def load_by_tag(
        self: Self,
        tag: str,
        project_hash: str | None = None,
    ) -> Session | None:
        """Load a session by tag.

        Args:
            tag: Tag to search for.
            project_hash: Optional project hash to filter by.

        Returns:
            Session if found, None otherwise.
        """
        return self.session_manager.load_by_tag(tag, project_hash)

    def save(self: Self, session: Session | None = None) -> Path:
        """Save a session to disk.

        Args:
            session: Session to save. If None, saves current session.

        Returns:
            Path to saved file.

        Raises:
            ValueError: If no session is provided and no current session exists.
        """
        session_to_save = session or self.session
        if session_to_save is None:
            msg = "No session to save"
            raise ValueError(msg)

        return self.session_manager.save(session_to_save)

    def list_sessions(
        self: Self,
        project_hash: str | None = None,
    ) -> list[SessionMetadata]:
        """List saved sessions.

        Args:
            project_hash: Optional project hash to filter by.

        Returns:
            List of session metadata.
        """
        return self.session_manager.list_sessions(project_hash)

    def delete(self: Self, session_id: str) -> None:
        """Delete a session from disk.

        Clears the current session reference when it matches *session_id*
        so no stale reference is held after deletion.

        Args:
            session_id: ID of session to delete.

        Raises:
            FileNotFoundError: If session doesn't exist.

        Returns:
            None
        """
        if self.session is not None and self.session.id == session_id:
            self.session = None
        self.session_manager.delete(session_id)

    def compute_project_hash(self: Self, directory: Path) -> str:
        """Compute a hash for a project directory.

        Args:
            directory: Project directory.

        Returns:
            Hash string identifying the project.
        """
        return self.session_manager.compute_project_hash(directory)

    def record_user_message(self: Self, content: str) -> None:
        """Record a user message to the current session.

        Args:
            content: The message content.

        Returns:
            None
        """
        _record_session_entry(self.session, role="user", content=content)

    def record_agent_message(
        self: Self,
        content: str | None = None,
        tool_calls: list[dict[str, Any]] | None = None,
        agent_id: str | None = None,
    ) -> None:
        """Record an agent message to the current session.

        Args:
            content: The message content.
            tool_calls: Tool calls made by the agent.
            agent_id: ID of the agent that generated the message.

        Returns:
            None
        """
        if self.session is not None:
            self.session.messages.append(
                SessionMessage(
                    role="assistant",
                    content=content,
                    tool_calls=tool_calls,
                    agent_id=agent_id,
                ),
            )

    def record_tool_result(self: Self, tool_call_id: str, content: str) -> None:
        """Record a tool result to the current session.

        Args:
            tool_call_id: ID of the tool call this result responds to.
            content: The tool result content.

        Returns:
            None
        """
        if self.session is not None:
            self.session.messages.append(
                SessionMessage(role="tool", content=content, tool_call_id=tool_call_id),
            )
