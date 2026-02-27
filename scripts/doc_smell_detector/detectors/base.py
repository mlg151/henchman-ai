"""Base class for all documentation smell detectors."""

from __future__ import annotations

import ast
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from scripts.doc_smell_detector.models import DocSmellInstance


@dataclass
class MarkdownFile:
    """Parsed representation of a Markdown file."""

    path: str  # Relative path from project root.
    content: str
    lines: list[str] = field(default_factory=list)
    last_modified: datetime | None = None  # From git log or stat.

    def __post_init__(self) -> None:
        if not self.lines:
            self.lines = self.content.splitlines()


@dataclass
class PythonSource:
    """Parsed representation of a Python source file."""

    path: str  # Relative path from project root.
    source: str
    tree: ast.Module | None = None
    last_modified: datetime | None = None  # From git log or stat.


@dataclass
class ScanContext:
    """All parsed project state, shared across detectors.

    Built once by the scanner and passed to every detector.
    """

    project_root: Path
    mkdocs_config: dict[str, Any]  # Parsed mkdocs.yml (empty dict if absent).
    markdown_files: list[MarkdownFile]  # All discovered .md files.
    python_sources: list[PythonSource]  # All discovered .py source files.
    nav_pages: list[str]  # .md paths referenced in mkdocs nav (relative to docs/).
    docs_dir: str = "docs"  # mkdocs docs_dir setting.
    public_symbols: dict[str, list[str]] = field(default_factory=dict)
    file_last_modified: dict[str, datetime] = field(default_factory=dict)
    # file_last_modified: mapping of relative path -> last modified datetime.
    # public_symbols: mapping of module path -> list of public symbol names
    # extracted from __all__ or non-underscore top-level defs.


class DocSmellDetector(ABC):
    """Abstract base class for documentation smell detectors."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Short identifier for this detector (e.g. 'orphaned_pages')."""

    @abstractmethod
    def detect(self, ctx: ScanContext) -> list[DocSmellInstance]:
        """Run detection and return any smells found.

        Args:
            ctx: The shared scan context containing all parsed project state.

        Returns:
            List of detected documentation smells.
        """
