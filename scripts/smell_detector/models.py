"""Compatibility exports for the reusable analysis data models."""

from henchman.analysis.smells.models import (
    SEVERITY_PENALTY,
    FileMetrics,
    FileReport,
    RepoReport,
    RepoSummary,
    SmellInstance,
    SmellSeverity,
    SmellType,
)

__all__ = [
    "SEVERITY_PENALTY",
    "FileMetrics",
    "FileReport",
    "RepoReport",
    "RepoSummary",
    "SmellInstance",
    "SmellSeverity",
    "SmellType",
]
