"""Contracts for values and origins read through the settings repository."""

from pathlib import Path

import pytest

from henchman.config.repository import SettingsRepository
from henchman.config.settings import SettingsSnapshot, load_settings_snapshot


def test_inspect_default_value_and_origin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)
    for name in ("HENCHMAN_SETTINGS_PATH", "HENCHMAN_PROVIDER", "HENCHMAN_MODEL"):
        monkeypatch.delenv(name, raising=False)

    project = Path(tmp_path / "project")
    project.mkdir()

    repo = SettingsRepository(project_root=project)
    entries = repo.inspect()

    assert entries["ui.theme"].value == "dark"
    assert entries["ui.theme"].origin.scope == "default"
    assert entries["ui.theme"].origin.source is None
    assert "ui.nonexistent" not in entries


def test_inspect_uses_one_snapshot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)
    for name in ("HENCHMAN_SETTINGS_PATH", "HENCHMAN_PROVIDER", "HENCHMAN_MODEL"):
        monkeypatch.delenv(name, raising=False)

    project = Path(tmp_path / "project")
    project.mkdir()

    monkeypatch.setenv("HENCHMAN_PROVIDER", "deepseek")
    monkeypatch.setenv("HENCHMAN_MODEL", "first-model")

    snapshot = load_settings_snapshot(project_root=project)

    monkeypatch.setenv("HENCHMAN_MODEL", "later-model")

    calls: list[Path | None] = []

    def mocked_load_settings_snapshot(project_root: Path | None = None) -> SettingsSnapshot:
        calls.append(project_root)
        return snapshot

    monkeypatch.setattr(
        "henchman.config.repository.load_settings_snapshot", mocked_load_settings_snapshot
    )

    repo = SettingsRepository(project_root=project)
    entries = repo.inspect()

    assert calls == [project]
    assert "providers.deepseek.model" in entries
    assert entries["providers.deepseek.model"].value == "first-model"
    assert entries["providers.deepseek.model"].origin.scope == "environment"
    assert entries["providers.deepseek.model"].origin.source == "HENCHMAN_MODEL"
