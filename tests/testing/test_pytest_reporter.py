"""Structured verification reports reject unavailable evidence and worker writes."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from henchman.testing.pytest_reporter import PytestEvidence, pytest_configure


@pytest.mark.parametrize("passed", [1, True, -1, "1"])
def test_bounded_payload_parser_preserves_report_validation(passed: object) -> None:
    payload = {
        "version": 1, "collect_only": False, "collected": 1,
        "executed": 1, "passed": passed, "failed": 0, "skipped": 0, "exit_status": 0,
    }
    evidence = PytestEvidence.from_dict(payload)
    if type(passed) is int and passed == 1:
        assert evidence == PytestEvidence(False, 1, 1, 1, 0, 0, 0)
    else:
        assert evidence is None


@pytest.mark.parametrize("text", [
    "not json", "[]", "{}", '{"version":2}',
    '{"version":1,"collect_only":"false"}',
])
def test_invalid_report_does_not_prove_execution(tmp_path, text):
    path = tmp_path / "report.json"
    path.write_text(text)
    assert PytestEvidence.load(path) is None


def test_missing_report_does_not_prove_execution(tmp_path):
    assert PytestEvidence.load(tmp_path / "missing.json") is None


def test_only_controller_writes_aggregated_outcomes(tmp_path):
    path = tmp_path / "report.json"
    manager = Mock()
    worker = SimpleNamespace(
        getoption=lambda _name: str(path), pluginmanager=manager, workerinput={},
    )
    pytest_configure(worker)
    manager.register.assert_not_called()

    controller = SimpleNamespace(getoption=lambda _name: str(path), pluginmanager=manager)
    pytest_configure(controller)
    reporter = manager.register.call_args.args[0]
    reporter.pytest_runtest_logreport(SimpleNamespace(
        nodeid="test_one", when="call", passed=True, failed=False, skipped=False,
    ))
    reporter.pytest_runtest_logreport(SimpleNamespace(
        nodeid="test_two", when="setup", passed=False, failed=False, skipped=True,
    ))
    reporter.pytest_runtest_logreport(SimpleNamespace(
        nodeid="test_one", when="teardown", passed=False, failed=True, skipped=False,
    ))
    session = SimpleNamespace(
        config=SimpleNamespace(option=SimpleNamespace(collectonly=False)), testscollected=2,
    )
    reporter.pytest_sessionfinish(session, exitstatus=1)

    assert PytestEvidence.load(path) == PytestEvidence(
        collect_only=False, collected=2, executed=1, passed=0, failed=1, skipped=1, exit_status=1,
    )
    assert json.loads(path.read_text())["version"] == 1
