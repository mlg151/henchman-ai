"""Contracts for values and origins read through the settings repository."""

from pathlib import Path

import pytest

from henchman.config.repository import SettingsRepository, SettingsScope
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


@pytest.mark.parametrize(
    "scope, expected_key, expected_value",
    [
        (SettingsScope.GLOBAL, "providers.deepseek.model", "global-model"),
        (SettingsScope.PROJECT, "providers.deepseek.model", "project-model"),
    ],
)
def test_inspect_explicit_scopes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    scope: SettingsScope,
    expected_key: str,
    expected_value: str,
) -> None:
    home = tmp_path / "home"
    home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(Path, "home", lambda: home)
    for name in ("HENCHMAN_SETTINGS_PATH", "HENCHMAN_PROVIDER", "HENCHMAN_MODEL"):
        monkeypatch.delenv(name, raising=False)

    project = Path(tmp_path / "project")
    project.mkdir()

    monkeypatch.setenv("HENCHMAN_PROVIDER", "deepseek")
    monkeypatch.setenv("HENCHMAN_MODEL", "env-model")

    # home/.henchman/settings.json supplies providers.deepseek.model=global-model
    home_settings = home / ".henchman" / "settings.json"
    home_settings.parent.mkdir(parents=True, exist_ok=True)
    home_settings.write_text(
        '{"providers": {"deepseek": {"model": "global-model"}}}', encoding="utf-8"
    )

    # project/.henchman/settings.json supplies project-model
    project_settings = project / ".henchman" / "settings.json"
    project_settings.parent.mkdir(parents=True, exist_ok=True)
    project_settings.write_text(
        '{"providers": {"deepseek": {"model": "project-model"}}}', encoding="utf-8"
    )

    repo = SettingsRepository(project_root=project)
    entries = repo.inspect(scope=scope)

    assert expected_key in entries
    entry = entries[expected_key]
    assert entry.value == expected_value
    assert entry.origin.scope == scope.value
    assert entry.origin.source is not None
    assert entry.origin.source == str(
        home_settings if scope == SettingsScope.GLOBAL else project_settings
    )

    assert "ui.theme" not in entries
    assert "providers.default" not in entries
