"""Session data class for conversation persistence.

Provides the :class:`Session` dataclass that holds all conversation
state including messages, turn summaries, and branching metadata.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from henchman.utils.evidence_redaction import EvidenceRedactor

from .session_evidence import redact_session_payload
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


@dataclass(frozen=True)
class SessionAccountingReference:
    """Advisory run identities; only the accounting database authorizes dispatch."""

    store_id: str
    active_run_id: str | None
    run_ids: tuple[str, ...]
    active_owner_key: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.store_id, str) or not self.store_id.strip():
            raise ValueError("Invalid accounting store identity")
        if not isinstance(self.run_ids, tuple) or any(not isinstance(r, str) or not r.strip() for r in self.run_ids):
            raise ValueError("Invalid accounting run identities")
        if len(set(self.run_ids)) != len(self.run_ids):
            raise ValueError("Duplicate accounting run identity")
        if self.active_run_id is not None and self.active_run_id not in self.run_ids:
            raise ValueError("Active accounting run is missing from history")
        if self.active_owner_key is not None and (self.active_run_id is None or not isinstance(self.active_owner_key, str) or not self.active_owner_key.strip()):
            raise ValueError("Invalid active accounting owner")

    def to_dict(self) -> dict[str, Any]:
        return {"store_id": self.store_id, "active_run_id": self.active_run_id,
                "run_ids": list(self.run_ids), "active_owner_key": self.active_owner_key}

    @classmethod
    def from_dict(cls, value: Any) -> SessionAccountingReference:
        if not isinstance(value, dict) or set(value) - {"active_owner_key"} != {"store_id", "active_run_id", "run_ids"} or not isinstance(value["run_ids"], list):
            raise ValueError("Invalid accounting reference")
        return cls(value["store_id"], value["active_run_id"], tuple(value["run_ids"]), value.get("active_owner_key"))


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
        plan_mode_origin: Authority that opened the current plan mode —
            ``"user"`` (user-imposed read-only boundary) or ``"model"``
            (model-proposed planning). Only an authorized user/runtime
            transition may widen execution rights out of a user-imposed
            boundary.
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
    plan_mode_origin: str = "user"
    turn_summaries: list[TurnSummaryRecord] = field(default_factory=list)
    active_agents: list[str] = field(default_factory=list)
    delegation_log: list[dict[str, Any]] = field(default_factory=list)
    parent_id: str | None = None
    branch_point: int | None = None
    template_id: str | None = None
    template_parameters: dict[str, Any] = field(default_factory=dict)
    export_metadata: dict[str, Any] = field(default_factory=dict)
    accounting: SessionAccountingReference | None = None
    # Disk concurrency/recovery state is deliberately absent from portable exports.
    _storage_token: str | None = field(default=None, init=False, repr=False, compare=False)
    _storage_path: str | None = field(default=None, init=False, repr=False, compare=False)
    recovery_notice: str | None = field(default=None, init=False, compare=False)
    evidence_redactor: EvidenceRedactor = field(
        default_factory=EvidenceRedactor, init=False, repr=False, compare=False
    )

    def to_dict(self: Session) -> dict[str, Any]:
        """Project redacted evidence without changing live execution messages.

        Returns:
            Dictionary representation.
        """
        return redact_session_payload({
            "id": self.id,
            "tag": self.tag,
            "project_hash": self.project_hash,
            "started": self.started,
            "last_updated": self.last_updated,
            "plan_mode": self.plan_mode,
            "plan_mode_origin": self.plan_mode_origin,
            "messages": [msg.to_dict() for msg in self.messages],
            "turn_summaries": [ts.to_dict() for ts in self.turn_summaries],
            "active_agents": self.active_agents,
            "delegation_log": self.delegation_log,
            "parent_id": self.parent_id,
            "branch_point": self.branch_point,
            "template_id": self.template_id,
            "template_parameters": self.template_parameters,
            "export_metadata": self.export_metadata,
            **({"accounting": self.accounting.to_dict()} if self.accounting is not None else {}),
        }, self.evidence_redactor)

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
    raw_origin = data.get("plan_mode_origin", "user")
    # Legacy sessions persisted without an origin stay user-locked so a
    # model-callable exit can never widen rights it was never granted.
    plan_mode_origin = raw_origin if raw_origin in ("user", "model") else "user"

    return Session(
        id=data["id"],
        tag=data.get("tag"),
        project_hash=data["project_hash"],
        started=data["started"],
        last_updated=data["last_updated"],
        plan_mode=data.get("plan_mode", False),
        plan_mode_origin=plan_mode_origin,
        messages=[message_from_dict(m) for m in data.get("messages", [])],
        turn_summaries=[turn_summary_from_dict(ts) for ts in data.get("turn_summaries", [])],
        active_agents=data.get("active_agents", []),
        delegation_log=data.get("delegation_log", []),
        parent_id=data.get("parent_id"),
        branch_point=data.get("branch_point"),
        template_id=data.get("template_id"),
        template_parameters=data.get("template_parameters", {}),
        export_metadata=data.get("export_metadata", {}),
        accounting=SessionAccountingReference.from_dict(data["accounting"]) if data.get("accounting") is not None else None,
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
