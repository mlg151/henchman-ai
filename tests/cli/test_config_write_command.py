"""Tests for the Tier 1 config write command slice."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import click
import pytest
import yaml
from click.testing import CliRunner

from henchman.cli.commands.config_write_command import (
    create_config_export_command,
    create_config_import_command,
    create_config_set_command,
    create_config_unset_command,
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


def _build_config_group(project_root: Path) -> click.Group:
    """Build a config command group for slice-level tests."""

    @click.group()
    def group() -> None:
        """Test config command group."""

    group.add_command(create_config_set_command(project_root=project_root))
    group.add_command(create_config_unset_command(project_root=project_root))
    group.add_command(create_config_import_command(project_root=project_root))
    group.add_command(create_config_export_command(project_root=project_root))
    return group


def test_set_command_parses_typed_values_for_explicit_scope(
    tmp_path: Path,
) -> None:
    """Set should coerce scalar and collection values before persistence."""
    project_root = tmp_path / "workspace"
    project_root.mkdir()

    runner = CliRunner()
    group = _build_config_group(project_root)

    max_tokens_result = runner.invoke(
        group,
        ["set", "context.max_tokens", "4096", "--scope", "project"],
    )
    enabled_result = runner.invoke(
        group,
        ["set", "api.require_auth", "true", "--scope", "project"],
    )
    api_keys_result = runner.invoke(
        group,
        ["set", "api.api_keys", '["alpha", "beta"]', "--scope", "project"],
    )

    assert max_tokens_result.exit_code == 0
    assert enabled_result.exit_code == 0
    assert api_keys_result.exit_code == 0
    assert _read_settings(project_root / ".henchman") == {
        "api": {
            "api_keys": ["alpha", "beta"],
            "require_auth": True,
        },
        "context": {"max_tokens": 4096},
    }
    assert max_tokens_result.output == (
        "operation: set\n"
        "key: context.max_tokens\n"
        "value: 4096\n"
        "scope: project\n"
    )


def test_set_command_redacts_secret_like_values_in_text_output_but_not_json(
    tmp_path: Path,
) -> None:
    """Secret-like values should stay machine-usable only in JSON output."""
    project_root = tmp_path / "workspace"
    project_root.mkdir()

    runner = CliRunner()
    group = _build_config_group(project_root)

    text_result = runner.invoke(
        group,
        ["set", "chat.discord.token", "super-secret-token", "--scope", "project"],
    )
    json_result = runner.invoke(
        group,
        [
            "set",
            "chat.discord.token",
            "super-secret-token",
            "--scope",
            "project",
            "--format",
            "json",
        ],
    )

    assert text_result.exit_code == 0
    assert json_result.exit_code == 0
    assert text_result.output == (
        "operation: set\n"
        "key: chat.discord.token\n"
        "value: <redacted>\n"
        "scope: project\n"
    )
    assert json.loads(json_result.output) == {
        "key": "chat.discord.token",
        "operation": "set",
        "scope": "project",
        "value": "super-secret-token",
    }
    assert _read_settings(project_root / ".henchman") == {
        "chat": {"discord": {"token": "super-secret-token"}}
    }


def test_set_command_reports_prd_code_for_invalid_config_values(
    tmp_path: Path,
) -> None:
    """Set should surface the PRD code for schema-invalid config values."""
    project_root = tmp_path / "workspace"
    project_root.mkdir()

    runner = CliRunner()
    result = runner.invoke(
        _build_config_group(project_root),
        ["set", "ui.theme", "midnight", "--scope", "project"],
    )

    assert result.exit_code != 0
    assert "HMN_CFG_INVALID_VALUE" in result.output
    assert "Configuration value failed schema validation." in result.output
    assert "Unsupported theme 'midnight'" in result.output


def test_unset_command_reports_removed_values(
    tmp_path: Path,
) -> None:
    """Unset should remove persisted values from the selected scope."""
    project_root = tmp_path / "workspace"
    project_root.mkdir()
    _write_settings(
        project_root / ".henchman",
        {"ui": {"output_style": "json", "theme": "light"}},
    )

    runner = CliRunner()
    result = runner.invoke(
        _build_config_group(project_root),
        ["unset", "ui.theme", "--scope", "project"],
    )

    assert result.exit_code == 0
    assert result.output == (
        "operation: unset\n"
        "key: ui.theme\n"
        "removed: true\n"
        "scope: project\n"
    )
    assert _read_settings(project_root / ".henchman") == {"ui": {"output_style": "json"}}


@pytest.mark.parametrize("output_args", [[], ["--format", "json"]])
def test_unset_command_surfaces_prd_code_for_missing_keys(
    tmp_path: Path,
    output_args: list[str],
) -> None:
    """Unset should fail with the missing-key PRD contract when nothing is removed."""
    project_root = tmp_path / "workspace"
    project_root.mkdir()
    _write_settings(project_root / ".henchman", {"ui": {"theme": "light"}})

    runner = CliRunner()
    result = runner.invoke(
        _build_config_group(project_root),
        ["unset", "ui.missing", "--scope", "project", *output_args],
    )

    assert result.exit_code != 0
    assert result.output == (
        "Error: HMN_CFG_KEY_NOT_FOUND: Requested configuration key was not found. "
        "Missing key 'ui.missing' in project settings.\n"
    )
    assert _read_settings(project_root / ".henchman") == {"ui": {"theme": "light"}}


def test_export_command_writes_local_sync_payload_to_a_file(
    tmp_path: Path,
) -> None:
    """Export should write the repository sync payload to a local file."""
    project_root = tmp_path / "workspace"
    export_path = tmp_path / "settings-export.yaml"
    project_root.mkdir()
    _write_settings(
        project_root / ".henchman",
        {
            "ui": {
                "keybindings": {"c-j": "accept"},
                "output_style": "json",
                "show_line_numbers": False,
                "theme": "light",
            },
        },
    )

    runner = CliRunner()
    result = runner.invoke(
        _build_config_group(project_root),
        ["export", str(export_path), "--scope", "project"],
    )

    assert result.exit_code == 0
    assert result.output == (
        "operation: export\n"
        f"path: {export_path}\n"
        "scope: project\n"
        "payload:\n"
        "  ui:\n"
        "    output_style: json\n"
        "    theme: light\n"
        "    keybindings:\n"
        "      c-j: accept\n"
    )
    assert yaml.safe_load(export_path.read_text(encoding="utf-8")) == {
        "ui": {
            "output_style": "json",
            "theme": "light",
            "keybindings": {"c-j": "accept"},
        }
    }


@pytest.mark.parametrize(
    ("export_name", "loader"),
    [
        ("settings-export.yaml", yaml.safe_load),
        ("settings-export.yml", yaml.safe_load),
        ("settings-export.json", json.loads),
    ],
)
def test_export_then_import_round_trips_sync_payload_for_supported_formats(
    tmp_path: Path,
    export_name: str,
    loader: Callable[[str], object],
) -> None:
    """Export/import should round-trip via YAML and JSON config sync files."""
    source_root = tmp_path / "source"
    destination_root = tmp_path / "destination"
    export_path = tmp_path / export_name
    source_root.mkdir()
    destination_root.mkdir()
    _write_settings(
        source_root / ".henchman",
        {
            "ui": {
                "keybindings": {"c-j": "accept", "c-k": "cancel"},
                "output_style": "json",
                "show_line_numbers": False,
                "theme": "monokai",
            },
        },
    )

    runner = CliRunner()
    source_group = _build_config_group(source_root)
    destination_group = _build_config_group(destination_root)

    export_result = runner.invoke(
        source_group,
        ["export", str(export_path), "--scope", "project"],
    )
    import_result = runner.invoke(
        destination_group,
        ["import", str(export_path), "--scope", "project"],
    )

    assert export_result.exit_code == 0
    assert import_result.exit_code == 0
    assert loader(export_path.read_text(encoding="utf-8")) == {
        "ui": {
            "output_style": "json",
            "theme": "monokai",
            "keybindings": {"c-j": "accept", "c-k": "cancel"},
        }
    }
    assert _read_settings(destination_root / ".henchman") == {
        "ui": {
            "keybindings": {"c-j": "accept", "c-k": "cancel"},
            "output_style": "json",
            "theme": "monokai",
        }
    }


def test_export_command_rejects_unsupported_destination_suffix(
    tmp_path: Path,
) -> None:
    """Export should reject sync files with unsupported suffixes."""
    project_root = tmp_path / "workspace"
    export_path = tmp_path / "settings-export.toml"
    project_root.mkdir()
    _write_settings(project_root / ".henchman", {"ui": {"theme": "light"}})

    runner = CliRunner()
    result = runner.invoke(
        _build_config_group(project_root),
        ["export", str(export_path), "--scope", "project"],
    )

    assert result.exit_code != 0
    assert "HMN_SYNC_FILE_INVALID" in result.output
    assert "Settings import file is invalid or incompatible with the current schema." in result.output
    assert "Unsupported config sync file format" in result.output


def test_import_command_validates_payload_before_mutating_settings(
    tmp_path: Path,
) -> None:
    """Import should fail before touching persisted settings on invalid payloads."""
    project_root = tmp_path / "workspace"
    import_path = tmp_path / "settings-import.yaml"
    project_root.mkdir()
    _write_settings(project_root / ".henchman", {"ui": {"theme": "light"}})
    before = (project_root / ".henchman" / "settings.yaml").read_text(encoding="utf-8")
    import_path.write_text(
        yaml.safe_dump({"ui": {"output_style": "json", "theme": "midnight"}}, sort_keys=True),
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(
        _build_config_group(project_root),
        ["import", str(import_path), "--scope", "project"],
    )

    assert result.exit_code != 0
    assert "HMN_CFG_INVALID_VALUE" in result.output
    assert "Configuration value failed schema validation." in result.output
    assert "Unsupported theme 'midnight'" in result.output
    assert (project_root / ".henchman" / "settings.yaml").read_text(encoding="utf-8") == before
