"""Tests for Tier 1 settings repository sync helpers."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from henchman.config.repository import SettingsRepository, SettingsScope


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


def test_export_settings_returns_sync_payload_shape(
    tmp_path: Path,
) -> None:
    """Export should serialize only the Tier 1 sync fields."""
    project_root = tmp_path / "workspace"
    project_settings_dir = project_root / ".henchman"
    project_root.mkdir()
    _write_settings(
        project_settings_dir,
        {
            "ui": {
                "output_style": "json",
                "theme": "light",
                "keybindings": {"c-j": "accept"},
                "show_line_numbers": False,
            },
        },
    )

    repository = SettingsRepository(project_root=project_root)

    assert repository.export_settings(scope=SettingsScope.PROJECT) == {
        "ui": {
            "output_style": "json",
            "theme": "light",
            "keybindings": {"c-j": "accept"},
        },
    }


def test_import_settings_round_trip_preserves_sync_values(
    tmp_path: Path,
) -> None:
    """Import/export should round-trip Tier 1 sync values."""
    source_root = tmp_path / "source"
    destination_root = tmp_path / "destination"
    source_root.mkdir()
    destination_root.mkdir()
    _write_settings(
        source_root / ".henchman",
        {
            "ui": {
                "output_style": "minimal",
                "theme": "monokai",
                "keybindings": {"c-j": "accept", "c-k": "cancel"},
            },
        },
    )

    source_repository = SettingsRepository(project_root=source_root)
    destination_repository = SettingsRepository(project_root=destination_root)

    exported_payload = source_repository.export_settings(scope=SettingsScope.PROJECT)

    destination_repository.import_settings(exported_payload, scope=SettingsScope.PROJECT)

    assert destination_repository.export_settings(scope=SettingsScope.PROJECT) == exported_payload


def test_import_settings_is_atomic_when_validation_fails(
    tmp_path: Path,
) -> None:
    """Invalid imports should fail before mutating persisted settings."""
    project_root = tmp_path / "workspace"
    project_settings_dir = project_root / ".henchman"
    project_root.mkdir()
    _write_settings(project_settings_dir, {"ui": {"theme": "light"}})
    before = (project_settings_dir / "settings.yaml").read_text(encoding="utf-8")

    repository = SettingsRepository(project_root=project_root)

    with pytest.raises(ValueError, match="Unsupported theme 'midnight'"):
        repository.import_settings(
            {
                "ui": {
                    "output_style": "json",
                    "theme": "midnight",
                    "keybindings": {"c-j": "accept"},
                },
            },
            scope=SettingsScope.PROJECT,
        )

    assert (project_settings_dir / "settings.yaml").read_text(encoding="utf-8") == before


def test_sync_ui_settings_updates_sync_values_atomically(
    tmp_path: Path,
) -> None:
    """Sync helper should update persisted Tier 1 UI settings in one commit."""
    project_root = tmp_path / "workspace"
    project_settings_dir = project_root / ".henchman"
    project_root.mkdir()
    _write_settings(project_settings_dir, {"ui": {"show_line_numbers": False, "theme": "light"}})

    repository = SettingsRepository(project_root=project_root)

    repository.sync_ui_settings(
        output_style="json",
        theme="monokai",
        keybindings={"c-j": "accept"},
        scope=SettingsScope.PROJECT,
    )

    assert _read_settings(project_settings_dir) == {
        "ui": {
            "keybindings": {"c-j": "accept"},
            "output_style": "json",
            "show_line_numbers": False,
            "theme": "monokai",
        },
    }


def test_sync_ui_settings_preserves_existing_file_on_validation_failure(
    tmp_path: Path,
) -> None:
    """Invalid sync payloads should not partially update persisted settings."""
    project_root = tmp_path / "workspace"
    project_settings_dir = project_root / ".henchman"
    project_root.mkdir()
    _write_settings(
        project_settings_dir,
        {"ui": {"output_style": "compact", "theme": "light"}},
    )
    before = (project_settings_dir / "settings.yaml").read_text(encoding="utf-8")

    repository = SettingsRepository(project_root=project_root)

    with pytest.raises(ValueError, match="Keybinding actions must not be blank"):
        repository.sync_ui_settings(
            output_style="json",
            theme="monokai",
            keybindings={"c-j": ""},
            scope=SettingsScope.PROJECT,
        )

    assert (project_settings_dir / "settings.yaml").read_text(encoding="utf-8") == before
