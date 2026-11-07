"""Context file loading for project instructions.

This module handles discovery and loading of project instruction files
(HENCHMAN.md, .henchman/HENCHMAN.md, .github/copilot-instructions.md,
.gemini/GEMINI.md, AGENTS.md) from the directory hierarchy.
"""

from __future__ import annotations

import fnmatch
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from collections.abc import Sequence


_TRUNCATION_MARKER = "\n… [truncated: showing {shown} of {total} characters]"


@dataclass(frozen=True)
class ContextSource:
    """Captured instruction text and its discovery provenance."""

    path: Path
    scope: Path
    kind: Literal["global", "repository"]
    order: int
    content: str
    original_chars: int
    truncated: bool


@dataclass(frozen=True)
class ContextSourceDiagnostic:
    """Bounded per-source diagnostic for instruction loading."""

    path: Path
    scope: Path
    kind: Literal["global", "repository"]
    order: int
    chars: int
    original_chars: int
    truncated: bool


@dataclass(frozen=True)
class ContextDiscovery:
    """Immutable discovery settings retained for runtime refresh, never persisted."""

    filenames: tuple[str, ...]
    start_dir: Path
    boundary: Path
    max_source_chars: int | None
    targets: tuple[Path, ...] = ()


@dataclass(frozen=True)
class ContextSnapshot:
    """Immutable source records with their rendered instruction content."""

    sources: tuple[ContextSource, ...]
    content: str
    discovery: ContextDiscovery | None = None

    @property
    def digest(self) -> str:
        """Return the SHA-256 digest of the rendered instruction content."""
        return hashlib.sha256(self.content.encode("utf-8")).hexdigest()

    @property
    def truncated_sources(self) -> tuple[ContextSource, ...]:
        """Return the sources whose captured content was truncated."""
        return tuple(source for source in self.sources if source.truncated)

    def diagnostics(self) -> tuple[ContextSourceDiagnostic, ...]:
        """Return bounded per-source diagnostics for this snapshot."""
        return tuple(
            ContextSourceDiagnostic(
                path=source.path,
                scope=source.scope,
                kind=source.kind,
                order=source.order,
                chars=len(source.content),
                original_chars=source.original_chars,
                truncated=source.truncated,
            )
            for source in self.sources
        )

    def to_dict(self, *, include_content: bool = False) -> dict[str, Any]:
        """Serialize this snapshot for persistence and diagnostics.

        Args:
            include_content: When True, include captured instruction text and
                the rendered content. Defaults to metadata-only records so
                persisted provenance never duplicates instruction text.

        Returns:
            JSON-compatible dictionary describing the snapshot.
        """
        sources: list[dict[str, Any]] = []
        for source in self.sources:
            record: dict[str, Any] = {
                "path": str(source.path),
                "scope": str(source.scope),
                "kind": source.kind,
                "order": source.order,
                "chars": len(source.content),
                "original_chars": source.original_chars,
                "truncated": source.truncated,
                "sha256": hashlib.sha256(source.content.encode("utf-8")).hexdigest(),
            }
            if include_content:
                record["content"] = source.content
            sources.append(record)
        payload: dict[str, Any] = {
            "version": 1,
            "digest": self.digest,
            "sources": sources,
        }
        if include_content:
            payload["content"] = self.content
        return payload


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
    .github/copilot-instructions.md, .gemini/GEMINI.md, AGENTS.md) in
    configured priority order:

    1. Global: ~/.henchman/<filename>
    2. Ancestors: Walk up from cwd to git root (root-first)
    3. Subdirectories: Walk down from cwd (optional)

    At each directory, all configured filenames are checked in priority
    order and all matches are included. Deeper-scope instructions render
    after broader ones so they take precedence by position.

    Attributes:
        filenames: Tuple of context file paths to discover.
        include_subdirs: Whether to search subdirectories.
        max_source_chars: Optional per-source capture limit.
    """

    _scope_boundary: Path | None = None

    def __init__(
        self,
        filename: str | None = None,
        filenames: Sequence[str] | None = None,
        *,
        include_subdirs: bool = False,
        start_dir: Path | None = None,
        max_source_chars: int | None = None,
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
            max_source_chars: Optional per-source capture limit. When set,
                captured content is truncated with an explicit marker and the
                snapshot records the original size in its diagnostics.

        Raises:
            ValueError: If *max_source_chars* is smaller than 1.
        """
        if max_source_chars is not None and max_source_chars < 1:
            msg = "max_source_chars must be a positive integer"
            raise ValueError(msg)
        if filename is not None:
            self.filenames: tuple[str, ...] = (filename,)
        elif filenames is not None:
            self.filenames = tuple(filenames)
        else:
            self.filenames = DEFAULT_FILENAMES
        self.include_subdirs = include_subdirs
        self._start_dir = start_dir
        self.max_source_chars = max_source_chars

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
        stop_at = git_root or self._scope_boundary or cwd
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


    def load_for_path(self, target: Path) -> ContextSnapshot:
        """Load context from a specific target directory or file.

        Args:
            target: Path to the target directory or file.

        Returns:
            ContextSnapshot of the target.
        """
        base = (self._start_dir or Path.cwd()).resolve()
        git_root = self._find_git_root(base)
        boundary = git_root or self._scope_boundary or base

        resolved_target = (target if target.is_absolute() else base / target).resolve()

        if not resolved_target.is_relative_to(boundary):
            raise ValueError(f"target {resolved_target} is outside boundary {boundary}")

        search_dir = resolved_target if resolved_target.is_dir() else resolved_target.parent

        new_loader = ContextLoader(
            filenames=self.filenames,
            include_subdirs=False,
            start_dir=search_dir,
            max_source_chars=self.max_source_chars,
        )
        new_loader._scope_boundary = boundary
        return new_loader.load_snapshot()

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
            original_chars = len(content)
            truncated = False
            cap = self.max_source_chars
            if cap is not None and original_chars > cap:
                content = content[:cap] + _TRUNCATION_MARKER.format(shown=cap, total=original_chars)
                truncated = True
            records.append(
                ContextSource(path, scope, kind, order, content, original_chars, truncated),
            )
            sections.append(f"# Context: {path}\n{content}")
        start_dir = (self._start_dir or Path.cwd()).resolve()
        discovery = ContextDiscovery(
            self.filenames, start_dir,
            self._find_git_root(start_dir) or self._scope_boundary or start_dir,
            self.max_source_chars,
        )
        return ContextSnapshot(tuple(records), "\n\n---\n\n".join(sections), discovery)

    def load(self: ContextLoader) -> str:
        """Load and concatenate all context files.

        Returns:
            Concatenated context content with file headers.
        """
        return self.load_snapshot().content
