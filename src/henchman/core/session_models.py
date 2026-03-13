"""Data models for session persistence.

Provides lightweight data classes for messages, metadata, and
turn summaries used throughout the session system.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from henchman.utils.serialization import AsDictMixin

# ---------------------------------------------------------------------------
# Session message
# ---------------------------------------------------------------------------


@dataclass
class SessionMessage(AsDictMixin):
    """A message in a session.

    Attributes:
        role: The role (user, assistant, tool, system).
        content: The message content.
        tool_calls: Tool calls made by the assistant.
        tool_call_id: ID of the tool call this message responds to.
        agent_id: ID of the agent that produced this message.
        agent_role: Role of the agent that produced this message.
    """

    role: str
    content: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None
    agent_id: str | None = None
    agent_role: str | None = None

    def to_dict(self: SessionMessage) -> dict[str, Any]:
        """Convert to dictionary, omitting ``None`` values.

        Returns:
            Dictionary representation with only non-None fields.
        """
        data: dict[str, Any] = {"role": self.role}
        if self.content is not None:
            data["content"] = self.content
        if self.tool_calls is not None:
            data["tool_calls"] = self.tool_calls
        if self.tool_call_id is not None:
            data["tool_call_id"] = self.tool_call_id
        if self.agent_id is not None:
            data["agent_id"] = self.agent_id
        if self.agent_role is not None:
            data["agent_role"] = self.agent_role
        return data


def message_from_dict(data: dict[str, Any]) -> SessionMessage:
    """Create a :class:`SessionMessage` from a dictionary.

    Args:
        data: Dictionary with message data.

    Returns:
        SessionMessage instance.
    """
    return SessionMessage(
        role=data["role"],
        content=data.get("content"),
        tool_calls=data.get("tool_calls"),
        tool_call_id=data.get("tool_call_id"),
        agent_id=data.get("agent_id"),
        agent_role=data.get("agent_role"),
    )


# Keep classmethod for backward compatibility
SessionMessage.from_dict = classmethod(  # type: ignore[attr-defined]
    lambda _cls, data: message_from_dict(data),
)


# ---------------------------------------------------------------------------
# Session metadata
# ---------------------------------------------------------------------------


@dataclass
class SessionMetadata(AsDictMixin):
    """Metadata about a session (without messages).

    Attributes:
        id: Unique session identifier.
        tag: Optional human-readable tag.
        project_hash: Hash identifying the project.
        started: ISO timestamp when session started.
        last_updated: ISO timestamp of last update.
        message_count: Number of messages in session.
    """

    id: str
    project_hash: str
    started: str
    last_updated: str
    message_count: int
    tag: str | None = None


def metadata_from_dict(data: dict[str, Any]) -> SessionMetadata:
    """Create a :class:`SessionMetadata` from a dictionary.

    Args:
        data: Dictionary with metadata.

    Returns:
        SessionMetadata instance.
    """
    return SessionMetadata(
        id=data["id"],
        tag=data.get("tag"),
        project_hash=data["project_hash"],
        started=data["started"],
        last_updated=data["last_updated"],
        message_count=data["message_count"],
    )


SessionMetadata.from_dict = classmethod(  # type: ignore[attr-defined]
    lambda _cls, data: metadata_from_dict(data),
)


# ---------------------------------------------------------------------------
# Turn summary record
# ---------------------------------------------------------------------------


@dataclass
class TurnSummaryRecord(AsDictMixin):
    """Summary of a completed turn for persistence.

    Attributes:
        turn_number: Sequential turn number in session.
        summary_text: LLM-generated summary of the turn.
        files_modified: List of files modified during the turn.
        tool_count: Number of tool calls made.
        timestamp: ISO timestamp when turn completed.
    """

    turn_number: int
    summary_text: str
    files_modified: list[str] = field(default_factory=list)
    tool_count: int = 0
    timestamp: str = ""

    def __hash__(self: TurnSummaryRecord) -> int:
        """Make TurnSummaryRecord hashable for deduplication."""
        return hash(
            (
                self.turn_number,
                self.summary_text,
                tuple(self.files_modified),
                self.tool_count,
                self.timestamp,
            )
        )


def turn_summary_from_dict(data: dict[str, Any]) -> TurnSummaryRecord:
    """Create a :class:`TurnSummaryRecord` from a dictionary.

    Args:
        data: Dictionary with turn summary data.

    Returns:
        TurnSummaryRecord instance.
    """
    return TurnSummaryRecord(
        turn_number=data["turn_number"],
        summary_text=data["summary_text"],
        files_modified=data.get("files_modified", []),
        tool_count=data.get("tool_count", 0),
        timestamp=data["timestamp"],
    )


TurnSummaryRecord.from_dict = classmethod(  # type: ignore[attr-defined]
    lambda _cls, data: turn_summary_from_dict(data),
)
