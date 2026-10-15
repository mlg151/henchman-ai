"""Static sandbox policy for runtime plugin loading."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Literal

from henchman.extensions.models import SecurityReport

_BLOCKED_IMPORTS = {
    "asyncio.subprocess",
    "ctypes",
    "httpx",
    "multiprocessing",
    "requests",
    "socket",
    "subprocess",
    "urllib",
}
_BLOCKED_CALLS = {
    "__import__",
    "compile",
    "eval",
    "exec",
    "open",
    "os.system",
    "subprocess.Popen",
    "subprocess.run",
}


class PluginSandbox:
    """Scan plugin source trees and block unsafe plugins when enforced."""

    def __init__(self, mode: Literal["none", "docker"] = "none") -> None:
        """Initialize the sandbox for one runtime mode."""

        self.mode = mode

    @property
    def enforced(self) -> bool:
        """Return whether sandbox enforcement is enabled."""

        return self.mode != "none"

    def scan_directory(self, plugin_dir: Path) -> SecurityReport:
        """Return a static security report for one plugin directory."""

        findings: list[str] = []
        if plugin_dir.is_dir():
            for source_file in sorted(plugin_dir.rglob("*.py")):
                findings.extend(self._scan_file(source_file, plugin_dir))
        return SecurityReport(
            plugin_name=plugin_dir.name,
            passed=not findings,
            risk_level="low" if not findings else "high",
            warnings=findings,
        )

    def allows_directory(self, plugin_dir: Path) -> tuple[bool, SecurityReport]:
        """Return whether a plugin directory is allowed under the current mode."""

        report = self.scan_directory(plugin_dir)
        return report.passed or not self.enforced, report

    def _scan_file(self, source_file: Path, plugin_dir: Path) -> list[str]:
        """Return static-analysis findings for one Python source file."""

        try:
            tree = ast.parse(source_file.read_text(encoding="utf-8"), filename=str(source_file))
        except SyntaxError as exc:
            relative = source_file.relative_to(plugin_dir)
            return [f"{relative}: syntax error blocks sandboxed loading ({exc.msg})"]

        findings: list[str] = []
        relative = source_file.relative_to(plugin_dir)
        for node in ast.walk(tree):
            findings.extend(_scan_node(node, relative))
        return findings


def _scan_node(node: ast.AST, relative: Path) -> list[str]:
    """Return any sandbox findings contributed by one AST node."""

    findings: list[str] = []
    if isinstance(node, ast.Import):
        for alias in node.names:
            module_name = alias.name
            if _is_blocked_import(module_name):
                findings.append(f"{relative}: blocked import '{module_name}'")
    elif isinstance(node, ast.ImportFrom):
        module_name = node.module or ""
        if _is_blocked_import(module_name):
            findings.append(f"{relative}: blocked import '{module_name}'")
    elif isinstance(node, ast.Call):
        qualified_name = _qualified_name(node.func)
        if qualified_name in _BLOCKED_CALLS:
            findings.append(f"{relative}: blocked call '{qualified_name}'")
    return findings


def _is_blocked_import(module_name: str) -> bool:
    """Return whether one imported module is blocked by the sandbox."""

    return any(
        module_name == blocked or module_name.startswith(f"{blocked}.")
        for blocked in _BLOCKED_IMPORTS
    )


def _qualified_name(node: ast.AST) -> str | None:
    """Return a dotted name for a call target when one can be resolved."""

    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _qualified_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return None
