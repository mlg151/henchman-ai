"""Explicit pytest plugin recording evidence for the agent's verification tool.

Pytest's built-in JUnit XML omits collection-mode evidence and collection counts.
A separate report also preserves any project-configured JUnit artifact path.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PytestEvidence:
    """A completed pytest session, distinct from console text or process success."""

    collect_only: bool
    collected: int
    executed: int
    passed: int
    failed: int
    skipped: int
    exit_status: int

    @classmethod
    def load(cls, path: Path) -> PytestEvidence | None:
        """Read a valid report, returning no evidence for missing/invalid reports."""
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: object) -> PytestEvidence | None:
        """Validate an already-read report without reading its source again."""
        if not isinstance(data, dict) or data.get("version") != 1:
            return None
        if type(data.get("collect_only")) is not bool:
            return None
        counts = ("collected", "executed", "passed", "failed", "skipped", "exit_status")
        if any(type(data.get(name)) is not int or data[name] < 0 for name in counts):
            return None
        return cls(collect_only=data["collect_only"], **{name: data[name] for name in counts})


class _SessionReporter:
    """Aggregate test outcomes on the controller, including xdist reports."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.calls: set[str] = set()
        self.passed: set[str] = set()
        self.failed: set[str] = set()
        self.skipped: set[str] = set()

    def pytest_runtest_logreport(self, report: Any) -> None:
        """Count unique outcomes without mistaking setup success for execution."""
        if report.when == "call":
            self.calls.add(report.nodeid)
            if report.passed:
                self.passed.add(report.nodeid)
        if report.failed:
            self.failed.add(report.nodeid)
        if report.skipped:
            self.skipped.add(report.nodeid)

    def pytest_sessionfinish(self, session: Any, exitstatus: int) -> None:
        """Persist evidence only after a session reaches its finish hook."""
        payload = {
            "version": 1,
            "collect_only": bool(session.config.option.collectonly),
            "collected": session.testscollected,
            "executed": len(self.calls),
            "passed": len(self.passed - self.failed - self.skipped),
            "failed": len(self.failed),
            "skipped": len(self.skipped - self.failed),
            "exit_status": int(exitstatus),
        }
        self.path.write_text(json.dumps(payload), encoding="utf-8")


def pytest_addoption(parser: Any) -> None:
    """Register the report destination only when this plugin is explicitly loaded."""
    parser.addoption("--henchman-report", action="store", default=None)


def pytest_configure(config: Any) -> None:
    """Register one report writer; xdist workers forward reports to the controller."""
    path = config.getoption("--henchman-report")
    if path and not hasattr(config, "workerinput"):
        config.pluginmanager.register(_SessionReporter(Path(path)), "henchman-session-reporter")
