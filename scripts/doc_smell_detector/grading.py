"""Grading rubric for documentation smell reports.

Converts raw smell counts + severity into A-F grades, with docstring
coverage as a weighting factor (analogous to MI in the code smell grader).
"""

from __future__ import annotations

from scripts.doc_smell_detector.models import (
    SEVERITY_PENALTY,
    DocFileReport,
    DocRepoReport,
    DocRepoSummary,
    DocSmellSeverity,
)

# Grade boundaries (score -> letter).
GRADE_BOUNDARIES: list[tuple[float, str]] = [
    (90.0, "A"),
    (80.0, "B"),
    (70.0, "C"),
    (60.0, "D"),
    (0.0, "F"),
]

# Weight of docstring coverage vs smell-based score in overall grade.
DOCSTRING_COVERAGE_WEIGHT = 0.20
SMELL_WEIGHT = 0.80


def _letter_grade(score: float) -> str:
    """Map a 0-100 score to a letter grade."""
    for threshold, letter in GRADE_BOUNDARIES:
        if score >= threshold:
            return letter
    return "F"


def grade_file(report: DocFileReport) -> None:
    """Compute and set grade + score on a DocFileReport (mutates in place)."""
    smell_score = 100.0
    for smell in report.smells:
        penalty = SEVERITY_PENALTY.get(smell.severity, 2)
        smell_score -= penalty
    smell_score = max(0.0, smell_score)

    report.score = round(smell_score, 1)
    report.grade = _letter_grade(report.score)


def grade_repo(report: DocRepoReport) -> None:
    """Compute overall grade and summary statistics (mutates in place)."""
    # Grade each file.
    for fr in report.files:
        grade_file(fr)

    # Aggregate summary.
    summary = DocRepoSummary()

    doc_files = [
        fr for fr in report.files
        if fr.path.endswith(".md") or fr.path.endswith(".yml")
    ]
    source_files = [
        fr for fr in report.files
        if fr.source_metrics is not None
    ]

    summary.total_doc_files = len(doc_files)
    summary.total_source_files_checked = len(source_files)
    summary.total_smells = sum(len(fr.smells) for fr in report.files)

    # Smells by type.
    by_type: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    for fr in report.files:
        for smell in fr.smells:
            by_type[smell.smell_type.value] = (
                by_type.get(smell.smell_type.value, 0) + 1
            )
            by_severity[smell.severity.value] = (
                by_severity.get(smell.severity.value, 0) + 1
            )
    summary.smells_by_type = dict(sorted(by_type.items(), key=lambda x: -x[1]))
    summary.smells_by_severity = dict(
        sorted(by_severity.items(), key=lambda x: -x[1]),
    )

    # Docstring coverage.
    total_apis = sum(
        fr.source_metrics.total_public_apis
        for fr in source_files
        if fr.source_metrics
    )
    documented_apis = sum(
        fr.source_metrics.documented_apis
        for fr in source_files
        if fr.source_metrics
    )
    summary.docstring_coverage_pct = (
        round(100.0 * documented_apis / total_apis, 1) if total_apis else 100.0
    )

    report.summary = summary

    # Overall score: weighted average of smell scores plus docstring coverage factor.
    all_files_with_smells = [fr for fr in report.files if fr.smells]
    all_files = report.files

    if all_files:
        # Simple average of file scores, weighted by importance:
        # - doc files weighted 2x (affect all users)
        # - source files weighted 1x (individual API docs)
        total_weight = 0.0
        weighted_score = 0.0
        for fr in all_files:
            w = 2.0 if fr.path.endswith(".md") or fr.path.endswith(".yml") else 1.0
            weighted_score += fr.score * w
            total_weight += w
        smell_avg = weighted_score / total_weight if total_weight else 100.0
    else:
        smell_avg = 100.0

    # Blend smell score with docstring coverage.
    docstring_score = summary.docstring_coverage_pct
    report.overall_score = round(
        SMELL_WEIGHT * smell_avg + DOCSTRING_COVERAGE_WEIGHT * docstring_score,
        1,
    )
    report.overall_grade = _letter_grade(report.overall_score)
