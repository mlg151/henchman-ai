"""Render a DocRepoReport as Markdown or JSON, optimised for LLM consumption."""

from __future__ import annotations

from scripts.doc_smell_detector.models import (
    DocFileReport,
    DocRepoReport,
    DocSmellInstance,
    DocSmellSeverity,
)

# Severity badge for visual scanning.
SEVERITY_BADGE: dict[DocSmellSeverity, str] = {
    DocSmellSeverity.CRITICAL: "🔴 CRITICAL",
    DocSmellSeverity.HIGH: "🟠 HIGH",
    DocSmellSeverity.MEDIUM: "🟡 MEDIUM",
    DocSmellSeverity.LOW: "🟢 LOW",
}

GRADE_EMOJI: dict[str, str] = {
    "A": "✅",
    "B": "👍",
    "C": "⚠️",
    "D": "🔶",
    "F": "❌",
}


def _grade_badge(grade: str) -> str:
    return f"{GRADE_EMOJI.get(grade, '❓')} {grade}"


def _severity_rank(severity: DocSmellSeverity) -> int:
    return {
        DocSmellSeverity.CRITICAL: 4,
        DocSmellSeverity.HIGH: 3,
        DocSmellSeverity.MEDIUM: 2,
        DocSmellSeverity.LOW: 1,
    }.get(severity, 0)


def _smell_table(smells: list[DocSmellInstance]) -> str:
    """Render a list of smells as a Markdown table."""
    if not smells:
        return "_No smells detected._\n"

    lines = [
        "| Line | Severity | Type | Message | Suggested Fix |",
        "|-----:|:---------|:-----|:--------|:--------------|",
    ]
    for s in sorted(smells, key=lambda x: (-_severity_rank(x.severity), x.line)):
        sev = SEVERITY_BADGE.get(s.severity, s.severity.value)
        lines.append(
            f"| {s.line} | {sev} | {s.smell_type.value} | "
            f"{s.message} | {s.suggested_fix} |",
        )
    return "\n".join(lines) + "\n"


def _top_smelliest_files(report: DocRepoReport, n: int = 15) -> list[DocFileReport]:
    """Return the *n* files with the lowest scores."""
    return sorted(report.files, key=lambda f: f.score)[:n]


def _prioritised_fix_queue(
    report: DocRepoReport, n: int = 20,
) -> list[DocSmellInstance]:
    """Return the top *n* highest-impact smells to fix first."""
    all_smells: list[DocSmellInstance] = []
    for fr in report.files:
        all_smells.extend(fr.smells)
    return sorted(
        all_smells,
        key=lambda s: (-_severity_rank(s.severity), s.file, s.line),
    )[:n]


# ---------------------------------------------------------------------------
# Main formatting function
# ---------------------------------------------------------------------------


