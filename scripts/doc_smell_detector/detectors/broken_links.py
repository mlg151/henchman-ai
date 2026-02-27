"""Detect broken internal links in Markdown documentation."""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath

from scripts.doc_smell_detector.detectors.base import DocSmellDetector, ScanContext
from scripts.doc_smell_detector.models import (
    DocSmellInstance,
    DocSmellSeverity,
    DocSmellType,
)

# Matches Markdown inline links: [text](target)
_INLINE_LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")

# Matches Markdown reference links: [text]: target
_REF_LINK_RE = re.compile(r"^\[([^\]]+)\]:\s+(\S+)", re.MULTILINE)

# URLs that are clearly external.
_EXTERNAL_PREFIXES = ("http://", "https://", "mailto:", "ftp://", "#")


def _extract_headings(lines: list[str]) -> set[str]:
    """Extract anchor slugs from Markdown headings.

    MkDocs / GitHub slugify: lowercase, replace spaces with hyphens,
    strip non-alphanumeric except hyphens.
    """
    heading_re = re.compile(r"^#{1,6}\s+(.+?)(?:\s*\{[^}]*\})?\s*$")
    slugs: set[str] = set()
    for line in lines:
        m = heading_re.match(line)
        if m:
            text = m.group(1).strip()
            slug = re.sub(r"[^\w\s-]", "", text.lower())
            slug = re.sub(r"[\s]+", "-", slug).strip("-")
            slugs.add(slug)
    return slugs


class BrokenLinksDetector(DocSmellDetector):
    """Detect broken internal links between Markdown files."""

    @property
    def name(self) -> str:
        return "broken_links"

    def detect(self, ctx: ScanContext) -> list[DocSmellInstance]:
        smells: list[DocSmellInstance] = []

        # Build lookup of all existing Markdown paths (relative to project root).
        existing_paths: set[str] = {md.path for md in ctx.markdown_files}

        # Build heading anchors per file for fragment checking.
        heading_anchors: dict[str, set[str]] = {}
        for md in ctx.markdown_files:
            heading_anchors[md.path] = _extract_headings(md.lines)

        for md in ctx.markdown_files:
            smells.extend(
                self._check_file(md.path, md.content, md.lines,
                                 existing_paths, heading_anchors, ctx),
            )

        return smells

    def _check_file(
        self,
        file_path: str,
        content: str,
        lines: list[str],
        existing_paths: set[str],
        heading_anchors: dict[str, set[str]],
        ctx: ScanContext,
    ) -> list[DocSmellInstance]:
        smells: list[DocSmellInstance] = []

        # Collect all links with line numbers.
        links: list[tuple[int, str, str]] = []  # (line, text, target)
        for i, line in enumerate(lines, 1):
            for m in _INLINE_LINK_RE.finditer(line):
                links.append((i, m.group(1), m.group(2)))
        for m in _REF_LINK_RE.finditer(content):
            # Approximate line number.
            line_num = content[: m.start()].count("\n") + 1
            links.append((line_num, m.group(1), m.group(2)))

        for line_num, link_text, target in links:
            # Skip external URLs.
            if any(target.startswith(p) for p in _EXTERNAL_PREFIXES):
                continue

            # Skip image/asset references that aren't .md.
            if target.startswith("!") or target.startswith("data:"):
                continue

            # Split target and fragment.
            fragment = ""
            if "#" in target:
                target, fragment = target.split("#", 1)

            # Skip empty targets (pure fragment links checked separately).
            if not target and fragment:
                # Check fragment against current file's headings.
                anchors = heading_anchors.get(file_path, set())
                if fragment and fragment not in anchors:
                    smells.append(
                        DocSmellInstance(
                            file=file_path,
                            line=line_num,
                            smell_type=DocSmellType.BROKEN_LINK,
                            severity=DocSmellSeverity.MEDIUM,
                            message=(
                                f"Anchor '#{fragment}' not found in "
                                f"headings of this file"
                            ),
                            suggested_fix=(
                                f"Check that a heading matching "
                                f"'#{fragment}' exists, or fix the anchor."
                            ),
                        ),
                    )
                continue

            if not target:
                continue

            # Resolve the target relative to the file's directory.
            file_dir = str(PurePosixPath(file_path).parent)
            resolved = str(PurePosixPath(file_dir) / target)
            # Normalize (remove ./ and ../ components).
            resolved = str(PurePosixPath(resolved))

            if resolved not in existing_paths:
                smells.append(
                    DocSmellInstance(
                        file=file_path,
                        line=line_num,
                        smell_type=DocSmellType.BROKEN_LINK,
                        severity=DocSmellSeverity.HIGH,
                        message=(
                            f"Link to '{target}' resolves to "
                            f"'{resolved}' which does not exist"
                        ),
                        suggested_fix=(
                            f"Fix the link target or create the missing "
                            f"file '{resolved}'."
                        ),
                    ),
                )
            elif fragment:
                # File exists, check fragment.
                anchors = heading_anchors.get(resolved, set())
                if fragment not in anchors:
                    smells.append(
                        DocSmellInstance(
                            file=file_path,
                            line=line_num,
                            smell_type=DocSmellType.BROKEN_LINK,
                            severity=DocSmellSeverity.MEDIUM,
                            message=(
                                f"Link to '{target}#{fragment}' — file exists "
                                f"but anchor '#{fragment}' not found"
                            ),
                            suggested_fix=(
                                f"Verify the heading exists in '{resolved}' "
                                f"or fix the fragment."
                            ),
                        ),
                    )

        return smells
