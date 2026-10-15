"""Project-local experimentation REPL sessions."""

from __future__ import annotations

import code
import io
import json
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar
from uuid import uuid4

from henchman.config.paths import resolve_project_settings_path


def _now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""

    return datetime.now(UTC).isoformat()


def _read_json(path: Path, *, default: object) -> object:
    """Read one JSON payload or return *default* when absent."""

    if not path.exists():
        return default
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return default


def _write_json(path: Path, payload: object) -> None:
    """Persist one JSON payload with stable formatting."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


@dataclass(frozen=True, slots=True)
class ReplEntryRecord:
    """One persisted REPL interaction entry."""

    code: str
    output: str
    created_at: str

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation."""

        return {"code": self.code, "output": self.output, "created_at": self.created_at}

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> ReplEntryRecord:
        """Create an entry record from persisted data."""

        return cls(
            code=str(payload.get("code", "")),
            output=str(payload.get("output", "")),
            created_at=str(payload.get("created_at", "")),
        )


@dataclass(frozen=True, slots=True)
class ReplSessionRecord:
    """Persisted metadata for one experimentation REPL session."""

    session_id: str
    name: str
    created_at: str
    updated_at: str
    closed_at: str | None
    history: tuple[ReplEntryRecord, ...]

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation."""

        return {
            "session_id": self.session_id,
            "name": self.name,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "closed_at": self.closed_at,
            "history": [entry.to_dict() for entry in self.history],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> ReplSessionRecord:
        """Create a session record from persisted data."""

        raw_history = payload.get("history", [])
        history = (
            tuple(
                ReplEntryRecord.from_dict(item)
                for item in raw_history
                if isinstance(item, dict)
            )
            if isinstance(raw_history, list)
            else ()
        )
        return cls(
            session_id=str(payload.get("session_id", "")),
            name=str(payload.get("name", "")),
            created_at=str(payload.get("created_at", "")),
            updated_at=str(payload.get("updated_at", "")),
            closed_at=str(payload["closed_at"]) if payload.get("closed_at") is not None else None,
            history=history,
        )


@dataclass(slots=True)
class _ReplRuntime:
    """In-memory REPL runtime shared per project root."""

    records: dict[str, ReplSessionRecord] = field(default_factory=dict)
    interpreters: dict[str, code.InteractiveInterpreter] = field(default_factory=dict)


class ExperimentReplService:
    """Manage local experimentation REPL sessions."""

    _runtimes: ClassVar[dict[Path, _ReplRuntime]] = {}

    def __init__(self, project_root: Path | None = None) -> None:
        """Initialize the REPL service for one project root."""

        self._project_root = (project_root or Path.cwd()).resolve()
        self._storage_dir = resolve_project_settings_path(self._project_root) / "repl"
        self._index_path = self._storage_dir / "index.json"
        runtime = self._runtimes.setdefault(self._storage_dir, _ReplRuntime())
        self._runtime = runtime
        if not runtime.records:
            self._load_runtime()

    def start_session(self, name: str | None = None) -> ReplSessionRecord:
        """Create and persist a new REPL session."""

        session_id = f"repl-{uuid4().hex[:12]}"
        now = _now_iso()
        record = ReplSessionRecord(
            session_id=session_id,
            name=name.strip() if isinstance(name, str) and name.strip() else session_id,
            created_at=now,
            updated_at=now,
            closed_at=None,
            history=(),
        )
        self._runtime.records[session_id] = record
        self._runtime.interpreters[session_id] = code.InteractiveInterpreter(locals={})
        self._persist_runtime()
        return record

    def list_sessions(self) -> list[ReplSessionRecord]:
        """Return all known REPL sessions."""

        return sorted(self._runtime.records.values(), key=lambda record: record.created_at)

    def get_session(self, session_id: str) -> ReplSessionRecord | None:
        """Return one REPL session when present."""

        return self._runtime.records.get(session_id)

    def execute(self, session_id: str, source: str) -> tuple[ReplSessionRecord, str]:
        """Execute one source snippet inside the named REPL session."""

        record = self.get_session(session_id)
        if record is None:
            msg = f"REPL session {session_id} not found."
            raise KeyError(msg)
        if record.closed_at is not None:
            msg = f"REPL session {session_id} is closed."
            raise ValueError(msg)

        interpreter = self._runtime.interpreters.setdefault(
            session_id,
            code.InteractiveInterpreter(locals={}),
        )
        buffer = io.StringIO()
        with redirect_stdout(buffer), redirect_stderr(buffer):
            incomplete = interpreter.runsource(source, symbol="exec")
        output = buffer.getvalue().strip() or "(ok)"
        if incomplete:
            output = "Incomplete input."

        entry = ReplEntryRecord(code=source, output=output, created_at=_now_iso())
        updated = replace(
            record,
            updated_at=_now_iso(),
            history=(*record.history, entry),
        )
        self._runtime.records[session_id] = updated
        self._persist_runtime()
        return updated, output

    def render_history(self, session_id: str) -> str:
        """Render a readable transcript for one REPL session."""

        record = self.get_session(session_id)
        if record is None:
            msg = f"REPL session {session_id} not found."
            raise KeyError(msg)
        if not record.history:
            return "(empty)"
        lines: list[str] = []
        for entry in record.history:
            lines.append(f">>> {entry.code}")
            lines.append(entry.output)
        return "\n".join(lines)

    def close_session(self, session_id: str) -> ReplSessionRecord:
        """Close one REPL session and persist the final metadata."""

        record = self.get_session(session_id)
        if record is None:
            msg = f"REPL session {session_id} not found."
            raise KeyError(msg)
        updated = replace(record, closed_at=record.closed_at or _now_iso(), updated_at=_now_iso())
        self._runtime.records[session_id] = updated
        self._persist_runtime()
        return updated

    def _load_runtime(self) -> None:
        """Load persisted REPL metadata into the shared runtime."""

        payload = _read_json(self._index_path, default=[])
        if not isinstance(payload, list):
            return
        for item in payload:
            if not isinstance(item, dict):
                continue
            record = ReplSessionRecord.from_dict(item)
            self._runtime.records[record.session_id] = record
            if record.closed_at is None:
                self._runtime.interpreters[record.session_id] = code.InteractiveInterpreter(
                    locals={},
                )

    def _persist_runtime(self) -> None:
        """Persist the current REPL session index."""

        payload = [
            record.to_dict()
            for record in sorted(self._runtime.records.values(), key=lambda item: item.created_at)
        ]
        _write_json(self._index_path, payload)
