"""Detect stale documentation content that has drifted from source code."""

from __future__ import annotations

import ast
import re
from pathlib import Path

from scripts.doc_smell_detector.detectors.base import (
    DocSmellDetector,
    MarkdownFile,
    ScanContext,
)
from scripts.doc_smell_detector.models import (
    DocSmellInstance,
    DocSmellSeverity,
    DocSmellType,
)


def _extract_tool_names_from_builtins(ctx: ScanContext) -> set[str]:
    """Walk src/henchman/tools/builtins/ to find Tool subclass names."""
    tool_names: set[str] = set()
    builtins_prefix = "src/henchman/tools/builtins/"
    for src in ctx.python_sources:
        if not src.path.startswith(builtins_prefix):
            continue
        if src.tree is None:
            continue
        for node in ast.walk(src.tree):
            if not isinstance(node, ast.ClassDef):
                continue
            # Look for a 'name' property returning a string literal.
            for item in node.body:
                if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if item.name != "name":
                    continue
                for stmt in item.body:
                    if isinstance(stmt, ast.Return) and isinstance(
                        stmt.value, ast.Constant
                    ):
                        if isinstance(stmt.value.value, str):
                            tool_names.add(stmt.value.value)
    return tool_names


def _extract_provider_class_names(ctx: ScanContext) -> set[str]:
    """Find provider class names from src/henchman/providers/."""
    provider_names: set[str] = set()
    providers_prefix = "src/henchman/providers/"
    for src in ctx.python_sources:
        if not src.path.startswith(providers_prefix):
            continue
        if src.tree is None:
            continue
        for node in ast.walk(src.tree):
            if not isinstance(node, ast.ClassDef):
                continue
            # Look for a 'name' property returning a string literal.
            for item in node.body:
                if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if item.name != "name":
                    continue
                for stmt in item.body:
                    if isinstance(stmt, ast.Return) and isinstance(
                        stmt.value, ast.Constant
                    ):
                        if isinstance(stmt.value.value, str):
                            provider_names.add(stmt.value.value)
    return provider_names


def _find_tools_md(ctx: ScanContext) -> MarkdownFile | None:
    """Find docs/tools.md."""
    for md in ctx.markdown_files:
        if md.path == "docs/tools.md":
            return md
    return None


def _find_providers_md(ctx: ScanContext) -> MarkdownFile | None:
    """Find docs/providers.md."""
    for md in ctx.markdown_files:
        if md.path == "docs/providers.md":
            return md
    return None


def _extract_mentioned_names(content: str) -> set[str]:
    """Extract backtick-quoted names from Markdown content."""
    return set(re.findall(r"`([A-Za-z_]\w*)`", content))


def _find_hardcoded_line_counts(md: MarkdownFile) -> list[tuple[int, str]]:
    """Find patterns like '(123 lines' or 'N lines' that embed fragile counts."""
    pattern = re.compile(r"\b(\d{2,})\s+lines?\b", re.IGNORECASE)
    hits: list[tuple[int, str]] = []
    for i, line in enumerate(md.lines, 1):
        for m in pattern.finditer(line):
            hits.append((i, m.group(0)))
    return hits


