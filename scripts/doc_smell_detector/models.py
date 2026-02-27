"""Data models for the documentation smell detector.

Pure dataclasses — no external dependencies beyond stdlib.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime, timezone


class DocSmellType(enum.Enum):
    """Categories of documentation smells."""

    ORPHANED_PAGE = "Orphaned Page"
    MISSING_NAV_TARGET = "Missing Nav Target"
    STALE_CONTENT = "Stale Content"
    STALE_AGE = "Stale Age"
    BROKEN_LINK = "Broken Link"
    MISSING_DOCSTRING = "Missing Docstring"
    INCOMPLETE_DOCSTRING = "Incomplete Docstring"
    STALE_DOCSTRING = "Stale Docstring"
    CONFIG_ISSUE = "Config Issue"
    CONSISTENCY_ERROR = "Consistency Error"


class DocSmellSeverity(enum.Enum):
    """Severity levels for detected documentation smells."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# Maps severity to score deduction when grading.
SEVERITY_PENALTY: dict[DocSmellSeverity, int] = {
    DocSmellSeverity.LOW: 2,
    DocSmellSeverity.MEDIUM: 5,
    DocSmellSeverity.HIGH: 10,
    DocSmellSeverity.CRITICAL: 20,
}


@dataclass(frozen=True)
class DocSmellInstance:
    """A single detected documentation smell."""

    file: str
    line: int
    smell_type: DocSmellType
    severity: DocSmellSeverity
    message: str
    suggested_fix: str


@dataclass
class DocFileMetrics:
    """Metrics for a single documentation file."""

    word_count: int = 0
    heading_count: int = 0
    link_count: int = 0
    code_block_count: int = 0


@dataclass
class SourceFileMetrics:
    """Docstring metrics for a single Python source file."""

    total_public_apis: int = 0
    documented_apis: int = 0
    incomplete_docstrings: int = 0


@dataclass
class DocFileReport:
    """Smell report for a single file."""

    path: str
    smells: list[DocSmellInstance] = field(default_factory=list)
    doc_metrics: DocFileMetrics | None = None
    source_metrics: SourceFileMetrics | None = None
    last_modified: datetime | None = None
    grade: str = "A"
    score: float = 100.0


@dataclass
class DocRepoSummary:
    """Aggregate statistics for the full documentation scan."""

    total_doc_files: int = 0
    total_source_files_checked: int = 0
    total_smells: int = 0
    smells_by_type: dict[str, int] = field(default_factory=dict)
    smells_by_severity: dict[str, int] = field(default_factory=dict)
    docstring_coverage_pct: float = 100.0


@dataclass
class DocRepoReport:
    """Complete documentation smell report for a project."""

    project_root: str
    files: list[DocFileReport] = field(default_factory=list)
    summary: DocRepoSummary = field(default_factory=DocRepoSummary)
    overall_grade: str = "A"
    overall_score: float = 100.0
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )
