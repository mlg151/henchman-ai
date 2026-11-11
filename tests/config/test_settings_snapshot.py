"""Values and provenance from the shared settings loader."""

from pathlib import Path

import pytest

from henchman.config.settings import (
    ConfigError,
    SettingOrigin,
    load_settings,
    load_settings_snapshot,
)


@pytest.fixture(autouse=True)
def isolate_settings_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep real user configuration and inherited overrides out of each case."""
    home = tmp_path / "isolated-home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    for name in ("HENCHMAN_PROVIDER", "HENCHMAN_MODEL", "HENCHMAN_SETTINGS_PATH"):
        monkeypatch.delenv(name, raising=False)


def test_load_settings_snapshot_default_origins(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mock_home = tmp_path / "mock_home"
    mock_home.mkdir()
    monkeypatch.setattr("pathlib.Path.home", lambda: mock_home)

    mock_project = tmp_path / "mock_project"
    mock_project.mkdir()

    snapshot = load_settings_snapshot(project_root=mock_project)

    assert snapshot.origins["providers.default"] is not None
    assert snapshot.origins["providers.default"].scope == "default"
    assert snapshot.origins["providers.default"].source is None


def test_load_settings_snapshot_global_project_overlay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:

    mock_home = tmp_path / "mock_home"
    mock_home.mkdir()
    user_dir = mock_home / ".henchman"
    user_dir.mkdir()

    user_settings_file = user_dir / "settings.yaml"
    user_settings_file.write_text(
        "tools: {auto_approve_read: true}\nui: {show_line_numbers: false}", encoding="utf-8"
    )

    project_root = tmp_path / "mock_project"
    project_root.mkdir()
    project_dir = project_root / ".henchman"
    project_dir.mkdir()
    project_settings_file = project_dir / "settings.yaml"
    project_settings_file.write_text(
        "tools: {auto_approve_read: true}\nui: {theme: monokai}", encoding="utf-8"
    )

    monkeypatch.setattr("pathlib.Path.home", lambda: mock_home)

    snapshot = load_settings_snapshot(project_root=project_root)

    assert snapshot.origins["tools.auto_approve_read"].scope == "project"
    assert snapshot.origins["ui.theme"].scope == "project"
    assert snapshot.settings.ui.theme == "monokai"
    assert snapshot.settings.ui.show_line_numbers is False
    assert snapshot.origins["ui.show_line_numbers"] == SettingOrigin(
        "global", str(user_settings_file)
    )
    assert snapshot.origins["tools.auto_approve_read"].source == str(project_settings_file)


def test_load_settings_snapshot_env_overrides(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:

    mock_home = tmp_path / "mock_home"
    mock_home.mkdir()
    monkeypatch.setattr("pathlib.Path.home", lambda: mock_home)

    project_root = tmp_path / "mock_project"
    project_root.mkdir()
    project_dir = project_root / ".henchman"
    project_dir.mkdir()

    project_settings_file = project_dir / "settings.yaml"
    project_settings_file.write_text(
        """
providers:
  openai:
    api_key: "secret"
  deepseek:
    model: "custom-model"
    api_key: "secret"
    """,
        encoding="utf-8",
    )

    monkeypatch.setenv("HENCHMAN_PROVIDER", "deepseek")
    monkeypatch.setenv("HENCHMAN_MODEL", "custom-model")

    snapshot = load_settings_snapshot(project_root=project_root)

    assert snapshot.settings.providers.default == "deepseek"
    assert snapshot.origins["providers.default"] == SettingOrigin(
        "environment", "HENCHMAN_PROVIDER"
    )
    assert snapshot.settings.providers.deepseek["model"] == "custom-model"
    assert snapshot.origins["providers.deepseek.model"].scope == "environment"
    assert snapshot.origins["providers.deepseek.model"].source == "HENCHMAN_MODEL"

    assert snapshot.origins["providers.openai.api_key"] == SettingOrigin(
        "project", str(project_settings_file)
    )


def test_load_settings_snapshot_explicit_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    explicit_file = tmp_path / "explicit_settings.yaml"
    explicit_file.write_text("tools: {auto_approve_read: true}", encoding="utf-8")

    monkeypatch.setenv("HENCHMAN_SETTINGS_PATH", str(explicit_file))

    snapshot = load_settings_snapshot(project_root=tmp_path / "mock_project")

    assert snapshot.origins["tools.auto_approve_read"].scope == "file"
    assert snapshot.origins["tools.auto_approve_read"].source == str(explicit_file)


def test_load_settings_snapshot_nonexistent_explicit_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    nonexistent_file = tmp_path / "nonexistent.yaml"

    mock_home = tmp_path / "mock_home"
    mock_home.mkdir()
    user_dir = mock_home / ".henchman"
    user_dir.mkdir()
    user_settings_file = user_dir / "settings.yaml"
    user_settings_file.write_text("ui: {theme: solarized-dark}", encoding="utf-8")

    monkeypatch.setattr("pathlib.Path.home", lambda: mock_home)
    monkeypatch.setenv("HENCHMAN_SETTINGS_PATH", str(nonexistent_file))

    project_root = tmp_path / "mock_project"
    project_dir = project_root / ".henchman"
    project_dir.mkdir(parents=True)
    project_file = project_dir / "settings.yaml"
    project_file.write_text("ui: {output_style: concise}", encoding="utf-8")
    snapshot = load_settings_snapshot(project_root=project_root)

    assert snapshot.origins["ui.output_style"] == SettingOrigin("project", str(project_file))
    assert snapshot.settings.ui.output_style == "concise"
    assert snapshot.origins["ui.theme"].scope == "global"
    assert snapshot.origins["ui.theme"].source == str(user_settings_file)


def test_load_settings_snapshot_home_project_duplicate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:

    project_root = tmp_path / "mock_project"
    project_root.mkdir()

    monkeypatch.setattr("pathlib.Path.home", lambda: project_root)

    project_dir = project_root / ".henchman"
    project_dir.mkdir()
    settings_file = project_dir / "settings.yaml"
    settings_file.write_text("ui: {theme: solarized-dark}", encoding="utf-8")

    snapshot = load_settings_snapshot(project_root=project_root)

    assert snapshot.origins["ui.theme"].scope == "project"


def test_load_settings_snapshot_wrapper_equals_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:

    mock_home = tmp_path / "mock_home"
    mock_home.mkdir()
    monkeypatch.setattr("pathlib.Path.home", lambda: mock_home)

    project_root = tmp_path / "mock_project"
    project_root.mkdir()
    project_dir = project_root / ".henchman"
    project_dir.mkdir()

    project_settings_file = project_dir / "settings.yaml"
    project_settings_file.write_text(
        "ui: {theme: monokai}\ntools: {auto_approve_read: true}", encoding="utf-8"
    )

    snapshot = load_settings_snapshot(project_root=project_root)
    settings = load_settings(project_root=project_root)

    assert settings == snapshot.settings
    assert snapshot.settings.ui.theme == "monokai"
    assert snapshot.settings.tools.auto_approve_read is True


def test_load_settings_snapshot_invalid_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:

    mock_home = tmp_path / "mock_home"
    mock_home.mkdir()
    monkeypatch.setattr("pathlib.Path.home", lambda: mock_home)

    project_root = tmp_path / "mock_project"
    project_root.mkdir()
    project_dir = project_root / ".henchman"
    project_dir.mkdir()

    project_settings_file = project_dir / "settings.yaml"
    project_settings_file.write_text("ui: {theme: non-existent}", encoding="utf-8")

    with pytest.raises(ConfigError) as excinfo:
        load_settings_snapshot(project_root=project_root)

    assert "Invalid settings" in str(excinfo.value)
