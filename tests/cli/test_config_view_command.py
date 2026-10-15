"""Tests for the Tier 1 config view command slice."""

from __future__ import annotations

from pathlib import Path

import click
import pytest
import yaml
from click.testing import CliRunner

from henchman.cli.commands.config_view_command import (
    create_config_get_command,
    create_config_list_command,
    create_config_view_command,
)


def _write_settings(settings_dir: Path, payload: dict[str, object]) -> None:
    """Write a YAML settings file for a test scope."""
    settings_dir.mkdir(parents=True, exist_ok=True)
    (settings_dir / "settings.yaml").write_text(
        yaml.safe_dump(payload, sort_keys=True),
        encoding="utf-8",
    )


def _build_config_group(project_root: Path) -> click.Group:
    """Build a config command group for slice-level tests."""

    @click.group()
    def group() -> None:
        """Test config command group."""

    group.add_command(create_config_view_command(project_root=project_root))
    group.add_command(create_config_get_command(project_root=project_root))
    group.add_command(create_config_list_command(project_root=project_root))
    return group


def test_view_reads_merged_value_and_reports_project_scope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The view command should resolve merged values and report project precedence."""
    home_dir = tmp_path / "home"
    project_root = tmp_path / "workspace"
    project_root.mkdir()
    monkeypatch.setenv("HOME", str(home_dir))
    _write_settings(home_dir / ".henchman", {"ui": {"theme": "light"}})
    _write_settings(project_root / ".henchman", {"ui": {"theme": "monokai"}})
    before = (project_root / ".henchman" / "settings.yaml").read_text(encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(_build_config_group(project_root), ["view", "ui.theme"])

    assert result.exit_code == 0
    assert result.output == (
        "key: ui.theme\n"
        "value: monokai\n"
        "requested_scope: merged\n"
        "resolved_scope: project\n"
    )
    assert (project_root / ".henchman" / "settings.yaml").read_text(encoding="utf-8") == before


def test_view_reports_default_scope_for_unset_merged_values(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The merged view should expose when a value only comes from defaults."""
    home_dir = tmp_path / "home"
    project_root = tmp_path / "workspace"
    project_root.mkdir()
    monkeypatch.setenv("HOME", str(home_dir))

    runner = CliRunner()
    result = runner.invoke(
        _build_config_group(project_root),
        ["view", "ui.show_line_numbers"],
    )

    assert result.exit_code == 0
    assert result.output == (
        "key: ui.show_line_numbers\n"
        "value: true\n"
        "requested_scope: merged\n"
        "resolved_scope: default\n"
    )


def test_get_is_an_alias_for_key_reads(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The get command should expose the same read payload as view."""
    home_dir = tmp_path / "home"
    project_root = tmp_path / "workspace"
    project_root.mkdir()
    monkeypatch.setenv("HOME", str(home_dir))
    _write_settings(home_dir / ".henchman", {"ui": {"output_style": "verbose"}})

    runner = CliRunner()
    result = runner.invoke(
        _build_config_group(project_root),
        ["get", "ui.output_style"],
    )

    assert result.exit_code == 0
    assert result.output == (
        "key: ui.output_style\n"
        "value: verbose\n"
        "requested_scope: merged\n"
        "resolved_scope: global\n"
    )


def test_view_redacts_secret_like_scalar_values(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """View should mask secret-like values in human-readable output."""
    home_dir = tmp_path / "home"
    project_root = tmp_path / "workspace"
    project_root.mkdir()
    monkeypatch.setenv("HOME", str(home_dir))
    _write_settings(
        project_root / ".henchman",
        {"chat": {"discord": {"token": "super-secret-token"}}},
    )

    runner = CliRunner()
    result = runner.invoke(
        _build_config_group(project_root),
        ["view", "chat.discord.token"],
    )

    assert result.exit_code == 0
    assert result.output == (
        "key: chat.discord.token\n"
        "value: <redacted>\n"
        "requested_scope: merged\n"
        "resolved_scope: project\n"
    )


def test_get_redacts_secret_like_list_values(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Get should mask secret-like list values in human-readable output."""
    home_dir = tmp_path / "home"
    project_root = tmp_path / "workspace"
    project_root.mkdir()
    monkeypatch.setenv("HOME", str(home_dir))
    _write_settings(
        project_root / ".henchman",
        {
            "api": {"api_keys": ["alpha-key", "beta-key"]},
        },
    )

    runner = CliRunner()
    result = runner.invoke(
        _build_config_group(project_root),
        ["get", "api.api_keys", "--scope", "project"],
    )

    assert result.exit_code == 0
    assert result.output == (
        "key: api.api_keys\n"
        "value: <redacted>\n"
        "requested_scope: project\n"
        "resolved_scope: project\n"
    )


def test_view_surfaces_prd_error_code_for_missing_keys(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The view command should expose the PRD error code for missing keys."""
    home_dir = tmp_path / "home"
    project_root = tmp_path / "workspace"
    project_root.mkdir()
    monkeypatch.setenv("HOME", str(home_dir))
    _write_settings(home_dir / ".henchman", {"ui": {"theme": "light"}})

    runner = CliRunner()
    result = runner.invoke(_build_config_group(project_root), ["view", "ui.missing"])

    assert result.exit_code != 0
    assert result.output == (
        "Error: HMN_CFG_KEY_NOT_FOUND: Requested configuration key was not found. "
        "Missing key 'ui.missing' in merged settings.\n"
    )


def test_get_surfaces_prd_error_code_for_missing_keys(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The get alias should expose the same missing-key failure contract."""
    home_dir = tmp_path / "home"
    project_root = tmp_path / "workspace"
    project_root.mkdir()
    monkeypatch.setenv("HOME", str(home_dir))

    runner = CliRunner()
    result = runner.invoke(_build_config_group(project_root), ["get", "ui.missing"])

    assert result.exit_code != 0
    assert result.output == (
        "Error: HMN_CFG_KEY_NOT_FOUND: Requested configuration key was not found. "
        "Missing key 'ui.missing' in merged settings.\n"
    )


def test_list_returns_sorted_keys_for_the_selected_scope(
    tmp_path: Path,
) -> None:
    """The list command should surface deterministic keys for an explicit scope."""
    project_root = tmp_path / "workspace"
    project_root.mkdir()
    _write_settings(
        project_root / ".henchman",
        {"ui": {"theme": "light", "output_style": "json"}},
    )

    runner = CliRunner()
    result = runner.invoke(
        _build_config_group(project_root),
        ["list", "--scope", "project"],
    )

    assert result.exit_code == 0
    assert result.output == (
        "requested_scope: project\n"
        "entries:\n"
        "- key: ui.output_style\n"
        "  resolved_scope: project\n"
        "- key: ui.theme\n"
        "  resolved_scope: project\n"
    )
