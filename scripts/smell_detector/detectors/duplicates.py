"""Compatibility exports for conservative duplicate candidate detection."""

from henchman.analysis.smells.duplicates import (
    MIN_NODES_FOR_COMPARISON,
    DuplicateCodeDetector,
    DuplicateIndex,
)

__all__ = ["MIN_NODES_FOR_COMPARISON", "DuplicateCodeDetector", "DuplicateIndex"]
