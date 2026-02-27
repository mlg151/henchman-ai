"""Registry of all documentation smell detectors."""

from __future__ import annotations

from scripts.doc_smell_detector.detectors.base import DocSmellDetector
from scripts.doc_smell_detector.detectors.broken_links import BrokenLinksDetector
from scripts.doc_smell_detector.detectors.config_issues import ConfigIssuesDetector
from scripts.doc_smell_detector.detectors.consistency import ConsistencyDetector
from scripts.doc_smell_detector.detectors.docstring_quality import (
    DocstringQualityDetector,
)
from scripts.doc_smell_detector.detectors.orphaned_pages import OrphanedPagesDetector
from scripts.doc_smell_detector.detectors.stale_content import StaleContentDetector
from scripts.doc_smell_detector.detectors.staleness_age import StalenessAgeDetector

ALL_DETECTORS: list[type[DocSmellDetector]] = [
    OrphanedPagesDetector,
    StaleContentDetector,
    StalenessAgeDetector,
    BrokenLinksDetector,
    DocstringQualityDetector,
    ConfigIssuesDetector,
    ConsistencyDetector,
]

__all__ = ["ALL_DETECTORS"]
