"""Bounded Python source traversal shared by analysis and formatting."""

from __future__ import annotations

import os
from collections.abc import Iterator
from itertools import islice
from pathlib import Path
from threading import Event
from typing import Protocol

MAX_ENTRIES = 20_000
EXCLUDED_DIRECTORIES = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        ".nox",
        "build",
        "dist",
        ".agent_tasks",
    }
)


class TraversalReport(Protocol):
    """Coverage counters and diagnostics supplied by a traversal's caller."""

    entries_seen: int
    skipped_symlinks: int
    truncated: bool

    def error(self, path: Path, message: str) -> None:
        """Record a traversal error in the caller's report."""
        ...


def iter_python_files(
    root: Path,
    report: TraversalReport,
    stop: Event,
    *,
    suffixes: frozenset[str] = frozenset({".py"}),
    skip_virtualenvs: bool = False,
) -> Iterator[Path]:
    """Prune dependencies and bound directory enumeration as well as files."""
    return _iter_python_files(
        root,
        report,
        stop,
        max_entries=MAX_ENTRIES,
        suffixes=suffixes,
        skip_virtualenvs=skip_virtualenvs,
    )


def _iter_python_files(
    root: Path,
    report: TraversalReport,
    stop: Event,
    *,
    max_entries: int,
    suffixes: frozenset[str] = frozenset({".py"}),
    skip_virtualenvs: bool = False,
) -> Iterator[Path]:
    """Share traversal while retaining legacy callers' adjustable entry ceiling."""
    if root.is_file():
        if root.suffix in suffixes:
            yield root
        else:
            extensions = " or ".join(sorted(suffixes))
            report.error(root, f"Expected a {extensions} file or directory")
        return
    pending = [root]
    while pending and not stop.is_set() and not report.truncated:
        directory = pending.pop()
        try:
            if skip_virtualenvs and (directory / "pyvenv.cfg").is_file():
                continue
            remaining = max_entries - report.entries_seen
            with os.scandir(directory) as scan:
                entries = sorted(islice(scan, remaining + 1), key=lambda entry: entry.name)
            if len(entries) > remaining:
                report.truncated = True
                report.error(directory, "Directory entry budget exceeded")
                return
            report.entries_seen += len(entries)
            subdirectories = []
            for entry in entries:
                if stop.is_set() or report.truncated:
                    return
                if entry.is_symlink():
                    report.skipped_symlinks += 1
                elif entry.is_dir(follow_symlinks=False):
                    if entry.name not in EXCLUDED_DIRECTORIES:
                        subdirectories.append(Path(entry.path))
                elif entry.name.endswith(tuple(suffixes)) and entry.is_file(follow_symlinks=False):
                    yield Path(entry.path)
            pending.extend(reversed(subdirectories))
        except OSError as exc:
            report.error(directory, str(exc))