class StaleContentDetector(DocSmellDetector):
    """Detect documentation content that has drifted from the actual codebase."""

    @property
    def name(self) -> str:
        return "stale_content"

    def detect(self, ctx: ScanContext) -> list[DocSmellInstance]:
        smells: list[DocSmellInstance] = []
        smells.extend(self._check_tool_staleness(ctx))
        smells.extend(self._check_provider_staleness(ctx))
        smells.extend(self._check_class_name_staleness(ctx))
        smells.extend(self._check_hardcoded_numbers(ctx))
        return smells

    # ------------------------------------------------------------------
    # Tool list staleness
    # ------------------------------------------------------------------
    def _check_tool_staleness(self, ctx: ScanContext) -> list[DocSmellInstance]:
        smells: list[DocSmellInstance] = []
        actual_tools = _extract_tool_names_from_builtins(ctx)
        if not actual_tools:
            return smells

        tools_md = _find_tools_md(ctx)
        if tools_md is None:
            return smells

        mentioned = _extract_mentioned_names(tools_md.content)
        # Tools present in code but missing from docs.
        undocumented = actual_tools - mentioned
        for tool in sorted(undocumented):
            smells.append(
                DocSmellInstance(
                    file=tools_md.path,
                    line=1,
                    smell_type=DocSmellType.STALE_CONTENT,
                    severity=DocSmellSeverity.HIGH,
                    message=(
                        f"Tool '{tool}' exists in source but is not "
                        f"documented in tools.md"
                    ),
                    suggested_fix=(
                        f"Add a section documenting the '{tool}' tool, "
                        f"including its parameters and usage."
                    ),
                ),
            )
        return smells

    # ------------------------------------------------------------------
    # Provider staleness
    # ------------------------------------------------------------------
    def _check_provider_staleness(self, ctx: ScanContext) -> list[DocSmellInstance]:
        smells: list[DocSmellInstance] = []
        actual_providers = _extract_provider_class_names(ctx)
        if not actual_providers:
            return smells

        providers_md = _find_providers_md(ctx)
        if providers_md is None:
            return smells

        content_lower = providers_md.content.lower()
        for prov in sorted(actual_providers):
            if prov.lower() not in content_lower:
                smells.append(
                    DocSmellInstance(
                        file=providers_md.path,
                        line=1,
                        smell_type=DocSmellType.STALE_CONTENT,
                        severity=DocSmellSeverity.HIGH,
                        message=(
                            f"Provider '{prov}' exists in source but is "
                            f"not mentioned in providers.md"
                        ),
                        suggested_fix=(
                            f"Add documentation for the '{prov}' provider "
                            f"including setup, API key, and example usage."
                        ),
                    ),
                )
        return smells

    # ------------------------------------------------------------------
    # Class / interface name staleness
    # ------------------------------------------------------------------
    def _check_class_name_staleness(
        self, ctx: ScanContext,
    ) -> list[DocSmellInstance]:
        smells: list[DocSmellInstance] = []
        # Collect actual public class names from source.
        actual_classes: set[str] = set()
        for src in ctx.python_sources:
            if src.tree is None:
                continue
            for node in ast.iter_child_nodes(src.tree):
                if isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
                    actual_classes.add(node.name)

        # Known stale names that sometimes appear in docs.
        stale_aliases: dict[str, str] = {
            "BaseProvider": "ModelProvider",
            "BaseTool": "Tool",
            "BaseExtension": "Extension",
        }

        for md in ctx.markdown_files:
            mentioned = _extract_mentioned_names(md.content)
            for stale_name, correct_name in stale_aliases.items():
                if stale_name in mentioned and correct_name in actual_classes:
                    # Find the line.
                    for i, line in enumerate(md.lines, 1):
                        if stale_name in line:
                            smells.append(
                                DocSmellInstance(
                                    file=md.path,
                                    line=i,
                                    smell_type=DocSmellType.STALE_CONTENT,
                                    severity=DocSmellSeverity.HIGH,
                                    message=(
                                        f"References '{stale_name}' but the "
                                        f"actual class is '{correct_name}'"
                                    ),
                                    suggested_fix=(
                                        f"Replace '{stale_name}' with "
                                        f"'{correct_name}'."
                                    ),
                                ),
                            )
                            break  # One smell per alias per file.
        return smells

    # ------------------------------------------------------------------
    # Hardcoded line counts
    # ------------------------------------------------------------------
    def _check_hardcoded_numbers(
        self, ctx: ScanContext,
    ) -> list[DocSmellInstance]:
        smells: list[DocSmellInstance] = []
        # Only check top-level docs (README, etc.) for fragile numbers.
        check_files = [
            md for md in ctx.markdown_files
            if md.path in ("README.md", "CONTRIBUTING.md")
            or md.path.startswith("docs/")
        ]
        for md in check_files:
            for line_num, match_text in _find_hardcoded_line_counts(md):
                smells.append(
                    DocSmellInstance(
                        file=md.path,
                        line=line_num,
                        smell_type=DocSmellType.STALE_CONTENT,
                        severity=DocSmellSeverity.LOW,
                        message=(
                            f"Hardcoded line count '{match_text}' may become "
                            f"stale as the codebase evolves"
                        ),
                        suggested_fix=(
                            "Remove the specific line count or replace with "
                            "a relative description (e.g. 'compact', 'concise')."
                        ),
                    ),
                )
        return smells
