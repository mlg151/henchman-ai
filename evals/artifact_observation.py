"""Bounded artifact fingerprints and event-time change evidence for evaluations."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Collection
from pathlib import Path
from typing import Any

from evals.models import ToolLog
from henchman.core.events import AgentEvent

_MAX_ARTIFACT_BYTES = 1_048_576


def fingerprint(path: Path) -> str | None:
    """Hash bounded file bytes; return unknown for unreadable or symlink artifacts."""
    try:
        if path.is_symlink() or not path.is_file():
            return None
        with path.open("rb") as source:
            data = source.read(_MAX_ARTIFACT_BYTES + 1)
        return hashlib.sha256(data).hexdigest() if len(data) <= _MAX_ARTIFACT_BYTES else None
    except OSError:
        return None


def tool_target(log: ToolLog, workspace: Path) -> str | None:
    """Resolve a tool's string path relative to the workspace, rejecting escapes."""
    raw = log.arguments.get("path")
    if not isinstance(raw, str):
        return None
    try:
        path = Path(raw)
        return (
            (path if path.is_absolute() else workspace / path)
            .resolve()
            .relative_to(workspace.resolve())
            .as_posix()
        )
    except (OSError, ValueError):
        return None


class ArtifactTimeline:
    """Track known artifacts at event boundaries, including non-file tool edits."""

    def __init__(
        self,
        workspace: Path,
        initial: dict[str, str | None],
        *,
        implementation_paths: Collection[str],
        protected_paths: Collection[str],
        fingerprint: Callable[[Path], str | None] = fingerprint,
    ) -> None:
        self.workspace = workspace
        self.initial = dict(initial)
        self.previous = dict(initial)
        self.implementation_paths = tuple(implementation_paths)
        self.protected_paths = tuple(protected_paths)
        self._fingerprint = fingerprint
        self.events_observed = 0
        self.first_change: int | None = None
        self.last_change: int | None = None
        self.protected_change = False
        self.snapshot_errors = {name for name, digest in initial.items() if digest is None}

    def snapshot(self, index: int) -> None:
        current = {name: self._fingerprint(self.workspace / name) for name in self.initial}
        self.snapshot_errors.update(name for name, digest in current.items() if digest is None)
        if any(current[name] != self.previous[name] for name in self.implementation_paths):
            if self.first_change is None:
                self.first_change = index
            self.last_change = index
        if any(current[name] != self.initial[name] for name in self.protected_paths):
            self.protected_change = True
        self.previous = current

    def __call__(self, _event: AgentEvent) -> None:
        self.snapshot(self.events_observed)
        self.events_observed += 1

    def finish(self, event_count: int) -> dict[str, Any]:
        # Catch a last mutation even if the producer emitted no subsequent event.
        self.snapshot(self.events_observed)
        return {
            "complete": self.events_observed == event_count and not self.snapshot_errors,
            "events_observed": self.events_observed,
            "first_implementation_change": self.first_change,
            "last_implementation_change": self.last_change,
            "protected_change_observed": self.protected_change,
            "snapshot_errors": sorted(self.snapshot_errors),
        }
