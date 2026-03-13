"""Session data class for conversation persistence.

Provides the :class:`Session` dataclass that holds all conversation
state including messages, turn summaries, and branching metadata.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from .session_models import (
    SessionMessage,
    SessionMetadata,
    TurnSummaryRecord,
    message_from_dict,
    turn_summary_from_dict,
)

# ---------------------------------------------------------------------------
# Session dataclass
# ---------------------------------------------------------------------------


@dataclass
class Session:
    """A conversation session.

    Attributes:
        id: Unique session identifier.
        project_hash: Hash identifying the project.
        started: ISO timestamp when session started.
        last_updated: ISO timestamp of last update.
        messages: List of session messages.
        tag: Optional human-readable tag.
        plan_mode: Whether the session is in Plan Mode.
        turn_summaries: Summaries of completed turns.
        parent_id: ID of parent session if this is a branch.
        branch_point: Message index where branch occurred.
        template_id: ID of template this session was created from.
        template_parameters: Parameters used to instantiate template.
        export_metadata: Metadata for export/import operations.
    """

    id: str
    project_hash: str
    started: str
    last_updated: str
    messages: list[SessionMessage] = field(default_factory=list)
    tag: str | None = None
    plan_mode: bool = False
    turn_summaries: list[TurnSummaryRecord] = field(default_factory=list)
    active_agents: list[str] = field(default_factory=list)
    delegation_log: list[dict[str, Any]] = field(default_factory=list)
    parent_id: str | None = None
    branch_point: int | None = None
    template_id: str | None = None
    template_parameters: dict[str, Any] = field(default_factory=dict)
    export_metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self: Session) -> dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation.
        """
        return {
            "id": self.id,
            "tag": self.tag,
            "project_hash": self.project_hash,
            "started": self.started,
            "last_updated": self.last_updated,
            "plan_mode": self.plan_mode,
            "messages": [msg.to_dict() for msg in self.messages],
            "turn_summaries": [ts.to_dict() for ts in self.turn_summaries],
            "active_agents": self.active_agents,
            "delegation_log": self.delegation_log,
            "parent_id": self.parent_id,
            "branch_point": self.branch_point,
            "template_id": self.template_id,
            "template_parameters": self.template_parameters,
            "export_metadata": self.export_metadata,
        }

    def to_json(self: Session) -> str:
        """Serialize to JSON string.

        Returns:
            JSON string.
        """
        return json.dumps(self.to_dict(), indent=2)

    def get_metadata(self: Session) -> SessionMetadata:
        """Get session metadata.

        Returns:
            SessionMetadata for this session.
        """
        return SessionMetadata(
            id=self.id,
            tag=self.tag,
            project_hash=self.project_hash,
            started=self.started,
            last_updated=self.last_updated,
            message_count=len(self.messages),
        )


# ---------------------------------------------------------------------------
# Factory functions (module-level to avoid feature envy)
# ---------------------------------------------------------------------------


def session_from_dict(data: dict[str, Any]) -> Session:
    """Create a :class:`Session` from a dictionary.

    Args:
        data: Dictionary with session data.

    Returns:
        Session instance.
    """
    return Session(
        id=data["id"],
        tag=data.get("tag"),
        project_hash=data["project_hash"],
        started=data["started"],
        last_updated=data["last_updated"],
        plan_mode=data.get("plan_mode", False),
        messages=[message_from_dict(m) for m in data.get("messages", [])],
        turn_summaries=[turn_summary_from_dict(ts) for ts in data.get("turn_summaries", [])],
        active_agents=data.get("active_agents", []),
        delegation_log=data.get("delegation_log", []),
        parent_id=data.get("parent_id"),
        branch_point=data.get("branch_point"),
        template_id=data.get("template_id"),
        template_parameters=data.get("template_parameters", {}),
        export_metadata=data.get("export_metadata", {}),
    )


def session_from_json(json_str: str) -> Session:
    """Deserialize a :class:`Session` from a JSON string.

    Args:
        json_str: JSON string.

    Returns:
        Session instance.
    """
    return session_from_dict(json.loads(json_str))


# Backward-compatible classmethods
Session.from_dict = classmethod(  # type: ignore[attr-defined]
    lambda _cls, data: session_from_dict(data),
)
Session.from_json = classmethod(  # type: ignore[attr-defined]
    lambda _cls, json_str: session_from_json(json_str),
)
