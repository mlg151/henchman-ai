"""Detect consistency errors across documentation and source files."""

from __future__ import annotations

import re
from typing import Any

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

# Regex to find GitHub repo URLs.
_GITHUB_URL_RE = re.compile(
    r"github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)",
)

# Regex to find coverage thresholds.
_COVERAGE_THRESHOLD_RE = re.compile(
    r"(?:coverage|cov[_-]fail[_-]under|cov)\s*(?:>|>=|=)\s*(\d+)",
    re.IGNORECASE,
)

# Alternative pattern for prose like "coverage > 80%".
_COVERAGE_PROSE_RE = re.compile(
    r"(?:test\s+)?coverage\s*(?:>|>=|of\s+)?\s*(\d+)\s*%",
    re.IGNORECASE,
)


def _find_md(ctx: ScanContext, name: str) -> MarkdownFile | None:
    """Find a Markdown file by exact relative path."""
    for md in ctx.markdown_files:
        if md.path == name:
            return md
    return None


class ConsistencyDetector(DocSmellDetector):
    """Detect contradictions and inconsistencies across project documentation."""

    @property
    def name(self) -> str:
        return "consistency"

    def detect(self, ctx: ScanContext) -> list[DocSmellInstance]:
        smells: list[DocSmellInstance] = []
        smells.extend(self._check_github_urls(ctx))
        smells.extend(self._check_coverage_thresholds(ctx))
        smells.extend(self._check_install_commands(ctx))
        return smells

    # ------------------------------------------------------------------
    # GitHub URL consistency
    # ------------------------------------------------------------------
    def _check_github_urls(self, ctx: ScanContext) -> list[DocSmellInstance]:
        smells: list[DocSmellInstance] = []

        # Collect all GitHub org/repo references with their source files.
        repo_refs: dict[str, list[tuple[str, int]]] = {}  # repo -> [(file, line)]

        def _normalise_repo(raw: str) -> str:
            """Normalise a repo reference: strip .git suffix, lowercase."""
            return raw.rstrip("/").removesuffix(".git").lower()

        def _collect(raw: str, file_path: str, line_num: int) -> None:
            norm = _normalise_repo(raw)
            repo_refs.setdefault(norm, []).append((file_path, line_num))

        # Check mkdocs.yml (treat as single-line for simplicity).
        if ctx.mkdocs_config:
            cfg_str = str(ctx.mkdocs_config)
            for m in _GITHUB_URL_RE.finditer(cfg_str):
                _collect(m.group(1), "mkdocs.yml", 1)

        # Check all Markdown files.
        for md in ctx.markdown_files:
            if md.path == "CONTRIBUTING.md":
                continue
            for i, line in enumerate(md.lines, 1):
                for m in _GITHUB_URL_RE.finditer(line):
                    _collect(m.group(1), md.path, i)

        # Check pyproject.toml if it exists.
        pyproject = ctx.project_root / "pyproject.toml"
        if pyproject.is_file():
            content = pyproject.read_text(encoding="utf-8", errors="replace")
            for i, line in enumerate(content.splitlines(), 1):
                for m in _GITHUB_URL_RE.finditer(line):
                    _collect(m.group(1), "pyproject.toml", i)

        # Filter out third-party repos: only flag repos that share the same
        # project name (last path component) — these are likely the *same*
        # project under different orgs/forks.
        # E.g. "matthew/henchman-ai" vs "mlg151/henchman-ai" are
        # the same project; "google/gemini-cli" is a different project.
        project_name_groups: dict[str, list[str]] = {}
        for repo in repo_refs:
            parts = repo.split("/")
            if len(parts) == 2:
                project_name_groups.setdefault(parts[1], []).append(repo)

        # Only flag groups with >1 org for the same project name.
        flagged_repos: set[str] = set()
        for _proj_name, repos in project_name_groups.items():
            if len(repos) > 1:
                flagged_repos.update(repos)

        # Also filter out placeholder repos (e.g. "your-username/...").
        placeholder_prefixes = ("your-username", "your-org", "example")
        flagged_repos = {
            r for r in flagged_repos
            if not any(r.lower().startswith(p) for p in placeholder_prefixes)
        }

        if len(flagged_repos) > 1:
            all_repos = sorted(flagged_repos)
            summary = ", ".join(f"'{r}'" for r in all_repos)
            # Pick the most-referenced repo as "canonical".
            flagged_refs = {
                r: locs for r, locs in repo_refs.items() if r in flagged_repos
            }
            canonical = max(flagged_refs, key=lambda r: len(flagged_refs[r]))
            for repo in flagged_repos:
                if repo == canonical:
                    continue
                for file_path, line_num in repo_refs.get(repo, []):
                    smells.append(
                        DocSmellInstance(
                            file=file_path,
                            line=line_num,
                            smell_type=DocSmellType.CONSISTENCY_ERROR,
                            severity=DocSmellSeverity.CRITICAL,
                            message=(
                                f"References GitHub repo '{repo}' but "
                                f"most files reference '{canonical}'. "
                                f"Found conflicting repos: {summary}"
                            ),
                            suggested_fix=(
                                f"Standardise all GitHub URLs to use "
                                f"'{canonical}'."
                            ),
                        ),
                    )

        # Also flag placeholder URLs separately.
        for md in ctx.markdown_files:
            if md.path == "CONTRIBUTING.md":
                continue
            for i, line in enumerate(md.lines, 1):
                for m in _GITHUB_URL_RE.finditer(line):
                    raw = m.group(1).rstrip("/").removesuffix(".git").lower()
                    parts = raw.split("/")
                    if len(parts) == 2 and any(
                        parts[0].startswith(p) for p in placeholder_prefixes
                    ):
                        smells.append(
                            DocSmellInstance(
                                file=md.path,
                                line=i,
                                smell_type=DocSmellType.CONSISTENCY_ERROR,
                                severity=DocSmellSeverity.HIGH,
                                message=(
                                    f"Contains placeholder GitHub URL "
                                    f"'{m.group(1)}' that should be "
                                    f"replaced with the actual repo URL"
                                ),
                                suggested_fix=(
                                    "Replace the placeholder URL with "
                                    "the actual project repository URL."
                                ),
                            ),
                        )

        return smells

    # ------------------------------------------------------------------
    # Coverage threshold consistency
    # ------------------------------------------------------------------
    def _check_coverage_thresholds(
        self, ctx: ScanContext,
    ) -> list[DocSmellInstance]:
        smells: list[DocSmellInstance] = []

        # Collect coverage thresholds from various files.
        thresholds: dict[int, list[tuple[str, int]]] = {}  # value -> [(file, line)]

        # Check pyproject.toml.
        pyproject = ctx.project_root / "pyproject.toml"
        if pyproject.is_file():
            content = pyproject.read_text(encoding="utf-8", errors="replace")
            for i, line in enumerate(content.splitlines(), 1):
                for m in _COVERAGE_THRESHOLD_RE.finditer(line):
                    val = int(m.group(1))
                    thresholds.setdefault(val, []).append(("pyproject.toml", i))

        # Check Markdown files.
        check_files = ["RELEASE_CHECKLIST.md", "CONTRIBUTING.md", "README.md"]
        for fname in check_files:
            md = _find_md(ctx, fname)
            if md is None:
                continue
            for i, line in enumerate(md.lines, 1):
                for m in _COVERAGE_PROSE_RE.finditer(line):
                    val = int(m.group(1))
                    thresholds.setdefault(val, []).append((md.path, i))

        # Check copilot/claude instructions.
        for pattern in (".github/copilot-instructions.md", ".claude/CLAUDE.md"):
            path = ctx.project_root / pattern
            if path.is_file():
                content = path.read_text(encoding="utf-8", errors="replace")
                for i, line in enumerate(content.splitlines(), 1):
                    for m in _COVERAGE_PROSE_RE.finditer(line):
                        val = int(m.group(1))
                        thresholds.setdefault(val, []).append((pattern, i))

        if len(thresholds) > 1:
            all_vals = sorted(thresholds.keys(), reverse=True)
            strictest = all_vals[0]
            summary = ", ".join(f"{v}%" for v in all_vals)
            for val, locations in thresholds.items():
                if val == strictest:
                    continue
                for file_path, line_num in locations:
                    smells.append(
                        DocSmellInstance(
                            file=file_path,
                            line=line_num,
                            smell_type=DocSmellType.CONSISTENCY_ERROR,
                            severity=DocSmellSeverity.MEDIUM,
                            message=(
                                f"States coverage threshold of {val}% but "
                                f"other files require {strictest}%. "
                                f"Found thresholds: {summary}"
                            ),
                            suggested_fix=(
                                f"Align all coverage requirements to "
                                f"{strictest}% (the strictest value)."
                            ),
                        ),
                    )

        return smells

    # ------------------------------------------------------------------
    # Install command consistency
    # ------------------------------------------------------------------
    def _check_install_commands(
        self, ctx: ScanContext,
    ) -> list[DocSmellInstance]:
        smells: list[DocSmellInstance] = []

        # Collect pip install commands across docs.
        install_re = re.compile(r"pip install\s+(.+?)(?:\s*$|`)", re.MULTILINE)
        install_variants: dict[str, list[tuple[str, int]]] = {}

        check_files = [
            "README.md",
            "CONTRIBUTING.md",
            "docs/getting-started.md",
            "docs/index.md",
        ]
        for fname in check_files:
            md = _find_md(ctx, fname)
            if md is None:
                continue
            for i, line in enumerate(md.lines, 1):
                for m in install_re.finditer(line):
                    cmd = m.group(1).strip().rstrip("`")
                    # Normalise: strip quotes, collapse whitespace.
                    cmd = re.sub(r"\s+", " ", cmd)
                    install_variants.setdefault(cmd, []).append((md.path, i))

        # Only flag if there are substantively different install commands.
        # Group by package name (first token).
        pkg_variants: dict[str, set[str]] = {}
        for cmd in install_variants:
            pkg = cmd.split()[0] if cmd.split() else cmd
            pkg_variants.setdefault(pkg, set()).add(cmd)

        for pkg, variants in pkg_variants.items():
            if len(variants) > 1:
                summary = ", ".join(f"'{v}'" for v in sorted(variants))
                for variant in variants:
                    for file_path, line_num in install_variants.get(variant, []):
                        smells.append(
                            DocSmellInstance(
                                file=file_path,
                                line=line_num,
                                smell_type=DocSmellType.CONSISTENCY_ERROR,
                                severity=DocSmellSeverity.MEDIUM,
                                message=(
                                    f"Install command 'pip install {variant}' "
                                    f"differs from other files. "
                                    f"Variants found: {summary}"
                                ),
                                suggested_fix=(
                                    "Standardise install commands across all "
                                    "documentation files."
                                ),
                            ),
                        )

        return smells
