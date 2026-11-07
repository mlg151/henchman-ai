"""Provider switches and inspection share one live settings snapshot."""

from io import StringIO
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from rich.console import Console

from henchman.cli.commands import CommandContext
from henchman.cli.commands.model import ModelCommand
from henchman.cli.provider_switch import switch_runtime_provider
from henchman.config.runtime import RuntimeSettingsState
from henchman.config.schema import Settings
from henchman.core.agent import Agent
from henchman.providers.base import Message
from henchman.providers.ollama import OllamaProvider


def runtime():
    settings = Settings(providers={"default": "ollama", "ollama": {"model": "old"}})
    state = RuntimeSettingsState.from_settings(settings)
    provider = OllamaProvider(model="old")
    agent = Agent(provider)
    agent.messages.append(Message(role="user", content="Preserve conversation"))
    return SimpleNamespace(settings=settings, settings_state=state, provider=provider, agent=agent)


def test_switch_records_provider_model_and_context_session_values():
    app = runtime()
    history, settings, context = app.agent.messages, app.settings, app.settings.context
    replacement = OllamaProvider(model="selected")

    switch_runtime_provider(app, replacement, provider_name="ollama", model_name="selected", context_length=9000)

    assert app.settings.providers.default == "ollama"
    assert app.settings.providers.ollama["model"] == "selected"
    assert app.settings.context.max_tokens == 9000
    assert app.settings is settings and app.settings.context is context
    snapshot = app.settings_state.snapshot()
    for key in ("providers.default", "providers.ollama.model", "context.max_tokens"):
        assert snapshot.origins[key].scope == "session"
    assert app.agent.messages is history
    assert app.agent.model == "selected"


def test_failed_pool_preparation_preserves_snapshot_and_provider():
    app = runtime()
    app.orchestrator = SimpleNamespace(pool=Mock(), settings=app.settings)
    app.orchestrator.pool.set_default_provider.side_effect = ValueError("invalid specialist options")
    before = app.settings_state.snapshot()
    old = app.provider

    with pytest.raises(ValueError, match="invalid specialist"):
        switch_runtime_provider(app, OllamaProvider(model="selected"), provider_name="ollama", model_name="selected", context_length=9000)

    assert app.settings_state.snapshot() == before
    assert app.provider is old and app.agent.provider is old


def test_cached_and_future_agents_share_live_settings_after_switch_and_resume(tmp_path, monkeypatch):
    from pathlib import Path

    from henchman.cli.repl import Repl
    from henchman.core.session import Session, SessionMessage

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    settings = Settings(providers={"default": "ollama", "ollama": {"model": "old"}})
    repl = Repl(OllamaProvider(model="old"), settings=settings, console=Console(file=StringIO()))
    cached = repl.orchestrator.pool.get_agent("explorer")
    provider_settings = repl.orchestrator.pool.provider_settings
    switch_runtime_provider(repl, OllamaProvider(model="new"), provider_name="ollama", model_name="new", context_length=9000)

    session = Session(id="resumed", project_hash="project", started="now", last_updated="now")
    session.messages.append(SessionMessage(role="user", content="Restored conversation"))
    state = repl.settings_state
    snapshot = state.snapshot()
    repl.set_session(session)

    assert repl.settings_state is state
    assert state.snapshot() == snapshot
    assert repl.settings is repl.orchestrator.settings is settings
    assert repl.orchestrator.pool.provider_settings is provider_settings is settings.providers
    assert repl.agent.messages[-1].content == "Restored conversation"
    for agent in (cached, repl.orchestrator.pool.get_agent("engineer"), repl.agent):
        assert agent.model == "new"
        assert agent.max_tokens == 6750


def test_direct_repl_injected_provider_records_effective_selection(tmp_path, monkeypatch):
    from pathlib import Path

    from henchman.cli.repl import Repl

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    repl = Repl(OllamaProvider(model="explicit-model"), console=Console(file=StringIO()))
    snapshot = repl.settings_state.snapshot()
    assert snapshot.settings.providers.default == "ollama"
    assert snapshot.settings.providers.ollama["model"] == "explicit-model"
    assert snapshot.origins["providers.default"].scope == "session"
    assert snapshot.origins["providers.ollama.model"].scope == "session"


def test_provider_constructor_default_is_inspected_without_claiming_session_override():
    from henchman.cli.provider_switch import capture_startup_provider_settings
    from henchman.config.settings import SettingOrigin, SettingsSnapshot

    settings = Settings(providers={"default": "ollama"})
    state = RuntimeSettingsState(SettingsSnapshot(settings, {"providers.default": SettingOrigin("project")}))
    provider = OllamaProvider()
    capture_startup_provider_settings(state, provider)
    snapshot = state.snapshot()
    assert snapshot.settings.providers.ollama["model"] == provider.default_model
    assert snapshot.origins["providers.ollama.model"].scope == "default"
    assert snapshot.origins["providers.default"].scope == "project"


def test_configured_default_model_alias_retains_its_file_origin():
    from henchman.cli.provider_switch import capture_startup_provider_settings
    from henchman.config.settings import SettingOrigin, SettingsSnapshot
    from henchman.providers.openai_compat import OpenAICompatibleProvider

    settings = Settings(providers={"default": "openai_compat", "openai_compat": {"default_model": "configured-alias"}})
    origin = SettingOrigin("project", "/project/.henchman/settings.yaml")
    state = RuntimeSettingsState(SettingsSnapshot(settings, {"providers.openai_compat.default_model": origin}))
    provider = OpenAICompatibleProvider(api_key="", base_url="http://localhost:19877/v1", default_model="configured-alias")
    provider._accounting_provider_name = "openai_compat"
    capture_startup_provider_settings(state, provider)
    assert state.snapshot().origins["providers.openai_compat.model"] == origin


def test_provider_fallback_does_not_erase_configured_selection():
    from henchman.cli.provider_switch import capture_startup_provider_settings
    from henchman.cli.textual_mixins import _NullProvider

    state = RuntimeSettingsState.from_settings(Settings(providers={"default": "ollama"}))
    before = state.snapshot()
    capture_startup_provider_settings(state, _NullProvider())
    assert state.snapshot() == before


@pytest.mark.asyncio
async def test_model_command_records_explicit_same_value_origin_and_actual_model():
    app = runtime()
    output = StringIO()
    ctx = CommandContext(console=Console(file=output), agent=app.agent, repl=app,
                         args=["set", "ollama", "new", "--context-length", "7000"])
    await ModelCommand().execute(ctx)
    assert app.settings.providers.ollama["model"] == "new"
    assert app.settings.context.max_tokens == 7000
    assert "(session)" in output.getvalue()
