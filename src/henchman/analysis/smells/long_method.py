"""Detect functions and methods that are too long.

Thresholds (body lines, excluding docstring):
  - 30–50  → LOW
  - 50–80  → MEDIUM
  - 80–120 → HIGH
  - 120+   → CRITICAL
"""

from __future__ import annotations

import ast

from henchman.analysis.smells.base import SmellDetector
from henchman.analysis.smells.models import SmellInstance, SmellSeverity, SmellType
from henchman.analysis.smells.symbols import has_docstring, iter_functions

THRESHOLD_LOW = 30
THRESHOLD_MEDIUM = 50
THRESHOLD_HIGH = 80
THRESHOLD_CRITICAL = 120


def _body_line_count(node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """Return the number of lines in the function body, excluding the docstring."""
    body = node.body[1:] if has_docstring(node.body) else node.body
    if not body:
        return 0
    return max(0, (body[-1].end_lineno or body[-1].lineno) - body[0].lineno + 1)


def _severity_for_length(length: int) -> SmellSeverity:
    if length >= THRESHOLD_CRITICAL:
        return SmellSeverity.CRITICAL
    if length >= THRESHOLD_HIGH:
        return SmellSeverity.HIGH
    if length >= THRESHOLD_MEDIUM:
        return SmellSeverity.MEDIUM
    return SmellSeverity.LOW


class LongMethodDetector(SmellDetector):
    """Flags functions/methods whose body exceeds 30 lines."""

    @property
    def name(self) -> str:
        return "Long Method"

    def detect(
        self,
        tree: ast.Module,
        source: str,
        filepath: str,
    ) -> list[SmellInstance]:
        smells: list[SmellInstance] = []
        for symbol_name, node in iter_functions(tree):
            length = _body_line_count(node)
            if length < THRESHOLD_LOW:
                continue
            severity = _severity_for_length(length)
            smells.append(
                SmellInstance(
                    file=filepath,
                    line=node.lineno,
                    end_line=node.end_lineno or node.lineno,
                    smell_type=SmellType.LONG_METHOD,
                    severity=severity,
                    message=(
                        f"Function '{symbol_name}' has {length} lines (threshold: {THRESHOLD_LOW})"
                    ),
                    suggested_refactoring=(
                        "Extract Method — break this function into smaller, "
                        "intention-revealing helper functions."
                    ),
                    symbol_name=symbol_name,
                ),
            )
        return smells
