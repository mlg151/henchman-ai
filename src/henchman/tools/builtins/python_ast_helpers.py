"""Module-level helper functions for Python AST analysis.

Extracted from PythonAstTool to eliminate Feature Envy and reduce class size.
These are pure functions with no side effects — easy to test independently.
"""

from __future__ import annotations

import ast


def get_node_docstring(node: ast.AST) -> str | None:
    """Extract the first line of a docstring from a node.

    Args:
        node: AST node (function, class, or module).

    Returns:
        First line of docstring, or None.
    """
    if isinstance(
        node,
        (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module),
    ):
        docstring = ast.get_docstring(node)
        if docstring:
            return docstring.split("\n")[0].strip()
    return None


def get_decorator_name(d: ast.expr) -> str:
    """Extract the base name from a decorator node.

    Args:
        d: Decorator AST node.

    Returns:
        The decorator's base name, or empty string if not determinable.
    """
    if isinstance(d, ast.Name):
        return d.id
    if isinstance(d, ast.Attribute):
        return d.attr
    if isinstance(d, ast.Call):
        return get_decorator_name(d.func)
    return ""


def format_decorator(node: ast.expr) -> str:
    """Format a decorator node to string.

    Args:
        node: AST decorator node.

    Returns:
        String representation of the decorator.
    """
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{format_decorator(node.value)}.{node.attr}"
    if isinstance(node, ast.Call):
        return f"{format_decorator(node.func)}(...)"
    return "?"


def classify_method(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """Classify a method by its decorators.

    Args:
        node: AST function node.

    Returns:
        Classification string (e.g., "staticmethod", "classmethod", "property").
    """
    _known = ("staticmethod", "classmethod", "property", "abstractmethod")
    tags = [name for d in node.decorator_list if (name := get_decorator_name(d)) in _known]
    return ", ".join(tags)


def format_function_node(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    indent: int = 0,
    *,
    include_docstrings: bool = True,
    is_method: bool = False,
) -> list[str]:
    """Format a function/method definition.

    Args:
        node: AST function node.
        indent: Indentation level.
        include_docstrings: Include docstring in output.
        is_method: Whether this is a method inside a class.

    Returns:
        List of formatted lines.
    """
    prefix = "  " * indent
    kind = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"

    args = ast.unparse(node.args)

    returns = f" -> {ast.unparse(node.returns)}" if node.returns else ""
    decos = [f"{prefix}@{format_decorator(d)}" for d in node.decorator_list]
    end_line = node.end_lineno or node.lineno
    sig = f"{prefix}{kind} {node.name}({args}){returns}"

    tag = ""
    if is_method:
        classification = classify_method(node)
        if classification:
            tag = f"  [{classification}]"

    lines = [*decos, f"{sig}  [L{node.lineno}-{end_line}]{tag}"]

    if include_docstrings:
        docstring = get_node_docstring(node)
        if docstring:
            lines.append(f'{prefix}  """{docstring}"""')

    return lines


def format_class_node(
    node: ast.ClassDef,
    indent: int = 0,
    *,
    include_docstrings: bool = True,
) -> list[str]:
    """Format a class definition with its methods.

    Args:
        node: AST class node.
        indent: Indentation level.
        include_docstrings: Include docstrings in output.

    Returns:
        List of formatted lines.
    """
    prefix = "  " * indent
    bases = [ast.unparse(b) for b in node.bases]
    bases_str = f"({', '.join(bases)})" if bases else ""
    decos = [f"{prefix}@{format_decorator(d)}" for d in node.decorator_list]
    end_line = node.end_lineno or node.lineno

    lines = [
        *decos,
        f"{prefix}class {node.name}{bases_str}  [L{node.lineno}-{end_line}]",
    ]

    if include_docstrings:
        docstring = get_node_docstring(node)
        if docstring:
            lines.append(f'{prefix}  """{docstring}"""')

    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            lines.extend(
                format_function_node(
                    child,
                    indent + 1,
                    include_docstrings=include_docstrings,
                    is_method=True,
                ),
            )
        elif isinstance(child, ast.ClassDef):
            lines.extend(
                format_class_node(
                    child,
                    indent + 1,
                    include_docstrings=include_docstrings,
                ),
            )

    return lines


def format_import_node(node: ast.Import | ast.ImportFrom) -> str:
    """Format an import statement.

    Args:
        node: AST import node.

    Returns:
        Formatted import string.
    """
    names = ", ".join(a.name + (f" as {a.asname}" if a.asname else "") for a in node.names)
    if isinstance(node, ast.Import):
        return f"import {names}  [L{node.lineno}]"
    module = node.module or ""
    level = "." * (node.level or 0)
    return f"from {level}{module} import {names}  [L{node.lineno}]"


def add_imports_section(sections: list[str], tree: ast.Module) -> None:
    """Add imports section to sections if imports exist.

    Args:
        sections: List to append to.
        tree: AST module node.

    Returns:
        None
    """
    imports = [n for n in ast.iter_child_nodes(tree) if isinstance(n, (ast.Import, ast.ImportFrom))]
    if imports:
        sections.append("\n## Imports")
        sections.extend(format_import_node(imp) for imp in imports)


def add_assignments_section(sections: list[str], tree: ast.Module) -> None:
    """Add assignments section to sections if assignments exist.

    Args:
        sections: List to append to.
        tree: AST module node.

    Returns:
        None
    """
    assigns = [n for n in ast.iter_child_nodes(tree) if isinstance(n, (ast.Assign, ast.AnnAssign))]
    if not assigns:
        return
    sections.append("\n## Constants / Variables")
    for a in assigns:
        if isinstance(a, ast.AnnAssign) and a.target:
            name = ast.unparse(a.target)
            ann = ast.unparse(a.annotation) if a.annotation else "?"
            sections.append(f"{name}: {ann}  [L{a.lineno}]")
        elif isinstance(a, ast.Assign):
            names = ", ".join(ast.unparse(t) for t in a.targets)
            sections.append(f"{names}  [L{a.lineno}]")


def add_functions_and_classes_sections(
    sections: list[str],
    tree: ast.Module,
    *,
    include_docstrings: bool,
) -> None:
    """Add functions and classes sections to sections.

    Args:
        sections: List to append to.
        tree: AST module node.
        include_docstrings: Include first-line docstrings in output.

    Returns:
        None
    """
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            sections.append("")
            sections.extend(
                format_function_node(node, include_docstrings=include_docstrings),
            )
        elif isinstance(node, ast.ClassDef):
            sections.append("")
            sections.extend(
                format_class_node(node, include_docstrings=include_docstrings),
            )


def generate_symbol_table(
    tree: ast.Module,
    file_name: str,
    *,
    include_docstrings: bool,
) -> list[str]:
    """Generate symbol table sections from AST.

    Args:
        tree: AST module node.
        file_name: Name of the file being analyzed.
        include_docstrings: Include first-line docstrings in output.

    Returns:
        List of formatted sections.
    """
    sections: list[str] = [f"# Symbol table for {file_name}"]

    if include_docstrings:
        module_doc = get_node_docstring(tree)
        if module_doc:
            sections.append(f'"""{module_doc}"""')

    add_imports_section(sections, tree)
    add_assignments_section(sections, tree)
    add_functions_and_classes_sections(
        sections,
        tree,
        include_docstrings=include_docstrings,
    )

    return sections
