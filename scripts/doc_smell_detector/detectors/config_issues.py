"""Detect MkDocs configuration issues."""

from __future__ import annotations

from typing import Any

from scripts.doc_smell_detector.detectors.base import DocSmellDetector, ScanContext
from scripts.doc_smell_detector.models import (
    DocSmellInstance,
    DocSmellSeverity,
    DocSmellType,
)


def _has_mermaid_blocks(ctx: ScanContext) -> bool:
    """Return True if any Markdown file contains ```mermaid blocks."""
    for md in ctx.markdown_files:
        if "```mermaid" in md.content:
            return True
    return False


def _has_mermaid_config(cfg: dict[str, Any]) -> bool:
    """Return True if superfences is configured with mermaid custom fences."""
    extensions = cfg.get("markdown_extensions", [])
    for ext in extensions:
        if isinstance(ext, dict) and "pymdownx.superfences" in ext:
            sf_cfg = ext["pymdownx.superfences"]
            if isinstance(sf_cfg, dict):
                fences = sf_cfg.get("custom_fences", [])
                for fence in fences:
                    if isinstance(fence, dict) and fence.get("name") == "mermaid":
                        return True
    return False


def _has_plugin(cfg: dict[str, Any], plugin_name: str) -> bool:
    """Return True if mkdocs.yml has a given plugin."""
    plugins = cfg.get("plugins", [])
    for p in plugins:
        if isinstance(p, str) and p == plugin_name:
            return True
        if isinstance(p, dict) and plugin_name in p:
            return True
    return False


def _has_api_docs(ctx: ScanContext) -> bool:
    """Return True if docs/api.md exists."""
    return any(md.path == "docs/api.md" for md in ctx.markdown_files)


class ConfigIssuesDetector(DocSmellDetector):
    """Detect issues in MkDocs configuration."""

    @property
    def name(self) -> str:
        return "config_issues"

    def detect(self, ctx: ScanContext) -> list[DocSmellInstance]:
        smells: list[DocSmellInstance] = []

        if not ctx.mkdocs_config:
            smells.append(
                DocSmellInstance(
                    file="mkdocs.yml",
                    line=1,
                    smell_type=DocSmellType.CONFIG_ISSUE,
                    severity=DocSmellSeverity.HIGH,
                    message="No mkdocs.yml found — documentation site is not configured",
                    suggested_fix="Create a mkdocs.yml with site_name, theme, and nav.",
                ),
            )
            return smells

        cfg = ctx.mkdocs_config

        # --- Mermaid rendering ---
        if _has_mermaid_blocks(ctx) and not _has_mermaid_config(cfg):
            smells.append(
                DocSmellInstance(
                    file="mkdocs.yml",
                    line=1,
                    smell_type=DocSmellType.CONFIG_ISSUE,
                    severity=DocSmellSeverity.MEDIUM,
                    message=(
                        "Markdown files contain ```mermaid blocks but "
                        "pymdownx.superfences is not configured with "
                        "mermaid custom fences — diagrams won't render"
                    ),
                    suggested_fix=(
                        "Add custom_fences mermaid configuration to "
                        "pymdownx.superfences in mkdocs.yml, or install "
                        "mkdocs-mermaid2-plugin."
                    ),
                ),
            )

        # --- mkdocstrings plugin ---
        if _has_api_docs(ctx) and not _has_plugin(cfg, "mkdocstrings"):
            smells.append(
                DocSmellInstance(
                    file="mkdocs.yml",
                    line=1,
                    smell_type=DocSmellType.CONFIG_ISSUE,
                    severity=DocSmellSeverity.LOW,
                    message=(
                        "docs/api.md exists but mkdocstrings plugin is "
                        "not configured — API docs are hand-written and "
                        "will drift from source code"
                    ),
                    suggested_fix=(
                        "Add mkdocstrings plugin to mkdocs.yml to "
                        "auto-generate API docs from docstrings."
                    ),
                ),
            )

        # --- Missing nav ---
        if "nav" not in cfg:
            smells.append(
                DocSmellInstance(
                    file="mkdocs.yml",
                    line=1,
                    smell_type=DocSmellType.CONFIG_ISSUE,
                    severity=DocSmellSeverity.MEDIUM,
                    message="mkdocs.yml has no 'nav' section — page order is undefined",
                    suggested_fix="Add a nav section to control page ordering and hierarchy.",
                ),
            )

        # --- Missing site_description or site_author ---
        for field in ("site_description", "site_author"):
            if field not in cfg:
                smells.append(
                    DocSmellInstance(
                        file="mkdocs.yml",
                        line=1,
                        smell_type=DocSmellType.CONFIG_ISSUE,
                        severity=DocSmellSeverity.LOW,
                        message=f"mkdocs.yml is missing '{field}'",
                        suggested_fix=f"Add '{field}' to mkdocs.yml for better SEO and metadata.",
                    ),
                )

        return smells
