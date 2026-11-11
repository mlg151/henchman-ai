"""Sync exports redact credential echoes without changing source settings."""

import json
from pathlib import Path

import pytest
import yaml

from henchman.config.repository import SettingsRepository, SettingsScope
from henchman.utils.evidence_redaction import REDACTED


@pytest.fixture(autouse=True)
def isolated_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    for name in ("HENCHMAN_PROVIDER", "HENCHMAN_MODEL", "HENCHMAN_SETTINGS_PATH"):
        monkeypatch.delenv(name, raising=False)


def write_settings(root: Path, payload: dict) -> None:
    directory = root / ".henchman"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "settings.yaml").write_text(yaml.safe_dump(payload), encoding="utf-8")


@pytest.mark.parametrize("scope", [SettingsScope.PROJECT, SettingsScope.GLOBAL])
def test_export_redacts_selected_and_effective_scope_secrets(tmp_path: Path, scope: SettingsScope) -> None:
    project = tmp_path / "project"
    project.mkdir()
    old_secret, current_secret = "old-private-canary", "current-private-canary"
    keybindings = {old_secret: current_secret, "c-x": f"{old_secret}/{current_secret}"}
    write_settings(Path.home(), {"providers": {"deepseek": {"api_key": old_secret}},
                                 "ui": {"keybindings": keybindings}})
    write_settings(project, {"providers": {"deepseek": {"api_key": current_secret}},
                             "ui": {"keybindings": keybindings}})
    repository = SettingsRepository(project)
    source = repository.view(scope=scope)
    exported = repository.export_settings(scope=scope)
    rendered = json.dumps(exported)
    assert old_secret not in rendered
    assert current_secret not in rendered
    assert repository.view(scope=scope) == source
    assert "providers" not in exported


def test_export_resolves_known_environment_references_only_for_redaction(tmp_path: Path, monkeypatch) -> None:
    secret = "environment-reference-private-canary"
    monkeypatch.setenv("ORDINARY_REFERENCE_NAME", secret)
    write_settings(tmp_path, {"providers": {"deepseek": {"api_key": "${ORDINARY_REFERENCE_NAME}"}},
                              "ui": {"keybindings": {"c-x": secret, "c-y": "${ORDINARY_REFERENCE_NAME}"}}})
    repository = SettingsRepository(tmp_path)
    exported = repository.export_settings(scope=SettingsScope.PROJECT)
    assert secret not in json.dumps(exported)
    assert exported["ui"]["keybindings"]["c-y"] == "${ORDINARY_REFERENCE_NAME}"
    assert repository.view(scope=SettingsScope.PROJECT)["ui"]["keybindings"]["c-x"] == secret


def test_export_masks_auth_headers_and_marked_dynamic_keys(tmp_path: Path) -> None:
    write_settings(tmp_path, {"ui": {"keybindings": {"password": "marked-private-canary",
                                                      "c-x": "Authorization: Bearer unknown-header-canary"}}})
    exported = SettingsRepository(tmp_path).export_settings(scope=SettingsScope.PROJECT)
    rendered = json.dumps(exported)
    assert "marked-private-canary" not in rendered
    assert "unknown-header-canary" not in rendered
    assert REDACTED in rendered


def test_short_secret_preserves_sync_schema_and_validated_enum_values(tmp_path: Path) -> None:
    ui = {"theme": "dark", "output_style": "json", "output_mode": "plain", "keyboard_mode": "standard",
          "detail_density": "normal", "layout": {"compact_tables": True},
          "reduced_motion": False, "mouse_capture": True, "keybindings": {"c-x": "a"}}
    write_settings(tmp_path, {"providers": {"deepseek": {"api_key": "a"}}, "ui": ui})
    repository = SettingsRepository(tmp_path)
    exported = repository.export_settings(scope=SettingsScope.PROJECT)
    expected = {**ui, "keybindings": {"c-x": REDACTED}}
    assert exported == {"ui": expected}
    destination = SettingsRepository(tmp_path / "destination")
    destination.import_settings(exported, scope=SettingsScope.PROJECT)
    assert destination.view(scope=SettingsScope.PROJECT)["ui"] == expected
    assert repository.view(scope=SettingsScope.PROJECT)["ui"] == ui


def test_invalid_enum_in_raw_scope_is_evidence_not_protocol_identity(tmp_path: Path) -> None:
    secret = "private-invalid-enum-canary"
    write_settings(tmp_path, {"providers": {"deepseek": {"api_key": secret}}, "ui": {"theme": secret}})
    exported = SettingsRepository(tmp_path).export_settings(scope=SettingsScope.PROJECT)
    assert secret not in json.dumps(exported)


@pytest.mark.parametrize("source", ["explicit_file", "runtime_snapshot"])
def test_export_knows_effective_credentials_outside_persisted_scope(tmp_path: Path, monkeypatch, source: str) -> None:
    from henchman.config.schema import Settings
    from henchman.config.settings import SettingsSnapshot

    secret = "effective-only-private-canary"
    write_settings(tmp_path, {"ui": {"keybindings": {"c-x": secret}}})
    settings = Settings(providers={"deepseek": {"api_key": secret}})
    if source == "explicit_file":
        explicit = tmp_path / "selected-settings.yaml"
        explicit.write_text(yaml.safe_dump({"providers": {"deepseek": {"api_key": secret}}}), encoding="utf-8")
        monkeypatch.setenv("HENCHMAN_SETTINGS_PATH", str(explicit))
        repository = SettingsRepository(tmp_path)
    else:
        repository = SettingsRepository(tmp_path, snapshot_provider=lambda: SettingsSnapshot(settings, {}))
    assert secret not in json.dumps(repository.export_settings(scope=SettingsScope.PROJECT))
    assert repository.view()["providers"]["deepseek"]["api_key"] == secret
    assert settings.providers.deepseek["api_key"] == secret
