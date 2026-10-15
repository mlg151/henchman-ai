"""Regression tests for the Tier 1 config package surface."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_config_package_exports_loader_and_settings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The config package should expose the loader bridge used by the CLI."""
    from henchman.config import ContextLoader, Settings, load_settings

    home_dir = tmp_path / "home"
    home_dir.mkdir()
    monkeypatch.setenv("HOME", str(home_dir))

    assert ContextLoader.__name__ == "ContextLoader"
    settings = load_settings()
    assert isinstance(settings, Settings)

    loader = ContextLoader(start_dir=tmp_path)
    assert loader.load() == ""


def test_config_environment_bridge_exports_helpers() -> None:
    """The environment helper bridge should stay importable."""
    from henchman.config.environment import (
        EnvironmentContext,
        format_environment_block,
        gather_environment,
    )

    environment = gather_environment()

    assert isinstance(environment, EnvironmentContext)
    assert isinstance(format_environment_block(environment), str)


def test_load_settings_merges_user_and_project_settings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Project settings should override user settings while preserving defaults."""
    from henchman.config import load_settings

    home_dir = tmp_path / "home"
    project_root = tmp_path / "workspace"
    user_config_dir = home_dir / ".henchman"
    project_config_dir = project_root / ".henchman"
    user_config_dir.mkdir(parents=True)
    project_config_dir.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home_dir))

    (user_config_dir / "settings.yaml").write_text(
        "providers:\n  default: openai\nui:\n  theme: light\n",
        encoding="utf-8",
    )
    (project_config_dir / "settings.yaml").write_text(
        "ui:\n  theme: monokai\ntools:\n  shell_timeout: 120\n",
        encoding="utf-8",
    )

    settings = load_settings(project_root=project_root)

    assert settings.providers.default == "openai"
    assert settings.ui.theme == "monokai"
    assert settings.tools.shell_timeout == 120


def test_load_settings_supports_legacy_project_settings_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Legacy project config should be read when the canonical directory is absent."""
    from henchman.config import load_settings

    home_dir = tmp_path / "home"
    project_root = tmp_path / "workspace"
    legacy_config_dir = project_root / ".hENCHMAN"
    legacy_config_dir.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home_dir))

    (legacy_config_dir / "settings.yaml").write_text(
        "ui:\n  theme: dracula\n",
        encoding="utf-8",
    )

    settings = load_settings(project_root=project_root)

    assert settings.ui.theme == "dracula"


def test_load_settings_reports_source_path_for_invalid_settings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Invalid persisted settings should report the file path and setting path."""
    from henchman.config import load_settings

    home_dir = tmp_path / "home"
    user_config_dir = home_dir / ".henchman"
    user_config_dir.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home_dir))

    settings_file = user_config_dir / "settings.yaml"
    settings_file.write_text(
        "chat:\n  discord:\n    stale_key: true\n",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match=r"Invalid settings in .*settings\.yaml: .*chat\.discord\.stale_key",
    ):
        load_settings()


def test_context_loader_reads_project_context_from_canonical_settings_dir(tmp_path: Path) -> None:
    """Context discovery should include the project-local config directory."""
    from henchman.config import ContextLoader

    project_root = tmp_path / "workspace"
    nested_dir = project_root / "src" / "pkg"
    config_dir = project_root / ".henchman"
    nested_dir.mkdir(parents=True)
    (project_root / ".git").mkdir()
    config_dir.mkdir()
    (project_root / "HENCHMAN.md").write_text("root guidance", encoding="utf-8")
    (config_dir / "HENCHMAN.md").write_text("config guidance", encoding="utf-8")

    loader = ContextLoader(start_dir=nested_dir)

    discovered = loader.discover_files()

    assert config_dir / "HENCHMAN.md" in discovered
    assert project_root / "HENCHMAN.md" in discovered
    loaded = loader.load()
    assert "root guidance" in loaded
    assert "config guidance" in loaded


def test_format_environment_block_is_deterministic() -> None:
    """Formatted environment blocks should be stable for prompt tests."""
    from henchman.config.environment import EnvironmentContext, format_environment_block

    environment = EnvironmentContext(
        working_directory="/workspace",
        git_root="/workspace",
        git_branch="main",
        git_status="clean (no uncommitted changes)",
        os_info="Linux 6.1.0",
        shell="/bin/bash",
        python_version="3.12.2",
        project_types=[("Python", "pyproject.toml")],
        directory_snapshot=["src/", "tests/", "README.md"],
        available_tools=["git", "python", "ruff"],
    )

    assert format_environment_block(environment) == (
        "<environment_context>\n"
        "* Working directory: /workspace\n"
        "* Git repository root: /workspace\n"
        "* Git branch: main\n"
        "* Git status: clean (no uncommitted changes)\n"
        "* OS: Linux 6.1.0\n"
        "* Shell: /bin/bash\n"
        "* Python: 3.12.2\n"
        "* Project type: Python (pyproject.toml)\n"
        "* Directory contents (top-level): src/ tests/ README.md\n"
        "* Available tools: git, python, ruff\n"
        "</environment_context>"
    )


def test_ci_smoke_installs_both_distribution_formats() -> None:
    """CI should install the release artifacts users can receive from PyPI."""
    workflow = (REPOSITORY_ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    parsed_workflow = yaml.safe_load(workflow)

    assert parsed_workflow["jobs"]["test"]["strategy"]["matrix"]["python-version"] == [
        "3.11",
        "3.12",
        "3.13",
        "3.14",
    ]

    package_smoke = workflow.split("  package-smoke:\n", maxsplit=1)[1]
    assert 'python-version: ["3.11", "3.14"]' in package_smoke
    assert "python -m pip install dist/*.whl" in package_smoke

    source_smoke = workflow.split("  source-smoke:\n", maxsplit=1)[1]
    assert 'python-version: "3.11"' in source_smoke
    assert "python -m pip install dist/*.tar.gz" in source_smoke


@pytest.mark.parametrize("job_name", ["package-smoke", "source-smoke"])
def test_ci_artifact_smoke_exercises_installed_runtime_contracts(job_name: str) -> None:
    """Every artifact install should exercise CLI, API, and RAG behavior."""
    workflow = yaml.safe_load(
        (REPOSITORY_ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    )
    job = workflow["jobs"][job_name]
    smoke_script = "\n".join(step.get("run", "") for step in job["steps"])

    assert "henchman --version" in smoke_script
    assert "mlg --version" in smoke_script
    assert "henchman --help" in smoke_script
    assert "henchman definitely-not-a-command" in smoke_script
    assert 'TestClient(app).get("/v1/ready")' in smoke_script
    assert "collection.query(" in smoke_script
    assert "embeddings=" in smoke_script
    assert "query_embeddings=" in smoke_script
