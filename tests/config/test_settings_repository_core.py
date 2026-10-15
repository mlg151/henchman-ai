"""Tests for the Tier 1 settings repository core."""

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


def test_repository_reads_merged_and_scoped_settings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Merged reads should overlay project settings on top of global settings."""
    home_dir = tmp_path / "home"
    project_root = tmp_path / "workspace"
    user_settings_dir = home_dir / ".henchman"
    project_settings_dir = project_root / ".henchman"
    project_root.mkdir()
    monkeypatch.setenv("HOME", str(home_dir))

    _write_settings(
        user_settings_dir,
        {"ui": {"theme": "light", "show_line_numbers": False}},
    )
    _write_settings(
        project_settings_dir,
        {"ui": {"theme": "monokai", "output_style": "json"}},
    )

    repository = SettingsRepository(project_root=project_root)

    assert repository.get("ui.theme") == "monokai"
    assert repository.get("ui.show_line_numbers") is False
    assert repository.get("ui.theme", scope=SettingsScope.GLOBAL) == "light"
    assert repository.get("ui.show_line_numbers", scope=SettingsScope.PROJECT) is None
    assert repository.list(scope=SettingsScope.PROJECT) == ["ui.output_style", "ui.theme"]
    assert repository.view(scope=SettingsScope.MERGED)["ui"]["theme"] == "monokai"


def test_repository_writes_project_settings_to_canonical_directory(
    tmp_path: Path,
) -> None:
    """Project writes should read legacy data but persist only to .henchman."""
    project_root = tmp_path / "workspace"
    legacy_settings_dir = project_root / ".hENCHMAN"
    project_root.mkdir()
    _write_settings(legacy_settings_dir, {"ui": {"theme": "dracula"}})

    repository = SettingsRepository(project_root=project_root)

    repository.set("ui.output_style", "json", scope=SettingsScope.PROJECT)

    canonical_settings_dir = project_root / ".henchman"
    assert _read_settings(canonical_settings_dir) == {
        "ui": {"output_style": "json", "theme": "dracula"},
    }
    assert _read_settings(legacy_settings_dir) == {"ui": {"theme": "dracula"}}
    assert repository.get("ui.theme", scope=SettingsScope.PROJECT) == "dracula"


def test_repository_validates_values_before_persisting(
    tmp_path: Path,
) -> None:
    """Invalid values should fail before any settings file mutation is committed."""
    project_root = tmp_path / "workspace"
    project_settings_dir = project_root / ".henchman"
    project_root.mkdir()
    _write_settings(project_settings_dir, {"ui": {"theme": "light"}})
    before = (project_settings_dir / "settings.yaml").read_text(encoding="utf-8")

    repository = SettingsRepository(project_root=project_root)

    with pytest.raises(ValueError, match="Unsupported theme 'midnight'"):
        repository.set("ui.theme", "midnight", scope=SettingsScope.PROJECT)
    with pytest.raises(ValueError, match="Keybinding actions must not be blank"):
        repository.set("ui.keybindings.enter", "", scope=SettingsScope.PROJECT)

    assert (project_settings_dir / "settings.yaml").read_text(encoding="utf-8") == before


def test_repository_writes_global_settings_to_home_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Global writes should use the canonical user-scoped .henchman directory."""
    home_dir = tmp_path / "home"
    project_root = tmp_path / "workspace"
    project_root.mkdir()
    monkeypatch.setenv("HOME", str(home_dir))

    repository = SettingsRepository(project_root=project_root)

    repository.set("ui.theme", "light", scope=SettingsScope.GLOBAL)

    assert _read_settings(home_dir / ".henchman") == {"ui": {"theme": "light"}}
    assert repository.get("ui.theme", scope=SettingsScope.GLOBAL) == "light"


def test_repository_view_and_list_global_scope_return_only_global_values(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Global reads should expose only persisted user-scoped settings."""
    home_dir = tmp_path / "home"
    project_root = tmp_path / "workspace"
    project_root.mkdir()
    monkeypatch.setenv("HOME", str(home_dir))
    _write_settings(
        home_dir / ".henchman",
        {"ui": {"output_style": "json", "theme": "light"}},
    )
    _write_settings(
        project_root / ".henchman",
        {"ui": {"show_line_numbers": False, "theme": "monokai"}},
    )

    repository = SettingsRepository(project_root=project_root)

    assert repository.view(scope=SettingsScope.GLOBAL) == {
        "ui": {"output_style": "json", "theme": "light"},
    }
    assert repository.list(scope=SettingsScope.GLOBAL) == [
        "ui.output_style",
        "ui.theme",
    ]


def test_repository_rejects_nested_keys_beneath_scalar_values(
    tmp_path: Path,
) -> None:
    """Nested writes should fail before mutating a scalar-backed path."""
    project_root = tmp_path / "workspace"
    project_settings_dir = project_root / ".henchman"
    project_root.mkdir()
    _write_settings(project_settings_dir, {"ui": {"theme": "light"}})
    before = (project_settings_dir / "settings.yaml").read_text(encoding="utf-8")

    repository = SettingsRepository(project_root=project_root)

    with pytest.raises(
        ValueError,
        match=r"Cannot set nested key beneath non-mapping path: ui\.theme\.accent",
    ):
        repository.set("ui.theme.accent", "blue", scope=SettingsScope.PROJECT)

    assert (project_settings_dir / "settings.yaml").read_text(encoding="utf-8") == before


def test_repository_unset_removes_values_and_cleans_empty_project_file(
    tmp_path: Path,
) -> None:
    """Unsetting the last explicit project value should remove the settings file."""
    project_root = tmp_path / "workspace"
    project_settings_dir = project_root / ".henchman"
    project_root.mkdir()
    _write_settings(
        project_settings_dir,
        {"ui": {"output_style": "json", "theme": "light"}},
    )

    repository = SettingsRepository(project_root=project_root)

    assert repository.unset("ui.theme", scope=SettingsScope.PROJECT) is True
    assert _read_settings(project_settings_dir) == {"ui": {"output_style": "json"}}
    assert repository.unset("ui.output_style", scope=SettingsScope.PROJECT) is True
    assert repository.unset("ui.output_style", scope=SettingsScope.PROJECT) is False
    assert not (project_settings_dir / "settings.yaml").exists()
    assert project_settings_dir.exists()
    assert repository.view(scope=SettingsScope.PROJECT) == {}
