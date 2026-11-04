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
    assert not (tmp_path / "tests/testing/test_package_runtime_observer.py").exists()
    assert not (tmp_path / "tests/testing/test_package_lifecycle_scenario.py").exists()


def test_package_staging_is_explicit_and_keeps_source_excluded(tmp_path):
    repository = Path(__file__).resolve().parents[2]
    stage_workflow_tests(repository, tmp_path, include_package=True)
    assert not (tmp_path / "src").exists()
    for name in (
        "test_package_oracle.py", "test_team_package_scenario.py",
        "test_package_runtime_observer.py",
        "test_package_lifecycle_scenario.py",
    ):
        assert (tmp_path / "tests/testing" / name).read_bytes() == (
            repository / "tests/testing" / name
        ).read_bytes()


@pytest.mark.parametrize("include_package", [True, False])
def test_stage_workflow_tests_includes_correct_files(
    tmp_path: Path, include_package: bool,
) -> None:
    """Stage the UTF-8 fixture regression and its actual helper in both modes."""
    repository = Path(__file__).resolve().parents[2]
    stage_workflow_tests(repository, tmp_path, include_package=include_package)

    regression_path = repository / "tests/testing/test_eval_fixture_encoding.py"
    helpers_path = repository / "evals/helpers.py"

    assert (tmp_path / regression_path.relative_to(repository)).read_bytes() == (
        regression_path.read_bytes()
    )
    assert (tmp_path / helpers_path.relative_to(repository)).read_bytes() == (
        helpers_path.read_bytes()
    )


@pytest.mark.parametrize("include_package", [True, False])
def test_stage_workflow_tests_includes_new_release_and_syntax_files(
    tmp_path: Path, include_package: bool,
) -> None:
    """Verify that new release corpus and syntax files are staged correctly."""
    repository = Path(__file__).resolve().parents[2]
    stage_workflow_tests(repository, tmp_path, include_package=include_package)

    paths = [
        "evals/release_corpus.py",
        "tests/testing/test_release_corpus.py",
        "tests/testing/test_syntax_scenario.py",
        "tests/testing/test_syntax_eval_contract.py",
    ]

    for path_str in paths:
        path = repository / path_str
        assert path.exists(), f"Expected {path} to exist in repository"
        assert (tmp_path / path_str).read_bytes() == path.read_bytes()


@pytest.mark.parametrize("include_package", [True, False])
def test_stage_workflow_tests_includes_new_regression_files(
    tmp_path: Path, include_package: bool,
) -> None:
    """Verify reviewed regression modules are staged correctly in both modes."""
    repository = Path(__file__).resolve().parents[2]
    stage_workflow_tests(repository, tmp_path, include_package=include_package)

    paths = [
        "tests/testing/test_fibonacci_scenario.py",
        "tests/testing/test_eval_bytecode_freshness.py",
        "tests/config/test_ui_unknown_fields.py",
        "tests/config/test_settings_snapshot.py",
        "tests/testing/test_pytest_evidence_helper.py",
        "tests/testing/test_python_reuse_scenario.py",
        "tests/config/test_settings_inspection.py",
        "tests/config/test_session_settings_overrides.py",
        "tests/config/test_strict_setting_fields.py",
        "tests/config/test_grouped_settings_inspection.py",
        "tests/config/test_unknown_group_error_origin.py",
        "tests/cli/test_config_group_values.py",
        "tests/cli/test_config_environment_origins.py",
        "tests/cli/test_runtime_settings_snapshot.py",
        "tests/cli/test_textual_settings_snapshot.py",
        "tests/cli/test_tui_injected_settings.py",
        "evals/test_test_docs.py",
        "tests/testing/test_test_docs_oracle.py",
        "tests/testing/test_test_docs_documentation.py",
        "tests/testing/test_test_docs_scenario.py",
        "tests/testing/test_semantic_bug_scenario.py",
        "evals/test_package_lifecycle.py",
    ]

    for path_str in paths:
        path = repository / path_str
        assert path.exists(), f"Expected {path} to exist in repository"
        assert (tmp_path / path_str).read_bytes() == path.read_bytes()
