import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from henchman.config import ConfigError, UISettings, load_settings
from henchman.config.repository import SettingsRepository, SettingsScope


def test_ui_settings_forbid_extra() -> None:
    # Should raise ValidationError because 'output_stlye' (misspelled) is extra
    with pytest.raises(ValidationError) as excinfo:
        UISettings(output_stlye="minimal")

    # Check that it identifies 'output_stlye' as the extra field
    errors = excinfo.value.errors()
    assert len(errors) == 1
    assert errors[0]["type"] == "extra_forbidden"
    assert errors[0]["loc"] == ("output_stlye",)


def test_repository_forbid_extra_on_set(tmp_path: Path) -> None:
    # Create a dummy project root
    project_root = tmp_path / "project"
    project_root.mkdir()

    repo = SettingsRepository(project_root=project_root)

    # First, set a valid field
    repo.set("ui.theme", "light", scope=SettingsScope.PROJECT)

    # The file should exist now
    settings_dir = project_root / ".henchman"
    assert settings_dir.exists()
    settings_file = settings_dir / "settings.yaml"
    assert settings_file.exists()

    original_bytes = settings_file.read_bytes()

    # Now, try to set an invalid field
    with pytest.raises(ValidationError):
        repo.set("ui.output_stlye", "minimal", scope=SettingsScope.PROJECT)

    # Verify the file remains unchanged
    assert settings_file.read_bytes() == original_bytes


def test_load_settings_rejects_extra_field(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Create a temporary JSON file with an extra field
    temp_json = tmp_path / "settings.json"
    data = {"ui": {"theme": "light", "output_stlye": "minimal"}}  # Extra field
    temp_json.write_text(json.dumps(data), encoding="utf-8")

    monkeypatch.setenv("HENCHMAN_SETTINGS_PATH", str(temp_json))
    with pytest.raises(ConfigError) as exc_info:
        load_settings()
    assert "ui.output_stlye" in str(exc_info.value)


def test_ui_settings_accepts_valid_mappings() -> None:
    # Ensure that valid mappings are still accepted
    data = {"theme": "light", "keybindings": {"c-x": "abort"}, "style_overrides": {"user": "cyan"}}
    settings = UISettings(**data)
    assert settings.theme == "light"
    assert settings.keybindings["c-x"] == "abort"
    assert settings.style_overrides["user"] == "cyan"
