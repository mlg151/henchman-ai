"""Project discovery and orchestration of all documentation smell detectors."""

from __future__ import annotations

import ast
import fnmatch
from pathlib import Path
from typing import Any

from scripts.doc_smell_detector.detectors import ALL_DETECTORS
from scripts.doc_smell_detector.detectors.base import (
    MarkdownFile,
    PythonSource,
    ScanContext,
)
from scripts.doc_smell_detector.grading import grade_repo
from scripts.doc_smell_detector.models import (
    DocFileMetrics,
    DocFileReport,
    DocRepoReport,
    DocSmellInstance,
    SourceFileMetrics,
)

# Default exclusion patterns for Python source files.
_PY_EXCLUDES: list[str] = [
    "tests/*",
    "*_test.py",
    "test_*.py",
    "conftest.py",
    "setup.py",
    "*/migrations/*",
    "*/.venv/*",
    "*/node_modules/*",
    "*/__pycache__/*",
    "*.egg-info/*",
]


def _should_exclude(path: str, excludes: list[str]) -> bool:
    """Return True if *path* matches any exclusion pattern."""
    return any(fnmatch.fnmatch(path, pat) for pat in excludes)


def _load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML file, returning an empty dict on failure.

    Uses PyYAML if available, otherwise falls back to a minimal parser.
    """
    if not path.is_file():
        return {}
    try:
        import yaml  # type: ignore[import-untyped]

        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data if isinstance(data, dict) else {}
    except ImportError:
        # Minimal fallback: read raw text — detectors that need parsed
        # YAML will degrade gracefully.
        return {"_raw": path.read_text(encoding="utf-8", errors="replace")}
    except Exception:
        return {}


def _extract_nav_pages(nav: Any, pages: list[str] | None = None) -> list[str]:
    """Recursively extract .md file paths from a mkdocs nav structure.

    The nav structure can be:
    - A list of dicts: [{"Home": "index.md"}, {"Guide": "guide.md"}]
    - A list of strings: ["index.md", "guide.md"]
    - Nested: [{"Section": [{"Page": "page.md"}]}]
    """
    if pages is None:
        pages = []
    if isinstance(nav, list):
        for item in nav:
            _extract_nav_pages(item, pages)
    elif isinstance(nav, dict):
        for value in nav.values():
            if isinstance(value, str) and value.endswith(".md"):
                pages.append(value)
            elif isinstance(value, list):
                _extract_nav_pages(value, pages)
    elif isinstance(nav, str) and nav.endswith(".md"):
        pages.append(nav)
    return pages


def _discover_markdown_files(root: Path) -> list[MarkdownFile]:
    """Find all Markdown files in the project, excluding hidden dirs and build outputs."""
    skip_dirs = {".git", ".venv", "node_modules", "__pycache__", "site",
                 "htmlcov", ".mypy_cache", ".pytest_cache", ".ruff_cache",
                 ".agent_tasks", "MagicMock", ".tox", "dist", "build",
                 ".eggs", "*.egg-info"}
    files: list[MarkdownFile] = []
    for p in sorted(root.rglob("*.md")):
        # Skip files in hidden/build directories.
        parts = p.relative_to(root).parts
        if any(part in skip_dirs or part.startswith(".") for part in parts[:-1]):
            continue
        rel = str(p.relative_to(root))
        try:
            content = p.read_text(encoding="utf-8", errors="replace")
            files.append(MarkdownFile(path=rel, content=content))
        except OSError:
            pass
    return files


def _discover_python_sources(
    root: Path,
    src_dirs: list[str],
    excludes: list[str],
) -> list[PythonSource]:
    """Find and parse Python source files."""
    sources: list[PythonSource] = []
    for src_dir in src_dirs:
        src_path = root / src_dir
        if not src_path.is_dir():
            continue
        for p in sorted(src_path.rglob("*.py")):
            rel = str(p.relative_to(root))
            if _should_exclude(rel, excludes):
                continue
            try:
                source = p.read_text(encoding="utf-8", errors="replace")
                tree = ast.parse(source, filename=rel)
                sources.append(PythonSource(path=rel, source=source, tree=tree))
            except SyntaxError:
                sources.append(PythonSource(path=rel, source="", tree=None))
            except OSError:
                pass
    return sources


def _compute_md_metrics(md: MarkdownFile) -> DocFileMetrics:
    """Compute basic metrics for a Markdown file."""
    words = len(md.content.split())
    headings = sum(1 for line in md.lines if line.startswith("#"))
    # Count Markdown links [text](url).
    import re

    links = len(re.findall(r"\[([^\]]*)\]\(([^)]+)\)", md.content))
    # Count fenced code blocks.
    code_blocks = md.content.count("```") // 2
    return DocFileMetrics(
        word_count=words,
        heading_count=headings,
        link_count=links,
        code_block_count=code_blocks,
    )


def _compute_source_metrics(
    src: PythonSource,
) -> SourceFileMetrics:
    """Compute docstring coverage metrics for a Python source file."""
    if src.tree is None:
        return SourceFileMetrics()

    total = 0
    documented = 0
    incomplete = 0

    for node in ast.iter_child_nodes(src.tree):
        if isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
            total += 1
            ds = ast.get_docstring(node)
            if ds:
                documented += 1
            # Check public methods.
            for item in node.body:
                if isinstance(
                    item, (ast.FunctionDef, ast.AsyncFunctionDef),
                ) and not item.name.startswith("_"):
                    total += 1
                    mds = ast.get_docstring(item)
                    if mds:
                        documented += 1
                    else:
                        incomplete += 1
        elif isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef),
        ) and not node.name.startswith("_"):
            total += 1
            ds = ast.get_docstring(node)
            if ds:
                documented += 1

    return SourceFileMetrics(
        total_public_apis=total,
        documented_apis=documented,
        incomplete_docstrings=incomplete,
    )


def scan_docs(
    project_root: str | Path,
    src_dirs: list[str] | None = None,
    skip_docstrings: bool = False,
) -> DocRepoReport:
    """Scan project documentation and produce a graded report.

    Args:
        project_root: Path to the project root directory.
        src_dirs: Python source directories to scan for docstrings.
            Defaults to ["src/henchman"].
        skip_docstrings: If True, skip Python docstring analysis.

    Returns:
        A fully graded DocRepoReport.
    """
    root = Path(project_root).resolve()
    if src_dirs is None:
        src_dirs = ["src/henchman"]

    # --- Load mkdocs config ---
    mkdocs_cfg = _load_yaml(root / "mkdocs.yml")
    docs_dir = mkdocs_cfg.get("docs_dir", "docs")
    nav_pages = _extract_nav_pages(mkdocs_cfg.get("nav", []))

    # --- Discover files ---
    markdown_files = _discover_markdown_files(root)
    python_sources: list[PythonSource] = []
    if not skip_docstrings:
        python_sources = _discover_python_sources(root, src_dirs, _PY_EXCLUDES)

    # --- Build scan context ---
    ctx = ScanContext(
        project_root=root,
        mkdocs_config=mkdocs_cfg,
        markdown_files=markdown_files,
        python_sources=python_sources,
        nav_pages=nav_pages,
        docs_dir=docs_dir,
    )

    # --- Run all detectors ---
    all_smells: list[DocSmellInstance] = []
    detectors = [cls() for cls in ALL_DETECTORS]
    if skip_docstrings:
        detectors = [d for d in detectors if d.name != "docstring_quality"]
    for detector in detectors:
        all_smells.extend(detector.detect(ctx))

    # --- Bucket smells by file ---
    smells_by_file: dict[str, list[DocSmellInstance]] = {}
    for smell in all_smells:
        smells_by_file.setdefault(smell.file, []).append(smell)

    # --- Build file reports ---
    file_reports: list[DocFileReport] = []

    # Markdown files.
    for md in markdown_files:
        report = DocFileReport(
            path=md.path,
            smells=smells_by_file.get(md.path, []),
            doc_metrics=_compute_md_metrics(md),
        )
        file_reports.append(report)

    # Python source files (only if they have smells or we're tracking metrics).
    if not skip_docstrings:
        for src in python_sources:
            smells = smells_by_file.get(src.path, [])
            metrics = _compute_source_metrics(src)
            if smells or metrics.total_public_apis > 0:
                report = DocFileReport(
                    path=src.path,
                    smells=smells,
                    source_metrics=metrics,
                )
                file_reports.append(report)

    # Add reports for files that only appear in smells (e.g. mkdocs.yml, pyproject.toml).
    reported_paths = {r.path for r in file_reports}
    for path, smells in smells_by_file.items():
        if path not in reported_paths:
            file_reports.append(DocFileReport(path=path, smells=smells))

    # --- Assemble and grade ---
    report = DocRepoReport(
        project_root=str(root),
        files=file_reports,
    )
    grade_repo(report)
    return report
