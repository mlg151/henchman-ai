"""Context file loading for project instructions.

This module handles discovery and loading of project instruction files
(HENCHMAN.md, .github/copilot-instructions.md, .gemini/GEMINI.md)
from the directory hierarchy.
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from collections.abc import Sequence

@dataclass(frozen=True)
class ContextSource:
    """Captured instruction text and its discovery provenance."""

    path: Path
    scope: Path
    kind: Literal["global", "repository"]
    order: int
    content: str

@dataclass(frozen=True)
class ContextSnapshot:
    """Immutable source records with their rendered instruction content."""

    sources: tuple[ContextSource, ...]
    content: str


DEFAULT_FILENAMES: tuple[str, ...] = (
    "HENCHMAN.md",
    ".henchman/HENCHMAN.md",
    ".github/copilot-instructions.md",
    ".gemini/GEMINI.md",
    "AGENTS.md",
)
"""Default context filenames to search for, in priority order."""


def _load_gitignore_patterns(base_dir: Path) -> list[str]:
    """Load simple gitignore-style patterns from ``base_dir/.gitignore``.

    Args:
        base_dir: Directory whose ``.gitignore`` file should be read.

    Returns:
        List of non-empty, non-comment patterns. Missing files produce ``[]``.
    """
    gitignore_path = base_dir / ".gitignore"
    if not gitignore_path.exists():
        return []

    patterns: list[str] = []
    for raw_line in gitignore_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.endswith("/"):
            line = line[:-1]
        patterns.append(line)
    return patterns


class ContextLoader:
    """Discovers and loads project instruction / context files.

    Searches for multiple context file patterns (HENCHMAN.md,
    .github/copilot-instructions.md, .gemini/GEMINI.md) in this order:

    1. Global: ~/.henchman/HENCHMAN.md
    2. Ancestors: Walk up from cwd to git root
    3. Subdirectories: Walk down from cwd (optional)

    At each directory, all configured filenames are checked in priority
    order and all matches are included.

    Attributes:
        filenames: Tuple of context file paths to discover.
        include_subdirs: Whether to search subdirectories.
    """

    def __init__(
        self,
        filename: str | None = None,
        filenames: Sequence[str] | None = None,
        *,
        include_subdirs: bool = False,
        start_dir: Path | None = None,
    ) -> None:
        """Initialize the context loader.

        Args:
            filename: Single filename to discover (backward compat).
                Mutually exclusive with *filenames*.
            filenames: Sequence of filenames / relative paths to discover.
                Defaults to :data:`DEFAULT_FILENAMES`.
            include_subdirs: Whether to search subdirectories.
            start_dir: Directory to start discovery from. When omitted,
                the current working directory is used.
        """
        if filename is not None:
            self.filenames: tuple[str, ...] = (filename,)
        elif filenames is not None:
            self.filenames = tuple(filenames)
        else:
            self.filenames = DEFAULT_FILENAMES
        self.include_subdirs = include_subdirs
        self._start_dir = start_dir

    @property
    def filename(self) -> str:
        """Return the first (primary) filename for backward compatibility."""
        return self.filenames[0]

    def _find_git_root(self: ContextLoader, start: Path) -> Path | None:
        """Find the git repository root.

        Args:
            start: Starting directory.

        Returns:
            Path to git root, or None if not in a git repo.
        """
        current = start.resolve()
        while current != current.parent:
            if (current / ".git").exists():
                return current
            current = current.parent
        return None

    def _is_ignored(self: ContextLoader, path: Path, patterns: list[str], base: Path) -> bool:
        """Check if a path matches any gitignore pattern.

        Args:
            path: Path to check.
            patterns: Gitignore patterns.
            base: Base directory for relative matching.

        Returns:
            True if path should be ignored.
        """
        try:
            relative = path.relative_to(base)
        except ValueError:
            return False

        for pattern in patterns:
            if fnmatch.fnmatch(str(relative), pattern):
                return True
            if fnmatch.fnmatch(relative.parts[0], pattern):
                return True
        return False

    def _global_context_files(self: ContextLoader) -> list[Path]:
        """Collect global context files from ~/.henchman/.

        Returns:
            Existing global context files in filename-priority order.
        """
        henchman_home = Path.home() / ".henchman"
        return [
            henchman_home / fn
            for fn in self.filenames
            if (henchman_home / fn).exists()
        ]

    def _ancestor_context_files(
        self: ContextLoader,
        cwd: Path,
        stop_at: Path,
        exclude: list[Path],
    ) -> list[Path]:
        """Collect context files from cwd up to stop_at, ordered root-first.

        Args:
            cwd: Starting directory (most specific).
            stop_at: Directory to stop walking at (e.g. git root).
            exclude: Files already collected (global files) to skip.

        Returns:
            Context files from stop_at down to cwd, preserving filename priority.
        """
        ancestor_groups: list[list[Path]] = []
        current = cwd
        while True:
            group = [
                current / fn
                for fn in self.filenames
                if (current / fn).exists() and (current / fn) not in exclude
            ]
            if group:
                ancestor_groups.append(group)
            if current == stop_at:
                break
            current = current.parent

        # Reverse so files appear root → cwd
        result: list[Path] = []
        for group in reversed(ancestor_groups):
            result.extend(group)
        return result

    def _subdir_context_files(self: ContextLoader, cwd: Path) -> list[Path]:
        """Collect context files from immediate non-hidden subdirectories.

        Respects .gitignore patterns found in *cwd*.

        Args:
            cwd: Directory whose subdirectories to search.

        Returns:
            Context files found one level below cwd.
        """
        patterns = _load_gitignore_patterns(cwd)
        found: list[Path] = []
        for subdir in cwd.iterdir():
            if not subdir.is_dir():
                continue
            if subdir.name.startswith("."):
                continue
            if self._is_ignored(subdir, patterns, cwd):
                continue
            for fn in self.filenames:
                context_file = subdir / fn
                if context_file.exists():
                    found.append(context_file)
        return found

    def discover_files(self: ContextLoader) -> list[Path]:
        """Discover all context files in the hierarchy.

        Returns:
            List of paths to context files, ordered from root to current.
        """
        cwd = (self._start_dir or Path.cwd()).resolve()
        git_root = self._find_git_root(cwd)
        stop_at = git_root or cwd
        stop_at_resolved = stop_at.resolve()

        # Gather global candidates
        globals_raw = self._global_context_files()

        # Gather repository candidates (ancestors + subdirs)
        ancestors_raw = self._ancestor_context_files(cwd, stop_at, globals_raw)

        subdirs_raw: list[Path] = []
        if self.include_subdirs and git_root:
            subdirs_raw = self._subdir_context_files(cwd)

        henchman_home = (Path.home() / ".henchman").resolve()

        final_files: list[Path] = []
        seen_resolved: set[Path] = set()

        # Filter globals
        for path in globals_raw:
            resolved = path.resolve()
            if resolved.is_relative_to(henchman_home) and resolved not in seen_resolved:
                final_files.append(path)
                seen_resolved.add(resolved)

        # Filter repository candidates
        for path in ancestors_raw + subdirs_raw:
            resolved = path.resolve()
            if resolved.is_relative_to(stop_at_resolved) and resolved not in seen_resolved:
                final_files.append(path)
                seen_resolved.add(resolved)

        return final_files


    def load_snapshot(self) -> ContextSnapshot:
        """Capture ordered instruction sources and their rendered content."""
        files = self.discover_files()
        global_root = Path.home() / ".henchman"
        global_paths = {global_root / name for name in self.filenames}
        records: list[ContextSource] = []
        sections: list[str] = []
        for order, path in enumerate(files):
            kind: Literal["global", "repository"]
            if path in global_paths and path.resolve().is_relative_to(global_root.resolve()):
                kind = "global"
                scope = global_root
            else:
                kind = "repository"
                matches = [
                    Path(name) for name in self.filenames
                    if Path(name).parts and path.parts[-len(Path(name).parts):] == Path(name).parts
                ]
                filename = max(matches, key=lambda item: len(item.parts), default=None)
                if filename is None:
                    raise ValueError(f"Instruction source does not match configured filenames: {path}")
                scope = path.parents[len(filename.parts) - 1]
            content = path.read_text(encoding="utf-8")
            records.append(ContextSource(path, scope, kind, order, content))
            sections.append(f"# Context: {path}\n{content}")
        return ContextSnapshot(tuple(records), "\n\n---\n\n".join(sections))

    def load(self: ContextLoader) -> str:
        """Load and concatenate all context files.

        Returns:
            Concatenated context content with file headers.
        """
        files = self.discover_files()
        if not files:
            return ""

        sections: list[str] = []
        for path in files:
            content = path.read_text()
            sections.append(f"# Context: {path}\n{content}")

        return "\n\n---\n\n".join(sections)
