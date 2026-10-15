"""Validate portable wheel smoke staging without installing or launching subprocesses."""

from pathlib import Path

import pytest
from tests.testing.installed_wheel_smoke import find_wheel, smoke_environment, stage_workflow_tests


def test_find_wheel_requires_one_unambiguous_artifact(tmp_path):
    with pytest.raises(ValueError, match="exactly one"):
        find_wheel(tmp_path)
    wheel = tmp_path / "henchman_ai-1.0-py3-none-any.whl"
    wheel.touch()
    assert find_wheel(tmp_path) == wheel
    (tmp_path / "other.whl").touch()
    with pytest.raises(ValueError, match="exactly one"):
        find_wheel(tmp_path)


def test_smoke_environment_removes_source_injection_and_preserves_executable_path():
    original = {"PYTHONPATH": "/checkout/src", "PYTHONHOME": "/other-python", "PATH": "executables"}
    isolated = smoke_environment(original)
    assert "PYTHONPATH" not in isolated
    assert "PYTHONHOME" not in isolated
    assert isolated["PATH"] == "executables"
    assert "PYTHONUTF8" not in isolated
    assert original["PYTHONPATH"] == "/checkout/src"


@pytest.mark.parametrize("utf8_mode", ["0", "1"])
def test_smoke_environment_preserves_inherited_encoding(utf8_mode):
    original = {"PYTHONUTF8": utf8_mode, "PYTHONIOENCODING": "cp1252"}
    isolated = smoke_environment(original)
    assert isolated["PYTHONUTF8"] == utf8_mode
    assert isolated["PYTHONIOENCODING"] == "cp1252"


def test_staged_tests_exclude_source_and_source_loading_conftest(tmp_path):
    repository = Path(__file__).resolve().parents[2]
    stage_workflow_tests(repository, tmp_path)
    assert not (tmp_path / "src").exists()
    assert not (tmp_path / "pyproject.toml").exists()
    assert (tmp_path / "tests/e2e/test_coding_loop.py").read_bytes() == (
        repository / "tests/e2e/test_coding_loop.py"
    ).read_bytes()
    assert (tmp_path / "tests/providers/stream_helpers.py").is_file()
    assert (tmp_path / "tests/tools/test_python_exec.py").is_file()
    assert (tmp_path / "tests/tools/test_python_verification_integrity.py").read_bytes() == (
        repository / "tests/tools/test_python_verification_integrity.py"
    ).read_bytes()
    assert (tmp_path / "tests/__init__.py").is_file()
    assert (tmp_path / "tests/conftest.py").read_text() != (
        repository / "tests/conftest.py"
    ).read_text()
    assert "distribution" in (tmp_path / "tests/conftest.py").read_text()
    assert (tmp_path / "evals/artifact_observation.py").is_file()
    assert (tmp_path / "evals/package_oracle.py").is_file()
    assert not (tmp_path / "tests/testing/test_package_oracle.py").exists()


def test_package_staging_is_explicit_and_keeps_source_excluded(tmp_path):
    repository = Path(__file__).resolve().parents[2]
    stage_workflow_tests(repository, tmp_path, include_package=True)
    assert not (tmp_path / "src").exists()
    for name in ("test_package_oracle.py", "test_team_package_scenario.py"):
        assert (tmp_path / "tests/testing" / name).read_bytes() == (
            repository / "tests/testing" / name
        ).read_bytes()
