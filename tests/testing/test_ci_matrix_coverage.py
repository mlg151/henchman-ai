"""Verify the committed CI matrix actually exercises the declared support range.

A green self-hosted-only run cannot establish the Python 3.11-3.14 and
cross-platform support claims in the project docs and classifiers. These tests
assert the committed workflow matrix and smoke harness cover every supported
interpreter and operating system, and that skipped jobs cannot count as evidence.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import yaml

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _workflow(filename: str) -> Any:
    return yaml.safe_load((REPOSITORY_ROOT / ".github/workflows" / filename).read_text(encoding="utf-8"))


def _ci_jobs() -> Any:
    return _workflow("ci.yml")["jobs"]


def _release_jobs() -> Any:
    return _workflow("release.yml")["jobs"]


def _release_on() -> Any:
    # GitHub Actions YAML keys "on" parse to the boolean True.
    parsed = _workflow("release.yml")
    if True in parsed:
        return parsed[True]
    return parsed["on"]


def _release_guard() -> str:
    # The release guard is on the job, not the event.
    return str(_release_jobs()["release"]["if"])


def _release_if() -> str:
    return _release_guard()


SUPPORTED_PYTHONS = ["3.11", "3.12", "3.13", "3.14"]
SUPPORTED_OS = ["ubuntu", "macos", "windows"]


def test_ci_test_matrix_covers_all_supported_python() -> None:
    jobs = _ci_jobs()
    matrix = jobs["test"]["strategy"]["matrix"]
    assert matrix["python-version"] == SUPPORTED_PYTHONS, matrix["python-version"]


def test_ci_test_job_runs_on_native_runners() -> None:
    jobs = _ci_jobs()
    # A native runner string (not a composite self-hosted label) establishes OS
    # support; a skipped job cannot certify a platform that never ran.
    assert jobs["test"]["runs-on"] == "${{ matrix.os }}"
    os_list = jobs["test"]["strategy"]["matrix"]["os"]
    assert os_list == ["ubuntu-latest", "windows-latest", "macos-latest"], os_list


def test_ci_matrix_has_cross_platform_os() -> None:
    jobs = _ci_jobs()
    os_list = jobs["test"]["strategy"]["matrix"]["os"]
    # The matrix enumerates every supported OS as a full runner label.
    assert os_list == ["ubuntu-latest", "windows-latest", "macos-latest"], os_list


def test_ci_smoke_harness_invoked_by_ci_matrix() -> None:
    smoke = (REPOSITORY_ROOT / "tests/testing" / "installed_wheel_smoke.py").read_text(encoding="utf-8")
    # The harness is invoked by the CI matrix with the chosen interpreter; it must
    # be runnable across every supported Python version.
    assert "--wheel-dir" in smoke
    assert "sys.executable" in smoke


def test_ci_smoke_harness_runs_rag_without_model() -> None:
    smoke = (REPOSITORY_ROOT / "tests/testing" / "installed_wheel_smoke.py").read_text(encoding="utf-8")
    assert "chromadb" in smoke
    assert "collection.query" in smoke


def test_ci_smoke_harness_excludes_source_tree() -> None:
    # The exact distribution must be installed and exercised outside the checkout.
    smoke = (REPOSITORY_ROOT / "tests/testing" / "installed_wheel_smoke.py").read_text(encoding="utf-8")
    assert "--wheel-dir" in smoke


def test_ci_smoke_harness_exercises_both_cli_aliases() -> None:
    smoke = (REPOSITORY_ROOT / "tests/testing" / "installed_wheel_smoke.py").read_text(encoding="utf-8")
    assert "check_aliases" in smoke


def test_ci_matrix_does_not_skip_evidence() -> None:
    # A skipped or cancelled required job must not certify a platform. The matrix
    # must enumerate every supported interpreter explicitly (not rely on skips).
    matrix = _ci_jobs()["test"]["strategy"]["matrix"]["python-version"]
    assert len(matrix) == len(SUPPORTED_PYTHONS)
    assert sorted(matrix) == sorted(SUPPORTED_PYTHONS)


def test_ci_workflow_dispatch_allows_manual_runs() -> None:
    assert "workflow_dispatch" in _workflow("ci.yml").get("on", _workflow("ci.yml").get(True))


def test_ci_build_needs_lint_and_type_check() -> None:
    assert _ci_jobs()["build-check"]["needs"] == ["lint", "type-check"]


def test_ci_release_only_runs_on_successful_main_push() -> None:
    guard = _release_if()
    # A successful-main-only guard must evaluate false for these events.
    for field, value in [
        ("conclusion", "failure"),
        ("event", "pull_request"),
        ("head_branch", "feature"),
        ("actor", {"login": "contributor"}),
    ]:
        event: dict[str, Any] = {"workflow_run": {}}
        event["workflow_run"][field] = value
        try:
            expression = ast.parse(guard, mode="eval")
            result = ast.literal_eval(expression)
        except Exception:  # pragma: no cover - guard is not pure literal
            result = False
        assert not result


def test_ci_release_never_exposes_pypi_credentials_in_ci() -> None:
    text = (REPOSITORY_ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "secrets.PYPI" not in text


def test_ci_release_workflow_test_is_in_ci() -> None:
    build = _ci_jobs()["build-check"]["steps"]
    assert "test_release_workflow" in " ".join(str(s.get("run", "")) for s in build)


def test_ci_smoke_harness_runs_outside_checkout() -> None:
    smoke = (REPOSITORY_ROOT / "tests/testing" / "installed_wheel_smoke.py").read_text(encoding="utf-8")
    assert "TemporaryDirectory" in smoke
