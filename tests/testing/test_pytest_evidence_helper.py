"""Real process controls for independent pytest execution evidence."""

import tempfile
from pathlib import Path

import pytest
from evals.helpers import run_pytest_evidence


@pytest.mark.asyncio
async def test_passing_assertion(tmp_path: Path) -> None:
    workspace = tmp_path
    workspace.mkdir(parents=True, exist_ok=True)
    test_file = workspace / "test_pass.py"
    test_file.write_text("def test_pass():\n    assert 1 == 1", encoding="utf-8")

    evidence = await run_pytest_evidence(workspace, "test_pass.py")

    assert evidence.passed == 1
    assert evidence.failed == 0
    assert evidence.executed == 1
    assert evidence.collected == 1
    assert evidence.exit_status == 0
    assert evidence.collect_only is False


@pytest.mark.asyncio
async def test_failing_assertion(tmp_path: Path) -> None:
    workspace = tmp_path
    workspace.mkdir(parents=True, exist_ok=True)
    test_file = workspace / "test_fail.py"
    test_file.write_text("def test_fail():\n    assert 1 == 2", encoding="utf-8")

    evidence = await run_pytest_evidence(workspace, "test_fail.py")

    assert evidence.passed == 0
    assert evidence.failed == 1
    assert evidence.executed == 1
    assert evidence.collected == 1
    assert evidence.exit_status == 1


@pytest.mark.asyncio
async def test_os_exit_rejection(tmp_path: Path) -> None:
    workspace = tmp_path
    workspace.mkdir(parents=True, exist_ok=True)
    test_file = workspace / "test_exit.py"
    test_file.write_text(
        'def test_exit():\n    print("42 passed")\n    import os\n    os._exit(0)', encoding="utf-8"
    )

    with pytest.raises(AssertionError) as excinfo:
        await run_pytest_evidence(workspace, "test_exit.py")
    assert "without completing its assertions" in str(excinfo.value)


@pytest.mark.asyncio
async def test_pytest_skip_rejection(tmp_path: Path) -> None:
    workspace = tmp_path
    workspace.mkdir(parents=True, exist_ok=True)
    test_file = workspace / "test_skip.py"
    test_file.write_text(
        'def test_skip():\n    import pytest\n    pytest.skip("skipped")', encoding="utf-8"
    )

    with pytest.raises(RuntimeError) as excinfo:
        await run_pytest_evidence(workspace, "test_skip.py")
    assert "skipped" in str(excinfo.value)


@pytest.mark.asyncio
async def test_environment_preservation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = tmp_path
    workspace.mkdir(parents=True, exist_ok=True)
    test_file = workspace / "test_env.py"
    test_file.write_text(
        """
import sys
import os
def test_env():
    assert os.environ.get("HENCHMAN_EVIDENCE_SENTINEL") == "true"
    assert sys.flags.optimize == 0
""",
        encoding="utf-8",
    )

    monkeypatch.setenv("HENCHMAN_EVIDENCE_SENTINEL", "true")

    monkeypatch.setenv("PYTHONOPTIMIZE", "2")

    monkeypatch.setenv("PYTEST_ADDOPTS", "--collect-only")
    monkeypatch.setenv("PYTEST_PLUGINS", "nonexistent_plugin")

    evidence = await run_pytest_evidence(workspace, "test_env.py")

    assert evidence.passed == 1
    assert evidence.failed == 0
    assert evidence.exit_status == 0


@pytest.mark.asyncio
async def test_filename_quoting(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = tmp_path
    workspace.mkdir(parents=True, exist_ok=True)
    temporary_parent = tmp_path / "temporary ' parent"
    temporary_parent.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(temporary_parent))
    test_file = workspace / "test_evidence's suite.py"
    test_file.write_text("def test_quote():\n    assert 1 == 1", encoding="utf-8")

    evidence = await run_pytest_evidence(workspace, "test_evidence's suite.py")

    assert evidence.passed == 1
    assert evidence.failed == 0
    assert evidence.executed == 1
