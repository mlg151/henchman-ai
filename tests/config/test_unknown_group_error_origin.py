import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from henchman.config.settings import ConfigError, load_settings


@pytest.fixture
def temp_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a temporary home directory."""
    home = tmp_path / "home"
    home.mkdir()
    # Patch Path.home with monkeypatch as requested
    monkeypatch.setattr("pathlib.Path.home", lambda: home)
    return home


@pytest.fixture
def temp_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create and change to a temporary working directory."""
    cwd = tmp_path / "workspace"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    return cwd


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Remove HENCHMAN_ environment variables."""
    for key in list(os.environ.keys()):
        if key.startswith("HENCHMAN_"):
            monkeypatch.delenv(key, raising=False)
    yield


@pytest.mark.usefixtures("clean_env")
@pytest.mark.parametrize(
    "settings_data_home, settings_data_project, expect_fail",
    [
        # Case 1: Unknown global group raises ConfigError naming global path.
        # Home file has unknown_group.enabled=true. Project file has ui.theme=light.
        (
            """
unknown_group:
  enabled: true
""",
            """
ui:
  theme: light
""",
            True,
        ),
        # Case 2: Valid global tools.shell_timeout=45 plus project ui.theme=light loads successfully.
        (
            """
tools:
  shell_timeout: 45
""",
            """
ui:
  theme: light
""",
            False,
        ),
    ],
)
def test_unknown_group_error_origin(
    temp_home: Path,
    temp_cwd: Path,
    settings_data_home: str,
    settings_data_project: str,
    expect_fail: bool,
) -> None:
    # Create global (home) settings
    henchman_dir_home = temp_home / ".henchman"
    henchman_dir_home.mkdir()
    global_settings_path = henchman_dir_home / "settings.yaml"
    global_settings_path.write_text(settings_data_home, encoding="utf-8")

    # Create project settings
    henchman_dir_project = temp_cwd / ".henchman"
    henchman_dir_project.mkdir()
    project_settings_path = henchman_dir_project / "settings.yaml"
    project_settings_path.write_text(settings_data_project, encoding="utf-8")

    if expect_fail:
        # Should fail and identify the global source file
        with pytest.raises(ConfigError) as excinfo:
            load_settings()
        # The error message should contain the global settings path, NOT the project settings path.
        assert "unknown_group" in str(excinfo.value)
        assert str(global_settings_path) in str(excinfo.value)
        assert str(project_settings_path) not in str(excinfo.value)
    else:
        # Should succeed
        settings = load_settings()
        assert settings.tools.shell_timeout == 45
        assert settings.ui.theme == "light"
