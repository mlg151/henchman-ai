"""Bounded, dependency-free source scanning for actionable quality candidates."""

from __future__ import annotations

import ast
import io
import tokenize
from collections.abc import Iterator
from dataclasses import asdict, dataclass, field
from pathlib import Path
from threading import Event

from henchman.analysis.smells.deep_nesting import DeepNestingDetector
from henchman.analysis.smells.duplicates import DuplicateIndex
from henchman.analysis.smells.long_method import LongMethodDetector
from henchman.analysis.smells.models import SmellInstance
from henchman.utils.source_files import EXCLUDED_DIRECTORIES, MAX_ENTRIES
from henchman.utils.source_files import _iter_python_files as _walk_python_files

MAX_FILE_BYTES = 1024 * 1024
MAX_TOTAL_BYTES = 10 * 1024 * 1024
MAX_ERRORS = 20
LIMITATIONS = (
    "Findings are review candidates, not proof of incorrect code or semantic equivalence.",
    "Duplicate fingerprints preserve identifiers, literals and call targets; renamed or partial clones may be missed.",
    "Long-method size measures physical body lines, including comments, blank lines and nested definitions.",
    "Only Python source is analyzed; no code is imported or executed. No lint, type or test gate is run.",
    "Dependency/cache directories and child symlinks are excluded; .gitignore is not interpreted.",
)


@dataclass(frozen=True)
class ScanOptions:
    """Caller-adjustable output and file budgets within hard resource ceilings."""

    max_files: int = 500
    max_findings: int = 100

    def __post_init__(self) -> None:
        for name, ceiling in (("max_files", 5000), ("max_findings", 500)):
            value = getattr(self, name)
            if type(value) is not int or not 1 <= value <= ceiling:
                raise ValueError(f"{name} must be an integer between 1 and {ceiling}")


@dataclass
class ScanReport:
    """Coverage and observations; failed or bounded scans never imply cleanliness."""

    options: ScanOptions
    files_examined: int = 0
    files_analyzed: int = 0
    bytes_read: int = 0
    entries_seen: int = 0
    skipped_symlinks: int = 0
    truncated: bool = False
    findings: list[SmellInstance] = field(default_factory=list)
    errors: list[dict[str, str]] = field(default_factory=list)

    @property
    def complete(self) -> bool:
        """Whether the selected scope was analyzed without errors or truncation."""
        return not self.errors and not self.truncated

    def error(self, path: Path, message: str) -> None:
        """Record bounded diagnostics for unreadable or unanalyzable paths."""
        if len(self.errors) < MAX_ERRORS:
            self.errors.append({"file": str(path), "message": message})
        if len(self.errors) >= MAX_ERRORS:
            self.truncated = True

    def add_findings(self, findings: list[SmellInstance]) -> None:
        """Retain at most the requested number of findings with explicit overflow."""
        remaining = self.options.max_findings - len(self.findings)
        self.findings.extend(findings[:remaining])
        if len(findings) > remaining:
            self.truncated = True

    def to_dict(self) -> dict[str, object]:
        """Produce a JSON-compatible report without unsupported quality grades."""
        findings = []
        for finding in self.findings:
            item = asdict(finding)
            item["smell_type"] = finding.smell_type.value
            item["severity"] = finding.severity.value
            findings.append(item)
        return {
            "complete": self.complete,
            "truncated": self.truncated,
            "files_examined": self.files_examined,
            "files_analyzed": self.files_analyzed,
            "bytes_read": self.bytes_read,
            "entries_seen": self.entries_seen,
            "skipped_symlinks": self.skipped_symlinks,
            "findings": findings,
            "errors": self.errors,
            "limits": {
                **asdict(self.options),
                "max_file_bytes": MAX_FILE_BYTES,
                "max_total_bytes": MAX_TOTAL_BYTES,
                "max_entries": MAX_ENTRIES,
            },
            "excluded_directories": sorted(EXCLUDED_DIRECTORIES),
            "limitations": list(LIMITATIONS),
        }


def _python_files(root: Path, report: ScanReport, stop: Event) -> Iterator[Path]:
    """Retain the scanner's entry budget while sharing source traversal."""
    yield from _walk_python_files(root, report, stop, max_entries=MAX_ENTRIES)


def _read_tree(path: Path, report: ScanReport) -> tuple[ast.Module, str] | None:
    """Respect Python encoding declarations while bounding raw bytes before parse."""
    try:
        remaining = MAX_TOTAL_BYTES - report.bytes_read
        if remaining <= 0:
            report.truncated = True
            report.error(path, "Total source byte budget exceeded")
            return None
        with path.open("rb") as stream:
            raw = stream.read(min(MAX_FILE_BYTES, remaining) + 1)
        report.bytes_read += len(raw)
        if report.bytes_read > MAX_TOTAL_BYTES:
            report.truncated = True
            report.error(path, "Total source byte budget exceeded")
            return None
        if len(raw) > MAX_FILE_BYTES:
            report.error(path, "File byte budget exceeded")
            return None
        encoding, _ = tokenize.detect_encoding(io.BytesIO(raw).readline)
        source = raw.decode(encoding)
        return ast.parse(source, filename=str(path)), source
    except (OSError, SyntaxError, UnicodeError, LookupError, ValueError, RecursionError) as exc:
        report.error(path, str(exc))
        return None


def scan_quality(path: str, options: ScanOptions, stop: Event | None = None) -> ScanReport:
    """Analyze one bounded source at a time, retaining only findings and hashes."""
    report = ScanReport(options)
    stopped = stop if stop is not None else Event()
    index = DuplicateIndex()
    detectors = (LongMethodDetector(), DeepNestingDetector())
    try:
        root = Path(path).resolve(strict=True)
    except (OSError, RuntimeError, ValueError) as exc:
        report.error(Path(path), str(exc))
        return report
    for source_path in _python_files(root, report, stopped):
        if stopped.is_set():
            break
        if report.files_examined >= options.max_files:
            report.truncated = True
            break
        report.files_examined += 1
        parsed = _read_tree(source_path, report)
        if parsed is not None:
            tree, source = parsed
            try:
                for detector in detectors:
                    report.add_findings(detector.detect(tree, source, str(source_path)))
                report.add_findings(index.add(tree, source, str(source_path)))
                report.files_analyzed += 1
            except RecursionError as exc:
                report.error(source_path, f"AST analysis exceeded recursion limit: {exc}")
        if report.truncated:
            break
    if stopped.is_set():
        report.truncated = True
    return report
