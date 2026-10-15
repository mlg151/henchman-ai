"""Tests for the Tier 1 config command group."""

from __future__ import annotations

from pathlib import Path

import click
import pytest
import yaml
from click.testing import CliRunner

from henchman.cli.commands.config_command import (
    create_config_command,
    register_config_command,
)


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


def _build_root_group() -> click.Group:
    """Build a root CLI group for registration tests."""

    @click.group(name="henchman")
    def group() -> None:
        """Test root command."""

    return group


def test_create_config_command_exposes_expected_subcommands() -> None:
    """The config group should expose the Tier 1 config command contract."""
    command = create_config_command()
    context = click.Context(command)

    assert command.name == "config"
    assert isinstance(command, click.Group)
    assert command.list_commands(context) == [
        "export",
        "get",
        "import",
        "list",
        "set",
        "unset",
        "view",
    ]


def test_register_config_command_routes_view_set_and_unset(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The registered config group should delegate read and write subcommands."""
    home_dir = tmp_path / "home"
    project_root = tmp_path / "workspace"
    project_root.mkdir()
    monkeypatch.setenv("HOME", str(home_dir))
    _write_settings(home_dir / ".henchman", {"ui": {"theme": "light"}})

    root = _build_root_group()
    register_config_command(root, project_root=project_root)
    runner = CliRunner()

    view_result = runner.invoke(root, ["config", "view", "ui.theme"])
    set_result = runner.invoke(
        root,
        ["config", "set", "ui.theme", "monokai", "--scope", "project"],
    )
    unset_result = runner.invoke(
        root,
        ["config", "unset", "ui.theme", "--scope", "project"],
    )

    assert view_result.exit_code == 0
    assert view_result.output == (
        "key: ui.theme\n"
        "value: light\n"
        "requested_scope: merged\n"
        "resolved_scope: global\n"
    )
    assert set_result.exit_code == 0
    assert set_result.output == (
        "operation: set\n"
        "key: ui.theme\n"
        "value: monokai\n"
        "scope: project\n"
    )
    assert unset_result.exit_code == 0
    assert unset_result.output == (
        "operation: unset\n"
        "key: ui.theme\n"
        "removed: true\n"
        "scope: project\n"
    )
    assert not (project_root / ".henchman" / "settings.yaml").exists()


def test_register_config_command_routes_list_after_group_writes(tmp_path: Path) -> None:
    """The registered config group should surface list through the shared router."""
    project_root = tmp_path / "workspace"
    project_root.mkdir()

    root = _build_root_group()
    register_config_command(root, project_root=project_root)
    runner = CliRunner()

    set_result = runner.invoke(
        root,
        ["config", "set", "ui.theme", "monokai", "--scope", "project"],
    )
    list_result = runner.invoke(
        root,
        ["config", "list", "--scope", "project"],
    )

    assert set_result.exit_code == 0
    assert list_result.exit_code == 0
    assert list_result.output == (
        "requested_scope: project\n"
        "entries:\n"
        "- key: ui.theme\n"
        "  resolved_scope: project\n"
    )


def test_config_group_routes_import_and_export(tmp_path: Path) -> None:
    """The config group should expose the local import/export flows."""
    project_root = tmp_path / "workspace"
    import_path = tmp_path / "settings-import.yaml"
    export_path = tmp_path / "settings-export.yaml"
    project_root.mkdir()
    import_path.write_text(
        yaml.safe_dump({"ui": {"output_style": "json", "theme": "light"}}, sort_keys=True),
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(
        create_config_command(project_root=project_root),
        ["import", str(import_path), "--scope", "project"],
    )
    export_result = runner.invoke(
        create_config_command(project_root=project_root),
        ["export", str(export_path), "--scope", "project"],
    )

    assert result.exit_code == 0
    assert result.output == (
        "operation: import\n"
        f"path: {import_path}\n"
        "scope: project\n"
        "payload:\n"
        "  ui:\n"
        "    output_style: json\n"
        "    theme: light\n"
    )
    assert export_result.exit_code == 0
    assert export_result.output == (
        "operation: export\n"
        f"path: {export_path}\n"
        "scope: project\n"
        "payload:\n"
        "  ui:\n"
        "    output_style: json\n"
        "    theme: light\n"
    )
    assert _read_settings(project_root / ".henchman") == {
        "ui": {"output_style": "json", "theme": "light"}
    }
    assert yaml.safe_load(export_path.read_text(encoding="utf-8")) == {
        "ui": {"output_style": "json", "theme": "light"}
    }


def test_config_group_help_describes_key_based_local_surface() -> None:
    """The config help text should describe the Tier 1 local config surface."""
    runner = CliRunner()

    result = runner.invoke(create_config_command(), ["--help"])

    assert result.exit_code == 0
    assert "Inspect and edit key-based local configuration values." in result.output
    assert "view" in result.output
    assert "list" in result.output
    assert "set" in result.output
    assert "unset" in result.output
    assert "import" in result.output
    assert "export" in result.output
