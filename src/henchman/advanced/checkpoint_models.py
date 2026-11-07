"""Versioned content review records; byte payloads never contain redacted substitutes."""

from __future__ import annotations

import base64
import hashlib
import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class FileState:
    """An exact supported file, absence, or an explicit non-restorable reason."""

    status: str
    content: bytes | None = None
    mode: int | None = None
    parents: tuple[tuple[int, int], ...] = ()

    @property
    def restorable(self) -> bool:
        return self.status in {"text", "missing"}

    def to_dict(self) -> dict[str, Any]:
        return {"status": self.status, "content": base64.b64encode(self.content).decode() if self.content is not None else None,
                "sha256": hashlib.sha256(self.content).hexdigest() if self.content is not None else None,
                "mode": self.mode, "parents": self.parents}

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> FileState:
        if not isinstance(value, dict) or set(value) != {"status", "content", "sha256", "mode", "parents"}:
            raise ValueError("Invalid checkpoint file fields")
        if value["status"] not in {"text", "missing", "excluded", "unsupported", "oversized", "binary", "secret"}:
            raise ValueError("Invalid checkpoint file status")
        parents = value["parents"]
        if not isinstance(parents, (tuple, list)) or any(
            not isinstance(pair, (tuple, list)) or len(pair) != 2
            or any(type(number) is not int or number < 0 for number in pair) for pair in parents
        ):
            raise ValueError("Invalid checkpoint parent identities")
        if value["content"] is not None and not isinstance(value["content"], str):
            raise ValueError("Invalid checkpoint content encoding")
        content = base64.b64decode(value["content"], validate=True) if value["content"] is not None else None
        if content is not None and hashlib.sha256(content).hexdigest() != value["sha256"]:
            raise ValueError("Checkpoint content integrity failed")
        if value["status"] == "text":
            if (content is None or type(value["mode"]) is not int or not 0 <= value["mode"] <= 0o777
                    or not isinstance(value["sha256"], str) or not re.fullmatch("[a-f0-9]{64}", value["sha256"])):
                raise ValueError("Checkpoint text lacks original bytes or mode")
            if "\x00" in content.decode("utf-8"):
                raise ValueError("Checkpoint text contains binary data")
        elif content is not None or value["sha256"] is not None or value["mode"] is not None:
            raise ValueError("Non-restorable checkpoint must not carry bytes")
        return cls(value["status"], content, value["mode"], tuple(tuple(pair) for pair in value["parents"]))


@dataclass(frozen=True)
class CheckpointRecord:
    checkpoint_id: str
    actor: str
    created_at: float
    state: str
    revision: int


@dataclass(frozen=True)
class ReviewHunk:
    index: int
    old_start: int
    old_end: int
    new_start: int
    new_end: int
    before: str
    after: str
    accepted: bool = False


@dataclass(frozen=True)
class ReviewFile:
    path: str
    before: FileState
    after: FileState
    hunks: tuple[ReviewHunk, ...]
    decision: str

    @property
    def restorable(self) -> bool:
        return self.before.restorable and self.after.restorable

    @property
    def hunk_status(self) -> str:
        return hunk_status(self.before, self.after)


def hunk_status(before: FileState, after: FileState) -> str:
    """Keep diff work bounded independently of the byte capture limit."""
    if before.status != "text" or after.status != "text":
        return "unsupported-type"
    if any(len((state.content or b"").decode().splitlines()) > 2000 for state in (before, after)):
        return "oversized"
    return "supported"


@dataclass(frozen=True)
class CheckpointReview:
    checkpoint_id: str
    revision: int
    files: tuple[ReviewFile, ...]
    metadata_policy: str = "posix-mode"


@dataclass(frozen=True)
class ReviewPlan:
    plan_id: str
    checkpoint_id: str
    revision: int
    decision: str
    paths: tuple[str, ...]
    metadata_policy: str = "posix-mode"


@dataclass(frozen=True)
class ReviewResult:
    changed_paths: tuple[str, ...]
    invalidate_checks: bool


class CheckpointConflict(RuntimeError):
    """Workspace or review authority changed; no unconditional overwrite is allowed."""

    def __init__(self, paths: tuple[str, ...] = (), reason: str = "Checkpoint conflicts with current workspace") -> None:
        super().__init__(reason)
        self.paths = paths
