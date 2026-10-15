"""Detect the deepest control-flow point in each function.

Alternative branches (elif, except, match cases) do not add artificial nesting.
Nested functions and classes are separate scopes. Depth four is the first warning.
"""

from __future__ import annotations

import ast

from henchman.analysis.smells.base import SmellDetector
from henchman.analysis.smells.models import SmellInstance, SmellSeverity, SmellType
from henchman.analysis.smells.symbols import iter_functions

NESTING_THRESHOLD = 4
NESTING_NODES = (
    ast.If,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.With,
    ast.AsyncWith,
    ast.Try,
    ast.TryStar,
    ast.Match,
)


def _severity_for_depth(depth: int) -> SmellSeverity:
    if depth >= 8:
        return SmellSeverity.CRITICAL
    if depth >= 6:
        return SmellSeverity.HIGH
    if depth >= 5:
        return SmellSeverity.MEDIUM
    return SmellSeverity.LOW


class _NestingVisitor:
    """Measure one function body without crossing into another lexical scope."""

    def __init__(self) -> None:
        self.maximum_depth = 0
        self.deepest_node: ast.stmt | None = None

    def visit(self, node: ast.AST, depth: int = 0) -> None:
        pending = [(node, depth)]
        while pending:
            current, current_depth = pending.pop()
            if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            if isinstance(current, NESTING_NODES):
                current_depth += 1
                if current_depth > self.maximum_depth:
                    self.maximum_depth = current_depth
                    self.deepest_node = current
            pending.extend(
                (child, current_depth - int(_is_elif(current, child)))
                for child in reversed(list(ast.iter_child_nodes(current)))
            )


def _is_elif(parent: ast.AST, child: ast.AST) -> bool:
    """Distinguish an elif alternative from an indented if inside an else."""
    return (
        isinstance(parent, ast.If)
        and isinstance(child, ast.If)
        and len(parent.orelse) == 1
        and parent.orelse[0] is child
        and parent.col_offset == child.col_offset
    )


class DeepNestingDetector(SmellDetector):
    """Report at most one finding per function with depth of at least four."""

    @property
    def name(self) -> str:
        return "Deep Nesting"

    def detect(self, tree: ast.Module, source: str, filepath: str) -> list[SmellInstance]:
        findings: list[SmellInstance] = []
        for symbol_name, function in iter_functions(tree):
            visitor = _NestingVisitor()
            for statement in function.body:
                visitor.visit(statement)
            node = visitor.deepest_node
            depth = visitor.maximum_depth
            if node is None or depth < NESTING_THRESHOLD:
                continue
            findings.append(
                SmellInstance(
                    file=filepath,
                    line=node.lineno,
                    end_line=node.end_lineno or node.lineno,
                    smell_type=SmellType.DEEP_NESTING,
                    severity=_severity_for_depth(depth),
                    message=(
                        f"Nesting depth {depth} in '{symbol_name}' (threshold: {NESTING_THRESHOLD})"
                    ),
                    suggested_refactoring=(
                        "Extract Method / Introduce Guard Clause / "
                        "Replace Nested Conditional with Early Return."
                    ),
                    symbol_name=symbol_name,
                )
            )
        return findings
