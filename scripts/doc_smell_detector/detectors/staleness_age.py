"""Detect documentation files that haven't been updated recently."""

from __future__ import annotations

from datetime import datetime, timezone

from scripts.doc_smell_detector.detectors.base import (
    DocSmellDetector,
    ScanContext,
)
from scripts.doc_smell_detector.models import (
    DocSmellInstance,
    DocSmellSeverity,
    DocSmellType,
)

# Thresholds in days.
_WARN_DAYS = 14  # 2 weeks  → MEDIUM
_HIGH_DAYS = 30  # 1 month    → HIGH
_CRITICAL_DAYS = 60  # 2 years   → CRITICAL

# If a source file was modified within this many days but its matching doc
# was not, flag the doc as likely out-of-date.
_SOURCE_DRIFT_DAYS = 90


def _days_since(dt: datetime) -> int:
    """Return the number of whole days between *dt* and now (UTC)."""
    now = datetime.now(timezone.utc)
    # Ensure *dt* is timezone-aware for comparison.
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return max(0, (now - dt).days)


def _severity_for_age(days: int) -> DocSmellSeverity | None:
    """Map age in days to a severity, or ``None`` if fresh enough."""
    if days >= _CRITICAL_DAYS:
        return DocSmellSeverity.CRITICAL
    if days >= _HIGH_DAYS:
        return DocSmellSeverity.HIGH
    if days >= _WARN_DAYS:
        return DocSmellSeverity.MEDIUM
    return None


class StalenessAgeDetector(DocSmellDetector):
    """Flag doc files that have not been modified for a long time.

    Also detects *source-doc drift* — when a Python source file has been
    modified recently but the corresponding documentation page has not.
    """

    @property
    def name(self) -> str:  # noqa: D401
        """Detector identifier."""
        return "staleness_age"

    def detect(self, ctx: ScanContext) -> list[DocSmellInstance]:
        """Run age-based staleness checks."""
        smells: list[DocSmellInstance] = []

        docs_dir = ctx.docs_dir  # e.g. "docs"

        # --- 1. Absolute-age check for every doc file ---
        for md in ctx.markdown_files:
            if not md.path.startswith(docs_dir + "/"):
                continue
            if md.last_modified is None:
                continue
            age_days = _days_since(md.last_modified)
            severity = _severity_for_age(age_days)
            if severity is not None:
                smells.append(
                    DocSmellInstance(
                        smell_type=DocSmellType.STALE_AGE,
                        severity=severity,
                        file=md.path,
                        line=1,
                        message=(
                            f"Doc file last modified {age_days} days ago"
                        ),
                        suggested_fix=(
                            "Review and update this documentation to "
                            "ensure it still reflects current behaviour."
                        ),
                    )
                )

        # --- 2. Source-doc drift check ---
        # Build a map of doc-stem → last_modified for quick lookup.
        doc_dates: dict[str, datetime] = {}
        for md in ctx.markdown_files:
            if not md.path.startswith(docs_dir + "/"):
                continue
            if md.last_modified is not None:
                # Key is the stem: "docs/tools.md" → "tools"
                stem = md.path.rsplit("/", 1)[-1].removesuffix(".md")
                doc_dates[stem] = md.last_modified

        for src in ctx.python_sources:
            if src.last_modified is None:
                continue
            src_age = _days_since(src.last_modified)
            if src_age > _SOURCE_DRIFT_DAYS:
                # Source itself is old — no drift signal.
                continue

            # Guess related doc pages by directory component.
            # e.g. "src/henchman/tools/builtins/grep.py" → stem "tools"
            parts = src.path.replace("\\", "/").split("/")
            candidate_stems: set[str] = set()
            for part in parts:
                clean = part.removesuffix(".py")
                if clean and clean not in {"src", "henchman", "__init__", "builtins"}:
                    candidate_stems.add(clean)

            for stem, doc_dt in doc_dates.items():
                if stem not in candidate_stems:
                    continue
                doc_age = _days_since(doc_dt)
                if doc_age > _SOURCE_DRIFT_DAYS and src_age <= _SOURCE_DRIFT_DAYS:
                    doc_path = next(
                        (
                            md.path
                            for md in ctx.markdown_files
                            if md.path.endswith(f"/{stem}.md")
                        ),
                        f"{docs_dir}/{stem}.md",
                    )
                    smells.append(
                        DocSmellInstance(
                            smell_type=DocSmellType.STALE_AGE,
                            severity=DocSmellSeverity.HIGH,
                            file=doc_path,
                            line=1,
                            message=(
                                f"Source '{src.path}' updated {src_age}d ago "
                                f"but doc last modified {doc_age}d ago"
                            ),
                            suggested_fix=(
                                f"Update '{doc_path}' to reflect recent "
                                f"changes in '{src.path}'."
                            ),
                        )
                    )

        return smells
