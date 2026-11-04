from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from henchman.cli.commands.config_command import create_config_command


@pytest.mark.parametrize(
    "variant, key, origin",
    [
        ("defaults", "ui.keybindings", "default"),
        ("project", "providers.deepseek", "project"),
        ("literal", "ui.keybindings.ctrl+.", "project"),
        ("literal", "ui.style_overrides..chat-pane", "project"),
        ("literal", "ui.theme", "default"),
    ],
)
def test_config_group_values(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    variant: str,
    key: str,
    origin: str,
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / ".henchman").mkdir()

    monkeypatch.setenv("HENCHMAN_SETTINGS_PATH", "")
    monkeypatch.setenv("HENCHMAN_PROVIDER", "")
    monkeypatch.setenv("HENCHMAN_MODEL", "")
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")

    (tmp_path / "home").mkdir()

    if variant == "project":
        settings = {
            "providers": {"deepseek": {"model": "file-model", "api_key": "hidden-test-key"}}
        }
        settings_file = project_root / ".henchman" / "settings.yaml"
        with open(settings_file, "w", encoding="utf-8") as f:
            yaml.safe_dump(settings, f)
    elif variant == "literal":
        settings = {
            "ui": {
                "keybindings": {"ctrl+.": "abort"},
                "style_overrides": {".chat-pane": "bold"},
            }
        }
        settings_file = project_root / ".henchman" / "settings.yaml"
        with open(settings_file, "w", encoding="utf-8") as f:
            yaml.safe_dump(settings, f)

    command = create_config_command(project_root=project_root)
    result = CliRunner().invoke(command, ["get", key])

    assert result.exit_code == 0, (result.output, result.exception)
    parse = yaml.safe_load(result.output)
    assert parse["key"] == key
    assert parse["requested_scope"] == "merged"
    assert parse["resolved_scope"] == origin

    if variant == "defaults":
        assert parse["value"] == {"c-c": "abort", "c-d": "exit"}
    elif variant == "project":
        assert parse["value"]["model"] == "file-model"
        assert isinstance(parse["value"]["api_key"], str)
        assert parse["value"]["api_key"] not in ("hidden-test-key", "")
        assert "hidden-test-key" not in result.output
    elif variant == "literal":
        if "ctrl+." in key:
            assert parse["value"] == "abort"
        elif "..chat-pane" in key:
            assert parse["value"] == "bold"
        elif "ui.theme" in key:
            assert parse["value"] == "dark"
