"""Per-session memory helpers for Tier 2 context management."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .session_data import Session
from .session_helpers import _generate_id, _now_iso

_MEMORY_METADATA_KEY = "session_memories"
_EXTRACTION_OPT_OUT_KEY = "memory_extraction_opt_out"
_MEMORY_KEYWORDS = (
    "always",
    "canonical",
    "important",
    "must",
    "never",
    "prefer",
    "remember",
    "use ",
)
_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")


@dataclass(slots=True)
class SessionMemoryRecord:
    """Persisted per-session memory entry."""

    id: str
    content: str
    kind: str
    source: str
    created_at: str
    message_index: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize the memory record."""

        return {
            "id": self.id,
            "content": self.content,
            "kind": self.kind,
            "source": self.source,
            "created_at": self.created_at,
            "message_index": self.message_index,
        }


def memory_from_dict(data: dict[str, Any]) -> SessionMemoryRecord:
    """Deserialize one persisted session-memory record."""

    return SessionMemoryRecord(
        id=str(data["id"]),
        content=str(data["content"]),
        kind=str(data.get("kind", "note")),
        source=str(data.get("source", "manual")),
        created_at=str(data.get("created_at", _now_iso())),
        message_index=data.get("message_index"),
    )


def _get_memory_payload(session: Session) -> list[dict[str, Any]]:
    """Return the raw persisted session-memory payload without mutating the session."""

    payload = session.export_metadata.get(_MEMORY_METADATA_KEY)
    if isinstance(payload, list):
        return [entry for entry in payload if isinstance(entry, dict)]
    return []


def _set_memory_payload(session: Session, records: list[SessionMemoryRecord]) -> None:
    """Persist the provided memory records onto the session."""

    session.export_metadata[_MEMORY_METADATA_KEY] = [record.to_dict() for record in records]


def _iter_memory_candidates(text: str) -> list[str]:
    """Extract deterministic memory candidates from one message body."""

    candidates: list[str] = []
    for fragment in _SPLIT_RE.split(text):
        cleaned = fragment.strip().strip("-*").strip()
        if len(cleaned) < 12:
            continue
        lowered = cleaned.casefold()
        if any(keyword in lowered for keyword in _MEMORY_KEYWORDS):
            candidates.append(cleaned)
    return candidates


class SessionMemoryService:
    """Manage the per-session memory store embedded in session metadata."""

    def list_memories(self, session: Session) -> list[SessionMemoryRecord]:
        """Return the persisted memory list for one session."""

        return [memory_from_dict(entry) for entry in _get_memory_payload(session)]

    def add_memory(
        self,
        session: Session,
        *,
        content: str,
        kind: str = "note",
        source: str = "manual",
        message_index: int | None = None,
    ) -> SessionMemoryRecord:
        """Append one new memory to the session."""

        record = SessionMemoryRecord(
            id=_generate_id(),
            content=content.strip(),
            kind=kind,
            source=source,
            created_at=_now_iso(),
            message_index=message_index,
        )
        records = self.list_memories(session)
        records.append(record)
        _set_memory_payload(session, records)
        return record

    def delete_memory(self, session: Session, memory_id: str) -> bool:
        """Delete one memory by id."""

        records = self.list_memories(session)
        remaining = [record for record in records if record.id != memory_id]
        if len(remaining) == len(records):
            return False
        _set_memory_payload(session, remaining)
        return True

    def edit_memory(
        self,
        session: Session,
        memory_id: str,
        *,
        content: str | None = None,
        kind: str | None = None,
        source: str | None = None,
    ) -> SessionMemoryRecord | None:
        """Edit one memory by id, touching only the fields provided.

        Returns the updated record, or ``None`` when no record matches
        ``memory_id`` (in which case the store is left untouched).
        """

        records = self.list_memories(session)
        updated: list[SessionMemoryRecord] = []
        found: SessionMemoryRecord | None = None
        for record in records:
            if record.id == memory_id:
                found = SessionMemoryRecord(
                    id=record.id,
                    content=content.strip() if content is not None else record.content,
                    kind=kind if kind is not None else record.kind,
                    source=source if source is not None else record.source,
                    created_at=record.created_at,
                    message_index=record.message_index,
                )
                updated.append(found)
            else:
                updated.append(record)
        if found is None:
            return None
        _set_memory_payload(session, updated)
        return found

    def clear_memories(self, session: Session) -> int:
        """Remove every stored memory; return how many were removed."""

        records = self.list_memories(session)
        _set_memory_payload(session, [])
        return len(records)

    def set_extraction_opt_out(self, session: Session, enabled: bool) -> None:
        """Persist the extraction/persistence opt-out flag for one session."""

        session.export_metadata[_EXTRACTION_OPT_OUT_KEY] = bool(enabled)

    def extraction_opt_out(self, session: Session) -> bool:
        """Return whether extraction persistence is opted out (default: off)."""

        flag = session.export_metadata.get(_EXTRACTION_OPT_OUT_KEY)
        return bool(flag) if isinstance(flag, bool) else False

    def extract_memories(self, session: Session) -> list[SessionMemoryRecord]:
        """Extract new memory entries heuristically from existing session messages.

        When the extraction opt-out flag is set, nothing is persisted and an
        empty list is returned.
        """

        if self.extraction_opt_out(session):
            return []

        existing = {
            record.content.casefold(): record
            for record in self.list_memories(session)
            if record.content.strip()
        }
        created: list[SessionMemoryRecord] = []

        for index, message in enumerate(session.messages):
            if message.role != "user" or not message.content:
                continue
            for candidate in _iter_memory_candidates(message.content):
                normalized = candidate.casefold()
                if normalized in existing:
                    continue
                kind = (
                    "preference"
                    if any(
                        keyword in normalized
                        for keyword in ("always", "canonical", "must", "never", "prefer", "use ")
                    )
                    else "note"
                )
                record = self.add_memory(
                    session,
                    content=candidate,
                    kind=kind,
                    source="extracted",
                    message_index=index,
                )
                existing[normalized] = record
                created.append(record)

        return created


__all__ = [
    "SessionMemoryRecord",
    "SessionMemoryService",
    "memory_from_dict",
]
