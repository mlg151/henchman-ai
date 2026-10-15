"""Compatibility exports for scoped control-flow nesting detection."""

from henchman.analysis.smells.deep_nesting import (
    NESTING_NODES,
    NESTING_THRESHOLD,
    DeepNestingDetector,
)

__all__ = ["NESTING_NODES", "NESTING_THRESHOLD", "DeepNestingDetector"]
