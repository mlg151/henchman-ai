"""Index syntax clone candidates without all-pairs comparisons.

Only root function names, docstrings, and source positions are ignored.
Identifiers, literals, call targets, signatures, and decorators remain significant.
Matches suggest review for reuse; they do not prove semantic equivalence across
scopes. Functions with fewer than 20 AST nodes (excluding docstrings) are skipped
because trivial accessors and stubs provide little useful evidence for extraction.
"""

from __future__ import annotations

import ast
import copy
import hashlib
from dataclasses import dataclass

from henchman.analysis.smells.base import SmellDetector
from henchman.analysis.smells.models import SmellInstance, SmellSeverity, SmellType
from henchman.analysis.smells.symbols import FunctionNode, has_docstring, iter_functions

MIN_NODES_FOR_COMPARISON = 20


def _normalise_tree(node: FunctionNode) -> FunctionNode:
    """Copy a function, removing only explicitly ignored syntax."""
    tree = copy.deepcopy(node)
    tree.name = "_"
    for child in ast.walk(tree):
        if isinstance(
            child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ) and has_docstring(child.body):
            child.body = child.body[1:]
    return tree


def _fingerprint(node: FunctionNode) -> str | None:
    normalised = _normalise_tree(node)
    if sum(1 for _ in ast.walk(normalised)) < MIN_NODES_FOR_COMPARISON:
        return None
    dump = ast.dump(normalised, annotate_fields=True, include_attributes=False)
    return hashlib.sha256(dump.encode()).hexdigest()


@dataclass(frozen=True)
class _Location:
    filepath: str
    line: int
    symbol_name: str


class DuplicateIndex:
    """Retain one location per fingerprint, never source text or parsed ASTs."""

    def __init__(self) -> None:
        self._representatives: dict[str, _Location] = {}

    def add(self, tree: ast.Module, source: str, filepath: str) -> list[SmellInstance]:
        """Report each later clone against the first occurrence in input order."""
        findings: list[SmellInstance] = []
        for symbol_name, node in iter_functions(tree):
            fingerprint = _fingerprint(node)
            if fingerprint is None:
                continue
            location = _Location(filepath, node.lineno, symbol_name)
            original = self._representatives.setdefault(fingerprint, location)
            if original != location:
                findings.append(_clone_finding(original, location, node))
        return findings


def _clone_finding(original: _Location, location: _Location, node: FunctionNode) -> SmellInstance:
    return SmellInstance(
        file=location.filepath,
        line=location.line,
        end_line=node.end_lineno or location.line,
        smell_type=SmellType.DUPLICATE_CODE,
        severity=SmellSeverity.HIGH,
        message=(
            f"Function '{location.symbol_name}' is a syntax clone candidate of "
            f"'{original.symbol_name}' at {original.filepath}:{original.line} "
            "(semantic equivalence is not established)"
        ),
        suggested_refactoring=(
            "Review scope and behavior, then reuse the existing implementation "
            "or extract shared logic where appropriate."
        ),
        symbol_name=location.symbol_name,
    )


class DuplicateCodeDetector(SmellDetector):
    """Compatibility facade for callers collecting repository ASTs."""

    @property
    def name(self) -> str:
        return "Duplicate Code"

    def detect(self, tree: ast.Module, source: str, filepath: str) -> list[SmellInstance]:
        """Leave duplicate detection to detect_repo, avoiding double reporting."""
        return []

    @staticmethod
    def detect_repo(file_trees: dict[str, ast.Module]) -> list[SmellInstance]:
        """Report syntax clones using the same index as incremental scans."""
        index = DuplicateIndex()
        return [
            finding
            for filepath, tree in file_trees.items()
            for finding in index.add(tree, "", filepath)
        ]
