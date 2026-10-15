"""Lexically qualified function names shared by AST detectors."""

from __future__ import annotations

import ast
from collections.abc import Iterator

FunctionNode = ast.FunctionDef | ast.AsyncFunctionDef


def iter_functions(
    tree: ast.AST, scope: tuple[str, ...] = ()
) -> Iterator[tuple[str, FunctionNode]]:
    """Yield functions in source order, including nested classes and functions."""
    pending: list[tuple[ast.AST, tuple[str, ...]]] = [(tree, scope)]
    while pending:
        node, parent_scope = pending.pop()
        node_scope = parent_scope
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            node_scope = (*parent_scope, node.name)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                yield ".".join(node_scope), node
        pending.extend((child, node_scope) for child in reversed(list(ast.iter_child_nodes(node))))


def has_docstring(body: list[ast.stmt]) -> bool:
    """Whether the leading statement is a Python docstring."""
    return bool(
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    )
