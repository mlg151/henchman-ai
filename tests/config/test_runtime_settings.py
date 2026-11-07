"""Live settings retain values, object identities, and honest provenance."""

import traceback
from pathlib import Path

import pytest

from henchman.config.repository import SettingsRepository, SettingsScope
from henchman.config.runtime import RuntimeSettingsState
from henchman.config.schema import Settings
from henchman.config.settings import ConfigError, SettingOrigin, load_settings_snapshot


@pytest.fixture
def state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> RuntimeSettingsState:
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    for key in ("HENCHMAN_PROVIDER", "HENCHMAN_MODEL", "HENCHMAN_SETTINGS_PATH"):
        monkeypatch.delenv(key, raising=False)
    directory = tmp_path / ".henchman"
    directory.mkdir()
    (directory / "settings.yaml").write_text(
        "providers: {default: ollama, ollama: {model: saved-model}}\n"
        "context: {max_tokens: 10000}\n", encoding="utf-8",
    )
    return RuntimeSettingsState(load_settings_snapshot(project_root=tmp_path))


def test_commit_preserves_shared_models_and_detaches_snapshots(state):
    settings, context, providers = state.settings, state.settings.context, state.settings.providers
    old = state.snapshot()
    update = state.prepare({"context": {"max_tokens": 5000}})
    assert state.settings.context.max_tokens == 10000

    state.commit(update)

    assert state.settings is settings
    assert state.settings.context is context
    assert state.settings.providers is providers
    assert context.max_tokens == 5000
    assert old.settings.context.max_tokens == 10000
    snapshot = state.snapshot()
    assert snapshot.origins["context.max_tokens"] == SettingOrigin("session")
    assert snapshot.origins["providers.default"].scope == "project"
    snapshot.settings.context.max_tokens = 77
    snapshot.origins.clear()
    assert state.settings.context.max_tokens == 5000
    assert state.snapshot().origins["context.max_tokens"].scope == "session"


def test_equal_override_still_has_session_origin(state):
    state.update({"context": {"max_tokens": 10000}})
    assert state.snapshot().origins["context.max_tokens"].scope == "session"


def test_invalid_update_leaves_values_and_origins_unchanged(state):
    before = state.snapshot()
    with pytest.raises(ConfigError, match="context.max_tokens"):
        state.update({"context": {"max_tokens": -1}})
    assert state.snapshot() == before


def test_invalid_override_diagnostics_do_not_echo_uncommitted_secrets(state):
    secret = "invalid-uncommitted-canary"
    with pytest.raises(ConfigError) as caught:
        state.update({"ui": {"password": secret}})
    diagnostic = "".join(traceback.format_exception(caught.value))
    assert "ui.password" in diagnostic
    assert secret not in diagnostic


def test_stale_prepared_change_cannot_erase_newer_state(state):
    pending = state.prepare({"context": {"max_tokens": 5000}})
    state.update({"ui": {"mcp_logging": True}})
    with pytest.raises(ValueError, match="stale"):
        state.commit(pending)
    assert state.settings.ui.mcp_logging
    assert state.settings.context.max_tokens == 10000


def test_explicit_settings_have_session_origins_without_disk_claims():
    settings = Settings(context={"max_tokens": 10000})
    state = RuntimeSettingsState.from_settings(settings)
    assert state.settings is settings
    assert state.snapshot().origins["context.max_tokens"] == SettingOrigin("session")
    assert state.snapshot().origins["context.compaction_threshold"].scope == "default"


def test_repository_live_snapshot_is_separate_from_file_and_environment(state, tmp_path, monkeypatch):
    repository = SettingsRepository(tmp_path, snapshot_provider=state.snapshot)
    state.update({"providers": {"ollama": {"model": "session-model"}}})
    monkeypatch.setenv("HENCHMAN_MODEL", "environment-model")
    repository.set("providers.ollama.model", "new-file-model", scope=SettingsScope.PROJECT)

    assert repository.get("providers.ollama.model") == "session-model"
    assert repository.inspect()["providers.ollama.model"].origin.scope == "session"
    assert repository.view()["providers"]["ollama"]["model"] == "session-model"
    assert repository.get("providers.ollama.model", scope=SettingsScope.PROJECT) == "new-file-model"
    assert repository.inspect(scope=SettingsScope.PROJECT)["providers.ollama.model"].origin.scope == "project"
    assert SettingsRepository(tmp_path).get("providers.ollama.model") == "environment-model"


def test_mutable_override_is_detached_before_commit(state):
    changes = {"providers": {"ollama": {"model": "selected"}}}
    prepared = state.prepare(changes)
    changes["providers"]["ollama"]["model"] = "mutated"
    state.commit(prepared)
    assert state.settings.providers.ollama["model"] == "selected"
