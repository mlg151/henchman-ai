"""Standalone XP Documentation Smell Detector.

Scans a project's documentation (Markdown files, MkDocs config, Python
docstrings) for common documentation smells. Produces a graded Markdown
report suitable for consumption by an AI documentation-improvement agent.

Dependencies: PyYAML (for mkdocs.yml parsing). Everything else uses stdlib.
"""

from scripts.doc_smell_detector.models import (
    DocFileReport,
    DocRepoReport,
    DocSmellInstance,
    DocSmellSeverity,
    DocSmellType,
)
from scripts.doc_smell_detector.scanner import scan_docs

__all__ = [
    "DocFileReport",
    "DocRepoReport",
    "DocSmellInstance",
    "DocSmellSeverity",
    "DocSmellType",
    "scan_docs",
]
