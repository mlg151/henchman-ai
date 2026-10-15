"""Acceptance checks establish bounded observations, never whole-task truth."""

import dataclasses
import sys
from pathlib import Path
from typing import Any, cast

import pytest

from henchman.advanced.acceptance_checks import (
    CheckSpec,
    parse_checks,
    prepare_checks,
    run_checks,
)
from henchman.testing.pytest_reporter import PytestEvidence
from henchman.tools.subprocess_utils import run_bounded_subprocess


def _results(report: dict[str, object]) -> list[dict[str, Any]]:
    results = report["results"]
    assert isinstance(results, list)
    assert all(isinstance(result, dict) for result in results)
    return cast("list[dict[str, Any]]", results)


async def test_advanced_package_imports_without_builtin_import_cycle(
    tmp_path: Path,
) -> None:
    result = await run_bounded_subprocess(
        [sys.executable, "-c", "import henchman.advanced; print('imported')"],
        cwd=tmp_path,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr.decode()
    assert "imported" in result.stdout.decode()


@pytest.mark.parametrize(
    "raw",
    [
        None,
        {},
        [],
        [{"kind": "unknown"}],
        [{"kind": "file_exists", "path": "../outside"}],
        [{"kind": "file_exists", "path": "/outside"}],
        [{"kind": "file_exists", "path": "C:\\outside"}],
        [{"kind": "file_exists", "path": "file", "source": "user"}],
        [{"kind": "file_changed", "path": "file", "baseline_sha256": "0" * 64}],
        [{"kind": "command", "argv": ["echo"], "timeout": True}],
        [{"kind": "command", "argv": ["echo"], "expected_exit": False}],
        [{"kind": "command", "argv": ["echo"], "timeout": 301}],
        [{"kind": "command", "argv": ["echo"] * 65}],
        [{"kind": "command", "argv": ["echo", "x" * 16384]}],
        [{"kind": "file_contains", "path": "a.py", "text": "x" * 4097}],
        [{"kind": "pytest", "path": "--collect-only"}],
        [{"kind": "pytest", "path": "tests", "collect_only": True}],
        [{"kind": "file_exists", "path": "file"}] * 21,
    ],
)
def test_invalid_or_untrusted_specs_are_rejected(raw: object) -> None:
    with pytest.raises(ValueError):
        parse_checks(raw)


def test_specs_are_immutable_and_baselines_round_trip(tmp_path: Path) -> None:
    target = tmp_path / "module.py"
    target.write_text("before", encoding="utf-8")
    spec = prepare_checks(
        tmp_path,
        parse_checks(
            [
                {"kind": "file_changed", "path": "module.py"},
            ]
        ),
    )[0]
    assert CheckSpec.from_dict(spec.to_dict()) == spec
    assert spec.baseline_sha256 is not None
    with pytest.raises(dataclasses.FrozenInstanceError):
        spec.path = "other.py"  # type: ignore[misc]
    with pytest.raises(ValueError):
        parse_checks([spec.to_dict()])


async def test_changes_require_captured_baseline_and_final_file(tmp_path: Path) -> None:
    raw = parse_checks([{"kind": "file_changed", "path": "new.py"}])
    assert not (await run_checks(tmp_path, raw))["checks_passed"]
    prepared = prepare_checks(tmp_path, raw)
    assert not (await run_checks(tmp_path, prepared))["checks_passed"]
    path = tmp_path / "new.py"
    path.write_text("value = 1", encoding="utf-8")
    result = await run_checks(tmp_path, prepared)
    assert result["checks_passed"] is True
    assert result["task_verified"] is False
    assert isinstance(result["spec_digest"], str)
    assert len(result["spec_digest"]) == 64
    assert result["checked_at"]
    baseline = prepare_checks(tmp_path, raw)
    assert not (await run_checks(tmp_path, baseline))["checks_passed"]
    path.write_text("value = 2", encoding="utf-8")
    assert (await run_checks(tmp_path, baseline))["checks_passed"]
    path.unlink()
    assert not (await run_checks(tmp_path, baseline))["checks_passed"]


async def test_reverification_uses_current_content(tmp_path: Path) -> None:
    target = tmp_path / "a.py"
    target.write_text("def useful(): pass", encoding="utf-8")
    specs = parse_checks(
        [
            {"kind": "file_exists", "path": "a.py"},
            {"kind": "file_contains", "path": "a.py", "text": "def useful"},
        ]
    )
    initial = await run_checks(tmp_path, specs)
    assert initial["checks_passed"]
    target.write_text("# removed", encoding="utf-8")
    current = await run_checks(tmp_path, specs)
    assert not current["checks_passed"]
    assert current["spec_digest"] == initial["spec_digest"]


@pytest.mark.parametrize("data", [b"x" * (1024 * 1024 + 1), b"\xff"])
async def test_unreadable_content_cannot_pass(tmp_path: Path, data: bytes) -> None:
    (tmp_path / "a.py").write_bytes(data)
    report = await run_checks(
        tmp_path,
        parse_checks(
            [
                {"kind": "file_contains", "path": "a.py", "text": "x"},
            ]
        ),
    )
    assert not report["checks_passed"]
    assert _results(report)[0]["error"]


async def test_oversized_baseline_cannot_be_treated_as_missing(tmp_path: Path) -> None:
    target = tmp_path / "a.py"
    target.write_bytes(b"x" * (1024 * 1024 + 1))
    specs = prepare_checks(
        tmp_path,
        parse_checks(
            [
                {"kind": "file_changed", "path": "a.py"},
            ]
        ),
    )
    target.write_text("now small", encoding="utf-8")
    report = await run_checks(tmp_path, specs)
    assert not report["checks_passed"]
    assert _results(report)[0]["error"]


async def test_symlink_escape_is_rejected_again_at_execution(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    outside = tmp_path / "outside.py"
    outside.write_text("secret", encoding="utf-8")
    target = root / "a.py"
    target.write_text("before", encoding="utf-8")
    specs = prepare_checks(
        root,
        parse_checks(
            [
                {"kind": "file_changed", "path": "a.py"},
            ]
        ),
    )
    target.unlink()
    try:
        target.symlink_to(outside)
    except OSError:
        pytest.skip("Host cannot create symlinks")
    report = await run_checks(root, specs)
    assert not report["checks_passed"]
    assert "escape" in _results(report)[0]["error"].lower()


async def test_commands_use_literal_argv_cwd_and_exit_status(tmp_path: Path) -> None:
    literal = "$(touch fabricated); echo false"
    specs = parse_checks(
        [
            {
                "kind": "command",
                "argv": [
                    sys.executable,
                    "-c",
                    "import os,sys; print(os.getcwd()); print(sys.argv[1])",
                    literal,
                ],
            },
            {"kind": "command", "argv": [sys.executable, "-c", "raise SystemExit(3)"]},
            {
                "kind": "command",
                "argv": [sys.executable, "-c", "raise SystemExit(3)"],
                "expected_exit": 3,
            },
        ]
    )
    report = await run_checks(tmp_path, specs)
    results = _results(report)
    assert not report["checks_passed"]
    assert results[0]["passed"]
    assert str(tmp_path) in results[0]["stdout"]
    assert literal in results[0]["stdout"]
    assert not (tmp_path / "fabricated").exists()
    assert not results[1]["passed"]
    assert results[2]["passed"]


async def test_command_output_and_time_are_bounded(tmp_path: Path) -> None:
    report = await run_checks(
        tmp_path,
        parse_checks(
            [
                {
                    "kind": "command",
                    "argv": [sys.executable, "-c", "print('x' * 200000)"],
                },
                {
                    "kind": "command",
                    "argv": [sys.executable, "-c", "import time; time.sleep(30)"],
                    "timeout": 1,
                },
            ]
        ),
    )
    results = _results(report)
    assert results[0]["passed"]
    assert results[0]["stdout_truncated"]
    assert len(results[0]["stdout"].encode()) <= 65536
    assert not results[1]["passed"]
    assert "time" in results[1]["error"].lower()


@pytest.mark.parametrize("mode", ["pass", "skip", "collect"])
async def test_pytest_requires_executed_passing_tests(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
) -> None:
    source = "def test_actual():\n    assert True\n"
    if mode == "skip":
        source = "import pytest\n@pytest.mark.skip(reason='not executed')\n" + source
    if mode == "collect":
        monkeypatch.setenv("PYTEST_ADDOPTS", "--collect-only")
    else:
        monkeypatch.delenv("PYTEST_ADDOPTS", raising=False)
    (tmp_path / "test_actual.py").write_text(source, encoding="utf-8")
    report = await run_checks(
        tmp_path,
        parse_checks(
            [
                {"kind": "pytest", "path": "test_actual.py"},
            ]
        ),
    )
    assert report["checks_passed"] is (mode == "pass")
    assert report["task_verified"] is False
    assert _results(report)[0]["evidence"] is not None


@pytest.mark.parametrize("oversized_report", [False, True])
async def test_pytest_console_claims_without_valid_report_fail(
    tmp_path: Path,
    oversized_report: bool,
) -> None:
    # A local module shadows pytest and exits successfully without executing tests.
    source = "print('100 passed')\n"
    if oversized_report:
        source += (
            "import pathlib, sys\n"
            "report = pathlib.Path(sys.argv[sys.argv.index('--henchman-report') + 1])\n"
            "report.write_text('x' * (1024 * 1024 + 1))\n"
        )
    (tmp_path / "pytest.py").write_text(source, encoding="utf-8")
    report = await run_checks(
        tmp_path,
        parse_checks(
            [
                {"kind": "pytest", "path": "test_actual.py"},
            ]
        ),
    )
    assert not report["checks_passed"]
    assert _results(report)[0]["error"]


async def test_directory_does_not_satisfy_file_exists(tmp_path: Path) -> None:
    (tmp_path / "folder").mkdir()
    report = await run_checks(
        tmp_path,
        parse_checks(
            [
                {"kind": "file_exists", "path": "folder"},
            ]
        ),
    )
    assert not report["checks_passed"]
    assert "regular file" in _results(report)[0]["error"]


async def test_pytest_report_is_not_read_again_without_a_bound(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden_load(_path: Path) -> None:
        raise AssertionError("do not reread a potentially changing report unbounded")

    monkeypatch.setattr(PytestEvidence, "load", forbidden_load)
    monkeypatch.delenv("PYTEST_ADDOPTS", raising=False)
    (tmp_path / "test_actual.py").write_text(
        "def test_actual():\n    assert True\n",
        encoding="utf-8",
    )
    report = await run_checks(
        tmp_path,
        parse_checks(
            [
                {"kind": "pytest", "path": "test_actual.py"},
            ]
        ),
    )
    assert report["checks_passed"]


async def test_python312_symlink_cycle_is_reported_as_a_failed_check(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resolve = Path.resolve

    def legacy_resolve(path: Path, strict: bool = False) -> Path:
        if path.name == "cycle":
            raise RuntimeError("Symlink loop")
        return resolve(path, strict=strict)

    monkeypatch.setattr(Path, "resolve", legacy_resolve)
    report = await run_checks(
        tmp_path,
        parse_checks(
            [
                {"kind": "file_exists", "path": "cycle"},
            ]
        ),
    )
    assert not report["checks_passed"]
    assert "resolve" in _results(report)[0]["error"]
