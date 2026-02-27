"""CLI entry point: python -m scripts.doc_smell_detector <project_root>."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from scripts.doc_smell_detector.formatter import format_json, format_markdown
from scripts.doc_smell_detector.scanner import scan_docs


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="doc_smell_detector",
        description=(
            "XP Documentation Smell Detector — scans a project's "
            "documentation for common smells and outputs a graded "
            "Markdown report."
        ),
    )
    parser.add_argument(
        "project_root",
        nargs="?",
        default=".",
        help="Project root directory (default: current directory).",
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        help=(
            "Output file path. If omitted, writes to stdout. "
            "Example: .agent_tasks/auto-doc-improve/doc-smell-report.md"
        ),
    )
    parser.add_argument(
        "-f", "--format",
        choices=["md", "json"],
        default="md",
        help="Output format (default: md).",
    )
    parser.add_argument(
        "--src-dirs",
        nargs="+",
        default=None,
        help=(
            "Python source directories to scan for docstrings. "
            "Defaults to src/henchman."
        ),
    )
    parser.add_argument(
        "--skip-docstrings",
        action="store_true",
        help="Skip Python docstring analysis (faster, docs-only).",
    )
    parser.add_argument(
        "--min-grade",
        choices=["A", "B", "C", "D", "F"],
        default=None,
        help="Only include files with this grade or worse.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the doc smell detector and write the report."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    root = Path(args.project_root)
    if not root.is_dir():
        print(f"Error: '{args.project_root}' is not a directory.", file=sys.stderr)
        return 1

    # Scan and grade.
    report = scan_docs(
        project_root=args.project_root,
        src_dirs=args.src_dirs,
        skip_docstrings=args.skip_docstrings,
    )

    # Filter by grade if requested.
    if args.min_grade:
        grade_order = {"F": 0, "D": 1, "C": 2, "B": 3, "A": 4}
        threshold = grade_order.get(args.min_grade, 0)
        report.files = [
            fr for fr in report.files
            if grade_order.get(fr.grade, 4) <= threshold
        ]

    # Format output.
    if args.format == "json":
        output = format_json(report)
    else:
        output = format_markdown(report)

    # Write output.
    if args.output:
        outpath = Path(args.output)
        outpath.parent.mkdir(parents=True, exist_ok=True)
        outpath.write_text(output, encoding="utf-8")
        print(f"Report written to {args.output}", file=sys.stderr)
    else:
        print(output)

    return 0


if __name__ == "__main__":
    sys.exit(main())
