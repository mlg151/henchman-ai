from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from henchman.cli.commands.config_command import create_config_command
from henchman.cli.commands.config_view_command import create_config_get_command
from henchman.config import repository
from henchman.config.settings import SettingsSnapshot


@pytest.mark.parametrize(
    "key, expected_value, expected_resolved_scope",
    [
        ("providers.default", "deepseek", "environment"),
        ("providers.deepseek.model", "env-model", "environment"),
        ("providers.openrouter.model", "file-router", "project"),
    ],
)
def test_config_environment_origins(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    key: str,
    expected_value: str,
    expected_resolved_scope: str,
) -> None:
    """
    Regression test to expose bug where origin reporting is incorrect for merged settings.
    """
    # Setup paths
    project_root = tmp_path / "project"
    project_root.mkdir()
    home_dir = tmp_path / "home"

    # Mock home directory
    monkeypatch.setattr("pathlib.Path.home", lambda: home_dir)

    # Create .henchman/settings.json in project root
    settings_dir = project_root / ".henchman"
    settings_dir.mkdir(parents=True, exist_ok=True)
    settings_file = settings_dir / "settings.json"

    payload = {
        "providers": {
            "default": "openrouter",
            "openrouter": {
                "model": "file-router",
            },
            "deepseek": {
                "model": "file-deepseek",
            },
        },
    }
    # Use json.dump to ensure compatibility with .json extension
    settings_file.write_text(
        json.dumps(payload, sort_keys=True),
        encoding="utf-8",
    )

    # Environment variables
    monkeypatch.delenv("HENCHMAN_SETTINGS_PATH", raising=False)
    monkeypatch.setenv("HENCHMAN_PROVIDER", "deepseek")
    monkeypatch.setenv("HENCHMAN_MODEL", "env-model")

    runner = CliRunner()

    result = runner.invoke(
        create_config_get_command(project_root=project_root),
        [key],
    )

    assert result.exit_code == 0
    output = yaml.safe_load(result.output)
    assert output["value"] == expected_value
    assert output["resolved_scope"] == expected_resolved_scope


def test_config_environment_origins_explicit_scope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Explicit --scope project query for providers.deepseek.model => file-deepseek/project.
    """
    project_root = tmp_path / "project"
    project_root.mkdir()
    home_dir = tmp_path / "home"

    # Mock home directory
    monkeypatch.setattr("pathlib.Path.home", lambda: home_dir)

    # Create .henchman/settings.json in project root
    settings_dir = project_root / ".henchman"
    settings_dir.mkdir(parents=True, exist_ok=True)
    settings_file = settings_dir / "settings.json"

    payload = {
        "providers": {
            "default": "openrouter",
            "openrouter": {
                "model": "file-router",
            },
            "deepseek": {
                "model": "file-deepseek",
            },
        },
    }
    # Use json.dump to ensure compatibility with .json extension
    settings_file.write_text(
        json.dumps(payload, sort_keys=True),
        encoding="utf-8",
    )

    # Environment variables
    monkeypatch.delenv("HENCHMAN_SETTINGS_PATH", raising=False)
    monkeypatch.setenv("HENCHMAN_PROVIDER", "deepseek")
    monkeypatch.setenv("HENCHMAN_MODEL", "env-model")

    runner = CliRunner()

    result = runner.invoke(
        create_config_get_command(project_root=project_root),
        ["providers.deepseek.model", "--scope", "project"],
    )

    assert result.exit_code == 0
    output = yaml.safe_load(result.output)
    assert output["value"] == "file-deepseek"
    assert output["resolved_scope"] == "project"


@pytest.mark.parametrize(
    "command_name",
    ["get", "list"],
)
def test_config_get_and_list_use_one_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    command_name: str,
) -> None:
    """Resolve each real command once and report the environment origin."""
    project_root = tmp_path / "project"
    project_root.mkdir()
    home_dir = tmp_path / "home"
    home_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr("pathlib.Path.home", lambda: home_dir)
    monkeypatch.delenv("HENCHMAN_SETTINGS_PATH", raising=False)
    monkeypatch.setenv("HENCHMAN_PROVIDER", "deepseek")
    monkeypatch.setenv("HENCHMAN_MODEL", "env-model")

    real_load = repository.load_settings_snapshot

    calls: list[Path | None] = []

    def mocked_load_settings_snapshot(project_root: Path | None = None) -> SettingsSnapshot:
        calls.append(project_root)
        return real_load(project_root=project_root)

    monkeypatch.setattr(repository, "load_settings_snapshot", mocked_load_settings_snapshot)

    runner = CliRunner()

    if command_name == "get":
        args = ["get", "providers.deepseek.model"]
        result = runner.invoke(
            create_config_command(project_root=project_root),
            args,
        )
        assert result.exit_code == 0
        output = yaml.safe_load(result.output)
        assert output["value"] == "env-model"
        assert output["resolved_scope"] == "environment"
    else:
        args = ["list"]
        result = runner.invoke(
            create_config_command(project_root=project_root),
            args,
        )
        assert result.exit_code == 0
        output = yaml.safe_load(result.output)
        assert "entries" in output
        entries = output["entries"]
        # Find the entry for providers.deepseek.model
        entry = next((e for e in entries if e["key"] == "providers.deepseek.model"), None)
        assert entry is not None
        assert entry["resolved_scope"] == "environment"

    assert calls == [project_root]
