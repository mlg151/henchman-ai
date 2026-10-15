"""Tests for the guided Tier 1 init command."""

from __future__ import annotations

from pathlib import Path

import yaml
from click.testing import CliRunner

from henchman.cli.commands.init_command import create_init_command


def _write_settings(settings_dir: Path, payload: dict[str, object]) -> None:
    """Write a YAML settings file for a test scope."""
    settings_dir.mkdir(parents=True, exist_ok=True)
    (settings_dir / "settings.yaml").write_text(
        yaml.safe_dump(payload, sort_keys=True),
        encoding="utf-8",
    )


def _read_settings(settings_dir: Path) -> dict[str, object]:
    """Read a YAML settings file from a test scope."""
    raw = (settings_dir / "settings.yaml").read_text(encoding="utf-8")
    parsed = yaml.safe_load(raw)
    assert isinstance(parsed, dict)
    return parsed


def test_init_bootstraps_project_local_settings_for_a_new_workspace(
    tmp_path: Path,
) -> None:
    """The wizard should create .henchman and persist guided Tier 1 settings."""
    project_root = tmp_path / "workspace"
    project_root.mkdir()
    runner = CliRunner()

    result = runner.invoke(
        create_init_command(project_root=project_root),
        input="n\nverbose\nmonokai\nc-j\nc-q\n",
    )

    assert result.exit_code == 0
    assert _read_settings(project_root / ".henchman") == {
        "ui": {
            "keybindings": {"c-j": "abort", "c-q": "exit"},
            "show_line_numbers": False,
            "theme": "monokai",
        }
    }
    assert "Created project settings in" in result.output
    assert "Next: run `henchman help`" in result.output


def test_init_preserves_existing_settings_when_update_is_declined(tmp_path: Path) -> None:
    """The wizard should stop before mutation when an existing project opts out."""
    project_root = tmp_path / "workspace"
    project_root.mkdir()
    settings_dir = project_root / ".henchman"
    _write_settings(settings_dir, {"ui": {"show_line_numbers": False, "theme": "light"}})
    before = (settings_dir / "settings.yaml").read_text(encoding="utf-8")
    runner = CliRunner()

    result = runner.invoke(
        create_init_command(project_root=project_root),
        input="n\n",
    )

    assert result.exit_code == 0
    assert "Detected existing project-local settings." in result.output
    assert "Init cancelled; existing settings were preserved." in result.output
    assert (settings_dir / "settings.yaml").read_text(encoding="utf-8") == before


def test_init_updates_guided_values_and_preserves_non_init_settings(
    tmp_path: Path,
) -> None:
    """Re-running init should merge guided choices without clobbering other config."""
    project_root = tmp_path / "workspace"
    project_root.mkdir()
    settings_dir = project_root / ".henchman"
    _write_settings(
        settings_dir,
        {
            "tools": {"shell_timeout": 12},
            "ui": {"theme": "light"},
        },
    )
    runner = CliRunner()

    result = runner.invoke(
        create_init_command(project_root=project_root),
        input="y\nn\njson\ndracula\nc-space\nc-x\n",
    )

    assert result.exit_code == 0
    assert _read_settings(settings_dir) == {
        "tools": {"shell_timeout": 12},
        "ui": {
            "keybindings": {"c-space": "abort", "c-x": "exit"},
            "output_style": "json",
            "show_line_numbers": False,
            "theme": "dracula",
        },
    }
    assert "Detected existing project-local settings." in result.output
    assert "Updated project settings in" in result.output
