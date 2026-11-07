"""Validate portable wheel smoke staging without installing or launching subprocesses."""

import ast
import os
import sysconfig
import zipfile
from pathlib import Path

import pytest
from tests.testing.installed_wheel_smoke import (
    find_wheel,
    isolated_runtime_environment,
    smoke_environment,
    stage_workflow_tests,
    verify_wheel_contents,
)


def test_find_wheel_requires_one_unambiguous_artifact(tmp_path):
    with pytest.raises(ValueError, match="exactly one"):
        find_wheel(tmp_path)
    wheel = tmp_path / "henchman_ai-1.0-py3-none-any.whl"
    wheel.touch()
    assert find_wheel(tmp_path) == wheel
    (tmp_path / "other.whl").touch()
    with pytest.raises(ValueError, match="exactly one"):
        find_wheel(tmp_path)


def test_same_version_stale_install_cannot_pass_artifact_verification(tmp_path):
    wheel = tmp_path / "release.whl"
    installation = tmp_path / "site-packages"
    package = installation / "henchman"
    package.mkdir(parents=True)
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("henchman/__init__.py", '__version__ = "0.4.1"\n')
        archive.writestr("henchman/runtime.py", "release behavior\n")
    (package / "__init__.py").write_text('__version__ = "0.4.1"\n')
    (package / "runtime.py").write_text("old behavior\n")
    with pytest.raises(RuntimeError, match="does not match"):
        verify_wheel_contents(wheel, installation)
    (package / "runtime.py").write_text("release behavior\n")
    verify_wheel_contents(wheel, installation)
    (package / "runtime.py").unlink()
    with pytest.raises(RuntimeError, match="does not match"):
        verify_wheel_contents(wheel, installation)


def test_smoke_environment_selects_installed_interpreter_before_inherited_executables():
    original = {"PYTHONPATH": "/checkout/src", "PYTHONHOME": "/other-python", "PATH": "executables"}
    isolated = smoke_environment(original)
    assert "PYTHONPATH" not in isolated
    assert "PYTHONHOME" not in isolated
    assert isolated["PATH"].split(os.pathsep) == [sysconfig.get_path("scripts"), "executables"]
    assert "PYTHONUTF8" not in isolated
    assert original["PYTHONPATH"] == "/checkout/src"


def test_runtime_environment_has_empty_caches_and_no_user_provider_selection(tmp_path):
    original = {"HOME": "/user", "TIKTOKEN_CACHE_DIR": "/warm-cache",
                "HENCHMAN_SETTINGS_PATH": "/user/settings", "HENCHMAN_PROVIDER": "remote",
                "HENCHMAN_MODEL": "inherited", "OPENAI_API_KEY": "private-value"}
    isolated = isolated_runtime_environment(original, tmp_path)
    for key in ("HOME", "USERPROFILE", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME", "TIKTOKEN_CACHE_DIR", "DATA_GYM_CACHE_DIR"):
        assert Path(isolated[key]).is_relative_to(tmp_path)
        assert Path(isolated[key]).is_dir()
    assert not list(Path(isolated["TIKTOKEN_CACHE_DIR"]).iterdir())
    assert not any(key.startswith("HENCHMAN_") for key in isolated)
    assert "OPENAI_API_KEY" not in isolated
    assert original["HOME"] == "/user"


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
        "tests/cli/test_config_header_redaction.py",
        "tests/cli/test_config_environment_origins.py",
        "tests/cli/test_runtime_settings_snapshot.py",
        "tests/cli/test_textual_settings_snapshot.py",
        "tests/cli/test_tui_injected_settings.py",
        "evals/test_test_docs.py",
        "tests/testing/test_test_docs_oracle.py",
        "tests/testing/test_test_docs_documentation.py",
        "tests/testing/test_test_docs_scenario.py",
        "tests/testing/test_semantic_bug_scenario.py",
        "evals/test_tool_failure_recovery.py",
        "tests/testing/test_tool_failure_recovery_scenario.py",
        "evals/test_package_lifecycle.py",
        "evals/test_interruption_recovery.py",
        "tests/testing/test_interruption_recovery_scenario.py",
        "tests/core/test_typed_tool_results.py",
        "tests/tools/test_restricted_web_fetch.py",
        "tests/config/test_network_host_settings.py",
        "tests/config/test_verification_settings.py",
        "tests/advanced/test_project_verification.py",
        "tests/core/test_workflow_state.py",
        "tests/core/test_session_workflow.py",
        "tests/ops/test_workflow_store.py",
        "tests/contracts/test_workflow_contract.py",
        "tests/mcp/test_context_attachment_handles.py",
        "tests/mcp/oauth_fixture.py",
        "tests/mcp/test_oauth_foundation.py",
        "tests/mcp/test_oauth_discovery.py",
        "tests/mcp/test_oauth_store.py",
        "tests/cli/test_mcp_context_attachment.py",
        "tests/core/test_context_attachments.py",
        "tests/utils/test_context_attachment_compaction.py",
        "tests/contracts/test_context_attachment_contract.py",
        "tests/contracts/schemas/runtime/message.json",
        "tests/contracts/schemas/providers/message.json",
        "tests/contracts/schemas/runtime/stream_chunk.json",
        "tests/contracts/schemas/config/mcp_server_config.json",
        "tests/contracts/test_advanced_contracts.py",
        "tests/contracts/schemas/advanced/task_record.json",
        "tests/contracts/schemas/advanced/plan_record.json",
        "tests/contracts/schemas/advanced/cron_schedule.json",
        "tests/contracts/schemas/advanced/repl_session.json",
        "tests/contracts/schemas/advanced/tungsten_snapshot.json",
    ]

    for path_str in paths:
        path = repository / path_str
        assert path.exists(), f"Expected {path} to exist in repository"
        assert (tmp_path / path_str).read_bytes() == path.read_bytes()


@pytest.mark.parametrize("include_package", [False, True])
def test_staged_workflows_include_local_import_dependencies(tmp_path, include_package):
    """Native collection must not depend on test helpers left in the checkout."""
    repository = Path(__file__).resolve().parents[2]
    stage_workflow_tests(repository, tmp_path, include_package=include_package)
    missing = []
    for staged in tmp_path.rglob("*.py"):
        for node in ast.walk(ast.parse(staged.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                modules = [node.module, *(f"{node.module}.{alias.name}" for alias in node.names)]
            else:
                continue
            for module in modules:
                if module.split(".")[0] not in {"tests", "evals"}:
                    continue
                relative = Path(*module.split(".")).with_suffix(".py")
                if (repository / relative).is_file() and not (tmp_path / relative).is_file():
                    missing.append(f"{staged.relative_to(tmp_path)} imports unstaged {relative}")
    assert not missing, "\n".join(sorted(set(missing)))
