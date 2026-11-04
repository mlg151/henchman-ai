from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from henchman.cli.commands.config_view_command import create_config_get_command


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
