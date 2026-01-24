"""Context file (HENCHMAN.md) loading.

This module handles discovery and loading of HENCHMAN.md context files
from the directory hierarchy.
"""

from __future__ import annotations

import fnmatch
from pathlib import Path


class ContextLoader:
    """Discovers and loads HENCHMAN.md context files.

    Context files are discovered in this order:
    1. Global: ~/.henchman/HENCHMAN.md
    2. Ancestors: Walk up from cwd to git root
    3. Subdirectories: Walk down from cwd (optional)

    Attributes:
        filename: The name of context files to discover.
        include_subdirs: Whether to search subdirectories.
    """

    def __init__(
        self,
        filename: str = "HENCHMAN.md",
        include_subdirs: bool = False,
    ) -> None:
        """Initialize the context loader.

        Args:
            filename: Name of context files to discover.
            include_subdirs: Whether to search subdirectories.
        """
        self.filename = filename
        self.include_subdirs = include_subdirs

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

    def discover_files(self) -> list[Path]:
        """Discover all context files in the hierarchy.

        Returns:
            List of paths to context files, ordered from root to current.
        """
        files: list[Path] = []
        cwd = Path.cwd().resolve()

        # Global context: ~/.henchman/HENCHMAN.md
        global_file = Path.home() / ".henchman" / self.filename
        if global_file.exists():
            files.append(global_file)

        # Find git root to limit ancestor search
        git_root = self._find_git_root(cwd)
        stop_at = git_root if git_root else cwd

        # Ancestor context files (from root to cwd)
        ancestors: list[Path] = []
        current = cwd
        # Walk up from cwd to stop_at (inclusive)
        while True:
            context_file = current / self.filename
            if context_file.exists() and context_file not in files:
                ancestors.append(context_file)
            if current == stop_at:
                break
            current = current.parent

        # Add ancestors in root-to-cwd order
        files.extend(reversed(ancestors))

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
                context_file = subdir / self.filename
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
