"""Detect missing, incomplete, or stale Python docstrings."""

from __future__ import annotations

import ast
import re

from scripts.doc_smell_detector.detectors.base import DocSmellDetector, ScanContext
from scripts.doc_smell_detector.models import (
    DocSmellInstance,
    DocSmellSeverity,
    DocSmellType,
)

# Patterns to skip when scanning for docstrings.
_SKIP_PATH_PATTERNS = (
    "tests/",
    "test_",
    "conftest.py",
    "__pycache__",
    ".venv/",
    "setup.py",
)


def _is_public(name: str) -> bool:
    """Return True if *name* looks like a public API symbol."""
    return not name.startswith("_")


def _get_docstring(node: ast.AST) -> str | None:
    """Extract the docstring from a function/class/module node."""
    return ast.get_docstring(node)


def _get_param_names(func: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    """Extract parameter names from a function def, excluding self/cls."""
    names: list[str] = []
    for arg in func.args.args:
        if arg.arg not in ("self", "cls"):
            names.append(arg.arg)
    for arg in func.args.posonlyargs:
        if arg.arg not in ("self", "cls"):
            names.append(arg.arg)
    for arg in func.args.kwonlyargs:
        names.append(arg.arg)
    if func.args.vararg:
        names.append(func.args.vararg.arg)
    if func.args.kwarg:
        names.append(func.args.kwarg.arg)
    return names


def _has_return_annotation(func: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Return True if the function has a return type annotation."""
    return func.returns is not None


def _returns_value(func: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Return True if function body contains 'return <value>' (not bare return)."""
    for node in ast.walk(func):
        if isinstance(node, ast.Return) and node.value is not None:
            return True
    return False


def _docstring_has_section(docstring: str, section: str) -> bool:
    """Check if a Google-style docstring has a given section header."""
    pattern = re.compile(rf"^\s*{section}\s*:", re.MULTILINE)
    return bool(pattern.search(docstring))


def _extract_documented_args(docstring: str) -> set[str]:
    """Extract parameter names from the Args: section of a Google-style docstring."""
    args_match = re.search(
        r"Args:\s*\n((?:\s+\S.*\n?)*)", docstring,
    )
    if not args_match:
        return set()
    args_block = args_match.group(1)
    # Each arg line starts with whitespace then the param name followed by colon or space.
    return set(re.findall(r"^\s+(\w+)\s*[:(]", args_block, re.MULTILINE))


class DocstringQualityDetector(DocSmellDetector):
    """Detect missing, incomplete, or stale docstrings in Python source files."""

    @property
    def name(self) -> str:
        return "docstring_quality"

    def detect(self, ctx: ScanContext) -> list[DocSmellInstance]:
        smells: list[DocSmellInstance] = []

        for src in ctx.python_sources:
            # Skip test files and non-source.
            if any(pat in src.path for pat in _SKIP_PATH_PATTERNS):
                continue
            if src.tree is None:
                continue
            smells.extend(self._check_module(src.path, src.tree))

        return smells

    def _check_module(
        self, path: str, tree: ast.Module,
    ) -> list[DocSmellInstance]:
        smells: list[DocSmellInstance] = []

        # Check module docstring.
        if not _get_docstring(tree):
            smells.append(
                DocSmellInstance(
                    file=path,
                    line=1,
                    smell_type=DocSmellType.MISSING_DOCSTRING,
                    severity=DocSmellSeverity.MEDIUM,
                    message="Module is missing a docstring",
                    suggested_fix="Add a module-level docstring describing the module's purpose.",
                ),
            )

        # Walk top-level definitions.
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef) and _is_public(node.name):
                smells.extend(self._check_class(path, node))
            elif isinstance(
                node, (ast.FunctionDef, ast.AsyncFunctionDef),
            ) and _is_public(node.name):
                smells.extend(self._check_function(path, node))

        return smells

    def _check_class(
        self, path: str, cls: ast.ClassDef,
    ) -> list[DocSmellInstance]:
        smells: list[DocSmellInstance] = []
        docstring = _get_docstring(cls)

        if not docstring:
            smells.append(
                DocSmellInstance(
                    file=path,
                    line=cls.lineno,
                    smell_type=DocSmellType.MISSING_DOCSTRING,
                    severity=DocSmellSeverity.HIGH,
                    message=f"Public class '{cls.name}' is missing a docstring",
                    suggested_fix=f"Add a Google-style docstring to '{cls.name}'.",
                ),
            )

        # Check public methods.
        for node in cls.body:
            if isinstance(
                node, (ast.FunctionDef, ast.AsyncFunctionDef),
            ) and _is_public(node.name):
                smells.extend(
                    self._check_function(path, node, class_name=cls.name),
                )

        return smells

    def _check_function(
        self,
        path: str,
        func: ast.FunctionDef | ast.AsyncFunctionDef,
        class_name: str | None = None,
    ) -> list[DocSmellInstance]:
        smells: list[DocSmellInstance] = []
        qualified = f"{class_name}.{func.name}" if class_name else func.name
        docstring = _get_docstring(func)
        params = _get_param_names(func)

        if not docstring:
            smells.append(
                DocSmellInstance(
                    file=path,
                    line=func.lineno,
                    smell_type=DocSmellType.MISSING_DOCSTRING,
                    severity=DocSmellSeverity.HIGH if not class_name else DocSmellSeverity.MEDIUM,
                    message=f"Public function '{qualified}' is missing a docstring",
                    suggested_fix=f"Add a Google-style docstring to '{qualified}'.",
                ),
            )
            return smells  # No point checking sections if missing entirely.

        # Check Args section.
        if params and not _docstring_has_section(docstring, "Args"):
            smells.append(
                DocSmellInstance(
                    file=path,
                    line=func.lineno,
                    smell_type=DocSmellType.INCOMPLETE_DOCSTRING,
                    severity=DocSmellSeverity.MEDIUM,
                    message=(
                        f"'{qualified}' has {len(params)} parameter(s) "
                        f"but no Args: section in docstring"
                    ),
                    suggested_fix=f"Add an Args: section documenting: {', '.join(params)}",
                ),
            )
        elif params and _docstring_has_section(docstring, "Args"):
            # Check for parameter mismatches.
            documented_args = _extract_documented_args(docstring)
            undocumented = set(params) - documented_args
            # Filter out **kwargs style params that may be documented differently.
            undocumented = {p for p in undocumented if p not in ("args", "kwargs")}
            if undocumented:
                smells.append(
                    DocSmellInstance(
                        file=path,
                        line=func.lineno,
                        smell_type=DocSmellType.STALE_DOCSTRING,
                        severity=DocSmellSeverity.HIGH,
                        message=(
                            f"'{qualified}' has undocumented parameters: "
                            f"{', '.join(sorted(undocumented))}"
                        ),
                        suggested_fix=(
                            f"Add these parameters to the Args: section: "
                            f"{', '.join(sorted(undocumented))}"
                        ),
                    ),
                )

        # Check Returns section.
        if (_has_return_annotation(func) or _returns_value(func)) and \
                not _docstring_has_section(docstring, "Returns") and \
                not _docstring_has_section(docstring, "Yields"):
            # Skip property methods — they don't need Returns.
            is_property = any(
                isinstance(d, ast.Name) and d.id == "property"
                for d in func.decorator_list
            ) or any(
                isinstance(d, ast.Attribute) and d.attr == "getter"
                for d in func.decorator_list
            )
            if not is_property:
                smells.append(
                    DocSmellInstance(
                        file=path,
                        line=func.lineno,
                        smell_type=DocSmellType.INCOMPLETE_DOCSTRING,
                        severity=DocSmellSeverity.LOW,
                        message=(
                            f"'{qualified}' returns a value but has "
                            f"no Returns: or Yields: section"
                        ),
                        suggested_fix=(
                            f"Add a Returns: section describing the "
                            f"return value of '{qualified}'."
                        ),
                    ),
                )

        return smells
