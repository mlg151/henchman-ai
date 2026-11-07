"""Typed UI settings for quiet/plain output, motion, density, keyboard, mouse, layout."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from henchman.config.schema import LayoutSettings, Settings, UISettings
from henchman.config.settings import ConfigError, load_settings


def test_defaults_preserve_current_behavior() -> None:
    ui = UISettings()

    assert ui.output_mode == "rich"
    assert ui.reduced_motion is False
    assert ui.detail_density == "normal"
    assert ui.keyboard_mode == "standard"
    assert ui.mouse_capture is True
    assert ui.layout.compact_tables is False


def test_defaults_load_through_full_settings() -> None:
    settings = Settings()

    assert settings.ui.output_mode == "rich"
    assert settings.ui.layout.compact_tables is False


@pytest.mark.parametrize("field,value", [
    ("output_mode", "silent"),
    ("detail_density", "everything"),
    ("keyboard_mode", "emacs"),
])
def test_invalid_enum_values_fail_early(field: str, value: str) -> None:
    with pytest.raises(ValidationError):
        UISettings(**{field: value})  # type: ignore[arg-type]


@pytest.mark.parametrize("field", ["output_mode", "detail_density", "keyboard_mode"])
def test_blank_enum_values_fail_early(field: str) -> None:
    with pytest.raises(ValidationError):
        UISettings(**{field: ""})  # type: ignore[arg-type]


def test_unknown_ui_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        UISettings(quiest_mode="quiet")  # type: ignore[call-arg]


def test_layout_unknown_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        LayoutSettings(compact_tabels=True)  # type: ignore[call-arg]


def test_project_settings_roundtrip_new_ui_controls(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    (project / ".henchman").mkdir(parents=True)
    (project / ".henchman" / "settings.yaml").write_text(
        "ui:\n"
        "  output_mode: quiet\n"
        "  reduced_motion: true\n"
        "  detail_density: compact\n"
        "  keyboard_mode: vim\n"
        "  mouse_capture: false\n"
        "  layout:\n"
        "    compact_tables: true\n",
        encoding="utf-8",
    )

    settings = load_settings(project_root=project)

    assert settings.ui.output_mode == "quiet"
    assert settings.ui.reduced_motion is True
    assert settings.ui.detail_density == "compact"
    assert settings.ui.keyboard_mode == "vim"
    assert settings.ui.mouse_capture is False
    assert settings.ui.layout.compact_tables is True


def test_invalid_project_ui_settings_fail_with_field_attribution(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    (project / ".henchman").mkdir(parents=True)
    (project / ".henchman" / "settings.yaml").write_text(
        "ui:\n  output_mode: shouty\n",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="ui.output_mode"):
        load_settings(project_root=project)


def test_sync_payload_roundtrip_includes_new_nonsecret_ui_controls() -> None:
    from henchman.config.repository import _build_sync_payload, _normalize_sync_payload

    source = {
        "ui": {
            "output_style": "concise",
            "theme": "dark",
            "output_mode": "plain",
            "reduced_motion": True,
            "detail_density": "detailed",
            "keyboard_mode": "vim",
            "mouse_capture": False,
            "layout": {"compact_tables": True},
            "show_line_numbers": False,  # not sync-scoped: stays local
        },
    }

    payload = _build_sync_payload(source)

    assert payload == {
        "ui": {
            "output_style": "concise",
            "theme": "dark",
            "output_mode": "plain",
            "reduced_motion": True,
            "detail_density": "detailed",
            "keyboard_mode": "vim",
            "mouse_capture": False,
            "layout": {"compact_tables": True},
        },
    }
    assert _normalize_sync_payload(payload) == payload


def test_sync_payload_rejects_invalid_nested_layout() -> None:
    from henchman.config.repository import _normalize_sync_payload

    with pytest.raises(ValueError, match="layout"):
        _normalize_sync_payload({"ui": {"layout": {"bogus": True}}})
    with pytest.raises(ValueError, match="layout"):
        _normalize_sync_payload({"ui": {"layout": "sideways"}})


def test_sync_payload_rejects_secret_like_ui_values_when_secret_named() -> None:
    from henchman.config.repository import _normalize_sync_payload

    with pytest.raises(ValueError, match="Unsupported sync payload ui keys"):
        _normalize_sync_payload({"ui": {"api_key": "sk-secret"}})
