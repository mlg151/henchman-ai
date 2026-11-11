from pathlib import Path
from typing import Any

import pytest

from henchman.config.settings import ConfigError, load_settings_snapshot


@pytest.mark.parametrize(
    "payload, valid, _id",
    [
        ({"tools.shell_timeout": 7}, False, "root-dot"),
        ({"tools": {"shell_timout": 7}}, False, "tool-typo"),
        ({"context": {"max_token": 1024}}, False, "context-typo"),
        ({"providers": {"defaut": "deepseek"}}, False, "provider-typo"),
        ({"unknown_group": {"enabled": True}}, False, "unknown-group"),
        (
            {
                "providers": {
                    "deepseek": {
                        "model": "sample-model",
                        "extra_headers": {"X-Custom.Header": "ok"},
                    }
                },
                "ui": {
                    "keybindings": {"ctrl+x": "abort"},
                    "style_overrides": {"chat-pane": "bold"},
                },
            },
            True,
            "dynamic-maps",
        ),
    ],
)
def test_strict_settings_loading(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    payload: dict[str, Any],
    valid: bool,
    _id: str,
) -> None:
    # Setup fake home/project dirs
    home_dir = tmp_path / ".home"
    home_dir.mkdir()
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    monkeypatch.setattr(Path, "home", lambda: home_dir)

    # Remove environment variables
    monkeypatch.delenv("HENCHMAN_SETTINGS_PATH", raising=False)
    monkeypatch.delenv("HENCHMAN_PROVIDER", raising=False)
    monkeypatch.delenv("HENCHMAN_MODEL", raising=False)

    if valid:
        # For valid branch assert actual provider extra_headers dict exactly {"X-Custom.Header":"ok"},
        # keybindings ctrl+x abort, style_overrides chat-pane bold.
        snapshot = load_settings_snapshot(project_root=project_dir, overrides=payload)
        settings = snapshot.settings

        assert settings.providers.deepseek["extra_headers"] == {"X-Custom.Header": "ok"}
        assert settings.ui.keybindings["ctrl+x"] == "abort"
        assert settings.ui.style_overrides["chat-pane"] == "bold"
    else:
        # For invalid branch with pytest.raises(ConfigError,match="Invalid settings") around actual loader, no fake raises.
        with pytest.raises(ConfigError, match="Invalid settings"):
            load_settings_snapshot(project_root=project_dir, overrides=payload)
