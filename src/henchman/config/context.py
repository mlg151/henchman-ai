"""Context file loading for project instructions.

This module handles discovery and loading of project instruction files
(HENCHMAN.md, .github/copilot-instructions.md, .gemini/GEMINI.md)
from the directory hierarchy.
"""

from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

DEFAULT_FILENAMES: tuple[str, ...] = (
    "HENCHMAN.md",
    ".github/copilot-instructions.md",
    ".gemini/GEMINI.md",
)
"""Default context filenames to search for, in priority order."""


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
        include_subdirs: bool = False,
    ) -> None:
        """Initialize the context loader.

        Args:
            filename: Single filename to discover (backward compat).
                Mutually exclusive with *filenames*.
            filenames: Sequence of filenames / relative paths to discover.
                Defaults to :data:`DEFAULT_FILENAMES`.
            include_subdirs: Whether to search subdirectories.
        """
        if filename is not None:
            self.filenames: tuple[str, ...] = (filename,)
        elif filenames is not None:
            self.filenames = tuple(filenames)
        else:
            self.filenames = DEFAULT_FILENAMES
        self.include_subdirs = include_subdirs

    @property
    def filename(self) -> str:
        """Return the first (primary) filename for backward compatibility."""
        return self.filenames[0]

    def _find_git_root(self, start: Path) -> Path | None:
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

    def _load_gitignore_patterns(self, directory: Path) -> list[str]:
        """Load gitignore patterns from a directory.

        Args:
            directory: Directory to check for .gitignore.

        Returns:
            List of gitignore patterns.
        """
        gitignore = directory / ".gitignore"
        if not gitignore.exists():
            return []

        patterns = []
        for line in gitignore.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                # Remove trailing slashes for directory patterns
                patterns.append(line.rstrip("/"))
        return patterns

    def _is_ignored(self, path: Path, patterns: list[str], base: Path) -> bool:
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

    def discover_files(self) -> list[Path]:  # noqa: C901, PLR0912
        """Discover all context files in the hierarchy.

        Returns:
            List of paths to context files, ordered from root to current.
        """
        files: list[Path] = []
        cwd = Path.cwd().resolve()

        # Global context: ~/.henchman/<filename> for each filename
        henchman_home = Path.home() / ".henchman"
        for fn in self.filenames:
            global_file = henchman_home / fn
            if global_file.exists():
                files.append(global_file)

        # Find git root to limit ancestor search
        git_root = self._find_git_root(cwd)
        stop_at = git_root or cwd

        # Ancestor context files (from root to cwd)
        ancestor_groups: list[list[Path]] = []
        current = cwd
        # Walk up from cwd to stop_at (inclusive)
        while True:
            group: list[Path] = []
            for fn in self.filenames:
                context_file = current / fn
                if context_file.exists() and context_file not in files:
                    group.append(context_file)
            if group:
                ancestor_groups.append(group)
            if current == stop_at:
                break
            current = current.parent

        # Add ancestors in root-to-cwd order (reverse dir order,
        # but preserve filename priority within each directory)
        for group in reversed(ancestor_groups):
            files.extend(group)

        # Subdirectory context files
        if self.include_subdirs and git_root:
            patterns = self._load_gitignore_patterns(cwd)
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
                        files.append(context_file)

        return files

    def load(self) -> str:
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
