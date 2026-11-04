"""Contracts for values and origins read through the settings repository."""

from pathlib import Path

import pytest

from henchman.config.repository import SettingsRepository


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

