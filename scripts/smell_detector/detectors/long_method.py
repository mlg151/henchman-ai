"""Compatibility exports for function body length detection."""

from henchman.analysis.smells.long_method import (
    THRESHOLD_CRITICAL,
    THRESHOLD_HIGH,
    THRESHOLD_LOW,
    THRESHOLD_MEDIUM,
    LongMethodDetector,
)

__all__ = [
    "THRESHOLD_CRITICAL",
    "THRESHOLD_HIGH",
    "THRESHOLD_LOW",
    "THRESHOLD_MEDIUM",
    "LongMethodDetector",
]
