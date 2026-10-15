"""Immutable workspace snapshot and diff tooling."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
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
class TungstenFileRecord:
    """One snapshotted file entry."""

    path: str
    sha256: str

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation."""

        return {"path": self.path, "sha256": self.sha256}

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> TungstenFileRecord:
        """Create a file record from persisted data."""

        return cls(path=str(payload.get("path", "")), sha256=str(payload.get("sha256", "")))


@dataclass(frozen=True, slots=True)
class TungstenSnapshotRecord:
    """Persisted immutable workspace snapshot."""

    snapshot_id: str
    name: str
    created_at: str
    files: tuple[TungstenFileRecord, ...]

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation."""

        return {
            "snapshot_id": self.snapshot_id,
            "name": self.name,
            "created_at": self.created_at,
            "files": [item.to_dict() for item in self.files],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> TungstenSnapshotRecord:
        """Create a snapshot record from persisted data."""

        raw_files = payload.get("files", [])
        files = (
            tuple(TungstenFileRecord.from_dict(item) for item in raw_files if isinstance(item, dict))
            if isinstance(raw_files, list)
            else ()
        )
        return cls(
            snapshot_id=str(payload.get("snapshot_id", "")),
            name=str(payload.get("name", "")),
            created_at=str(payload.get("created_at", "")),
            files=files,
        )


class TungstenService:
    """Manage immutable workspace snapshots for reproducible diffs."""

    def __init__(self, project_root: Path | None = None) -> None:
        """Initialize the Tungsten service for one project root."""

        self._project_root = (project_root or Path.cwd()).resolve()
        self._storage_dir = resolve_project_settings_path(self._project_root) / "tungsten"
        self._index_path = self._storage_dir / "snapshots.json"

    def snapshot(
        self,
        *,
        name: str,
        paths: list[str] | tuple[str, ...] | None = None,
    ) -> TungstenSnapshotRecord:
        """Create one immutable snapshot for the requested paths."""

        files = tuple(
            TungstenFileRecord(path=relative_path, sha256=self._hash_file(self._project_root / relative_path))
            for relative_path in self._collect_relative_paths(paths)
        )
        record = TungstenSnapshotRecord(
            snapshot_id=f"snapshot-{uuid4().hex[:12]}",
            name=name.strip() if name.strip() else "snapshot",
            created_at=_now_iso(),
            files=files,
        )
        snapshots = self._load_snapshots()
        snapshots[record.snapshot_id] = record
        self._persist_snapshots(snapshots)
        return record

    def list_snapshots(self) -> list[TungstenSnapshotRecord]:
        """Return all persisted snapshots."""

        return sorted(self._load_snapshots().values(), key=lambda item: item.created_at)

    def compare(self, left: str, right: str) -> tuple[str, ...]:
        """Compare two snapshots and return human-readable diff lines."""

        snapshots = self._load_snapshots()
        left_snapshot = snapshots[left]
        right_snapshot = snapshots[right]
        left_files = {item.path: item.sha256 for item in left_snapshot.files}
        right_files = {item.path: item.sha256 for item in right_snapshot.files}
        changes: list[str] = []
        for path in sorted(left_files.keys() | right_files.keys()):
            if path not in left_files:
                changes.append(f"added: {path}")
            elif path not in right_files:
                changes.append(f"removed: {path}")
            elif left_files[path] != right_files[path]:
                changes.append(f"modified: {path}")
        return tuple(changes or ["no changes"])

    def _collect_relative_paths(self, paths: list[str] | tuple[str, ...] | None) -> tuple[str, ...]:
        """Collect relative file paths included in a snapshot."""

        if paths:
            collected: list[str] = []
            for raw_path in paths:
                resolved = (self._project_root / raw_path).resolve()
                if resolved.is_file():
                    collected.append(str(resolved.relative_to(self._project_root)))
            return tuple(sorted(dict.fromkeys(collected)))

        collected = [
            str(path.relative_to(self._project_root))
            for path in self._project_root.rglob("*")
            if path.is_file() and ".henchman" not in path.parts and ".git" not in path.parts
        ]
        return tuple(sorted(collected))

    def _hash_file(self, path: Path) -> str:
        """Return the SHA-256 digest for one file."""

        return hashlib.sha256(path.read_bytes()).hexdigest()

    def _load_snapshots(self) -> dict[str, TungstenSnapshotRecord]:
        """Load persisted snapshots from disk."""

        payload = _read_json(self._index_path, default=[])
        if not isinstance(payload, list):
            return {}
        snapshots: dict[str, TungstenSnapshotRecord] = {}
        for item in payload:
            if not isinstance(item, dict):
                continue
            snapshot = TungstenSnapshotRecord.from_dict(item)
            snapshots[snapshot.snapshot_id] = snapshot
        return snapshots

    def _persist_snapshots(self, snapshots: dict[str, TungstenSnapshotRecord]) -> None:
        """Persist snapshots to project-local storage."""

        payload = [
            snapshot.to_dict()
            for snapshot in sorted(snapshots.values(), key=lambda item: item.created_at)
        ]
        _write_json(self._index_path, payload)
