"""Conservative, standard-library-only Python code smell analysis."""

from henchman.analysis.smells.deep_nesting import DeepNestingDetector
from henchman.analysis.smells.duplicates import DuplicateCodeDetector, DuplicateIndex
from henchman.analysis.smells.long_method import LongMethodDetector
from henchman.analysis.smells.models import SmellInstance, SmellSeverity, SmellType

__all__ = [
    "DeepNestingDetector",
    "DuplicateCodeDetector",
    "DuplicateIndex",
    "LongMethodDetector",
    "SmellInstance",
    "SmellSeverity",
    "SmellType",
]
