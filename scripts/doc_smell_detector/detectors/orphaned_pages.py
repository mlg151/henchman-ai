"""Detect orphaned documentation pages and missing nav targets."""

from __future__ import annotations

from scripts.doc_smell_detector.detectors.base import DocSmellDetector, ScanContext
from scripts.doc_smell_detector.models import (
    DocSmellInstance,
    DocSmellSeverity,
    DocSmellType,
)


class OrphanedPagesDetector(DocSmellDetector):
    """Detect Markdown files not referenced in mkdocs nav, and nav entries
    pointing to non-existent files."""

    @property
    def name(self) -> str:
        return "orphaned_pages"

    def detect(self, ctx: ScanContext) -> list[DocSmellInstance]:
        smells: list[DocSmellInstance] = []

        if not ctx.mkdocs_config:
            # No mkdocs.yml — nothing to check.
            return smells

        docs_dir = ctx.docs_dir
        nav_pages_set = set(ctx.nav_pages)

        # --- Files on disk but not in nav ---
        for md in ctx.markdown_files:
            # Only check files inside the docs dir.
            if not md.path.startswith(docs_dir + "/") and md.path != docs_dir:
                continue
            rel = md.path[len(docs_dir) + 1 :]  # Strip "docs/" prefix.
            if rel and rel not in nav_pages_set:
                smells.append(
                    DocSmellInstance(
                        file=md.path,
                        line=1,
                        smell_type=DocSmellType.ORPHANED_PAGE,
                        severity=DocSmellSeverity.CRITICAL,
                        message=(
                            f"'{rel}' exists in {docs_dir}/ but is not "
                            f"referenced in mkdocs.yml nav"
                        ),
                        suggested_fix=(
                            f"Add '{rel}' to the nav section in mkdocs.yml, "
                            f"or delete the file if it's no longer needed."
                        ),
                    ),
                )

        # --- Nav entries pointing to non-existent files ---
        existing_doc_paths = {
            md.path[len(docs_dir) + 1 :]
            for md in ctx.markdown_files
            if md.path.startswith(docs_dir + "/")
        }
        for nav_page in ctx.nav_pages:
            if nav_page not in existing_doc_paths:
                smells.append(
                    DocSmellInstance(
                        file="mkdocs.yml",
                        line=1,
                        smell_type=DocSmellType.MISSING_NAV_TARGET,
                        severity=DocSmellSeverity.CRITICAL,
                        message=(
                            f"Nav references '{nav_page}' but the file "
                            f"does not exist in {docs_dir}/"
                        ),
                        suggested_fix=(
                            f"Create {docs_dir}/{nav_page} or remove "
                            f"the nav entry from mkdocs.yml."
                        ),
                    ),
                )

        return smells
