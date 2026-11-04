import copy
from pathlib import Path

import pytest

from henchman.config.settings import ConfigError, load_settings_snapshot


@pytest.mark.parametrize("model", ["session-model", "ambient-model"])
def test_load_settings_snapshot_with_overrides(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, model: str
) -> None:
    """Transient settings win, retain origins and leave later loads/files unchanged."""
    # Create fake home/project
    home = tmp_path / "fake_home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)

    # Remove HENCHMAN_SETTINGS_PATH
    monkeypatch.delenv("HENCHMAN_SETTINGS_PATH", raising=False)

    # Set environment variables
    monkeypatch.setenv("HENCHMAN_PROVIDER", "deepseek")
    monkeypatch.setenv("HENCHMAN_MODEL", "ambient-model")

    # Create actual project/.henchman/settings.yaml
    project = tmp_path / "fake_project"
    project.mkdir()
    project_dir = project / ".henchman"
    project_dir.mkdir()
    settings_file = project_dir / "settings.yaml"
    settings_file.write_text(
        "providers:\n  default: deepseek\n  deepseek:\n    model: file-model",
        encoding="utf-8",
    )

    # Record bytes
    recorded_bytes = settings_file.read_bytes()

    # Define overrides
    overrides = {"providers": {"deepseek": {"model": model}}}
    # Record caller-owned data
    recorded_overrides = copy.deepcopy(overrides)

    snapshot = load_settings_snapshot(project_root=project, overrides=overrides)

    assert snapshot.settings.providers.deepseek["model"] == model
    assert snapshot.origins["providers.deepseek.model"].scope == "session"
    assert snapshot.origins["providers.deepseek.model"].source is None

    # Call without overrides
    snapshot_no_overrides = load_settings_snapshot(project_root=project)

    # Assert resulting model is ambient-model with environment scope
    assert snapshot_no_overrides.settings.providers.deepseek["model"] == "ambient-model"
    assert snapshot_no_overrides.origins["providers.deepseek.model"].scope == "environment"

    # Caller overrides mapping and file bytes unchanged
    assert overrides == recorded_overrides
    assert recorded_bytes == settings_file.read_bytes()


@pytest.mark.parametrize(
    "field, bad_value",
    [
        ("shell_timeout", -1),
        ("sandbox", "unknown"),
    ],
)
def test_load_settings_snapshot_invalid_overrides(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field: str, bad_value: object
) -> None:
    """Invalidly typed overrides should raise ConfigError but leave project file unchanged."""
    # Create fake home/project
    home = tmp_path / "fake_home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)

    # Remove HENCHMAN_SETTINGS_PATH
    monkeypatch.delenv("HENCHMAN_SETTINGS_PATH", raising=False)
    # Remove other variables
    monkeypatch.delenv("HENCHMAN_PROVIDER", raising=False)
    monkeypatch.delenv("HENCHMAN_MODEL", raising=False)

    # Create actual project/.henchman/settings.yaml
    project = tmp_path / "fake_project"
    project.mkdir()
    project_dir = project / ".henchman"
    project_dir.mkdir()
    settings_file = project_dir / "settings.yaml"
    settings_file.write_text(
        "tools: {shell_timeout: 60, sandbox: none}",
        encoding="utf-8",
    )

    # Record bytes
    recorded_bytes = settings_file.read_bytes()

    # Define overrides
    overrides = {"tools": {field: bad_value}}
    # Record caller-owned data
    recorded_overrides = copy.deepcopy(overrides)

    with pytest.raises(ConfigError, match=rf"session overrides.*tools\.{field}"):
        load_settings_snapshot(project_root=project, overrides=overrides)

    # Caller overrides mapping and file bytes unchanged
    assert overrides == recorded_overrides
    assert recorded_bytes == settings_file.read_bytes()