def format_markdown(report: DocRepoReport) -> str:
    """Render a full Markdown report from *report*."""
    sections: list[str] = []

    # --- Title ---
    sections.append(
        f"# Documentation Smell Report — {_grade_badge(report.overall_grade)} "
        f"(Score: {report.overall_score}/100)\n",
    )
    sections.append(f"_Project: {report.project_root}_  ")
    sections.append(f"_Generated: {report.timestamp}_\n")

    # --- Executive Summary ---
    s = report.summary
    sections.append("## Executive Summary\n")
    sections.append("| Metric | Value |")
    sections.append("|:-------|------:|")
    sections.append(f"| **Overall Grade** | {_grade_badge(report.overall_grade)} |")
    sections.append(f"| **Overall Score** | {report.overall_score}/100 |")
    sections.append(f"| **Doc Files Scanned** | {s.total_doc_files} |")
    sections.append(f"| **Source Files Checked** | {s.total_source_files_checked} |")
    sections.append(f"| **Total Smells** | {s.total_smells} |")
    sections.append(f"| **Docstring Coverage** | {s.docstring_coverage_pct}% |")
    sections.append("")

    # Smells by severity.
    if s.smells_by_severity:
        sections.append("### Smells by Severity\n")
        sections.append("| Severity | Count |")
        sections.append("|:---------|------:|")
        for sev, count in s.smells_by_severity.items():
            sections.append(f"| {sev} | {count} |")
        sections.append("")

    # Smells by type.
    if s.smells_by_type:
        sections.append("### Smells by Category\n")
        sections.append("| Category | Count |")
        sections.append("|:---------|------:|")
        for typ, count in s.smells_by_type.items():
            sections.append(f"| {typ} | {count} |")
        sections.append("")

    # --- Prioritised Fix Queue ---
    queue = _prioritised_fix_queue(report)
    if queue:
        sections.append("## 🎯 Prioritised Fix Queue\n")
        sections.append(
            "These are the highest-impact documentation smells to address first:\n",
        )
        for i, smell in enumerate(queue, 1):
            sev = SEVERITY_BADGE.get(smell.severity, smell.severity.value)
            sections.append(
                f"{i}. **{smell.file}:{smell.line}** — {sev} — "
                f"{smell.smell_type.value}  \n"
                f"   {smell.message}  \n"
                f"   → _{smell.suggested_fix}_\n",
            )
        sections.append("")

    # --- Files Ranked by Quality ---
    worst = _top_smelliest_files(report)
    if worst:
        sections.append("## 📊 Files Ranked by Quality\n")
        sections.append(
            "| Rank | File | Grade | Score | Smells | Last Modified |",
        )
        sections.append(
            "|-----:|:-----|:------|------:|-------:|:-------------|",
        )
        for i, fr in enumerate(worst, 1):
            lm = (
                fr.last_modified.strftime("%Y-%m-%d")
                if fr.last_modified
                else "—"
            )
            sections.append(
                f"| {i} | {fr.path} | {_grade_badge(fr.grade)} | "
                f"{fr.score} | {len(fr.smells)} | {lm} |",
            )
        sections.append("")

    # --- Per-File Details ---
    MAX_DETAIL_FILES = 25
    MAX_SMELLS_PER_FILE = 15
    files_with_smells = [
        fr for fr in report.files if fr.smells or fr.grade in ("D", "F")
    ]
    files_with_smells.sort(key=lambda f: f.score)
    files_with_smells = files_with_smells[:MAX_DETAIL_FILES]

    if files_with_smells:
        sections.append("## 📁 Per-File Details\n")
        if len(report.files) > MAX_DETAIL_FILES:
            sections.append(
                f"_Showing {MAX_DETAIL_FILES} worst files. "
                f"{len(report.files) - MAX_DETAIL_FILES} additional files omitted._\n",
            )
        for fr in files_with_smells:
            lm_str = (
                f" (last modified {fr.last_modified.strftime('%Y-%m-%d')})"
                if fr.last_modified
                else ""
            )
            sections.append(
                f"### {fr.path} — {_grade_badge(fr.grade)} ({fr.score}/100){lm_str}\n",
            )
            # Show metrics if available.
            if fr.doc_metrics:
                m = fr.doc_metrics
                sections.append(
                    f"Words: {m.word_count} | "
                    f"Headings: {m.heading_count} | "
                    f"Links: {m.link_count} | "
                    f"Code blocks: {m.code_block_count}\n",
                )
            if fr.source_metrics:
                sm = fr.source_metrics
                coverage = (
                    round(100.0 * sm.documented_apis / sm.total_public_apis, 0)
                    if sm.total_public_apis
                    else 100
                )
                sections.append(
                    f"Public APIs: {sm.total_public_apis} | "
                    f"Documented: {sm.documented_apis} | "
                    f"Coverage: {coverage}%\n",
                )

            display_smells = sorted(
                fr.smells,
                key=lambda x: (-_severity_rank(x.severity), x.line),
            )[:MAX_SMELLS_PER_FILE]
            sections.append(_smell_table(display_smells))
            if len(fr.smells) > MAX_SMELLS_PER_FILE:
                sections.append(
                    f"_... and {len(fr.smells) - MAX_SMELLS_PER_FILE} more smells._\n",
                )

    # --- Clean Files ---
    clean_files = [
        fr for fr in report.files
        if not fr.smells and fr.grade not in ("D", "F")
    ]
    if clean_files:
        sections.append(
            f"## ✨ Clean Files ({len(clean_files)} files with no smells)\n",
        )
        sections.append(
            "<details><summary>Click to expand</summary>\n",
        )
        for fr in clean_files:
            sections.append(f"- {fr.path} — {_grade_badge(fr.grade)}")
        sections.append("\n</details>\n")

    # --- Footer ---
    sections.append("---\n")
    sections.append(
        "_Report generated by XP Documentation Smell Detector. "
        "Smells are static heuristics — use judgement when prioritising fixes._\n",
    )

    return "\n".join(sections)


def format_json(report: DocRepoReport) -> str:
    """Render the report as JSON."""
    import json
    from dataclasses import asdict

    def _serialise(obj: object) -> object:
        if hasattr(obj, "value"):
            return obj.value
        if hasattr(obj, "isoformat"):
            return obj.isoformat()  # type: ignore[union-attr]
        raise TypeError(f"Cannot serialise {type(obj)}")

    return json.dumps(asdict(report), default=_serialise, indent=2)
