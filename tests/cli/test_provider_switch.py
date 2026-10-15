"""Offline regressions for in-place runtime provider changes."""

from io import StringIO
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from rich.console import Console

from henchman.cli.commands import CommandContext
from henchman.cli.commands.model import ModelCommand
from henchman.cli.textual_mixins import _ProviderMixin
from henchman.config.schema import ProviderSettings, Settings
from henchman.core.agent import Agent
from henchman.providers.base import Message
from henchman.providers.ollama import OllamaProvider
from tests.providers.stream_helpers import SDKResponse


@pytest.mark.parametrize("max_tokens,expected", [(0, 6963), (1234, 1234)])
def test_agent_switch_updates_model_and_context_without_losing_history(max_tokens, expected):
    agent = Agent(OllamaProvider(model="llama3.2"), max_tokens=max_tokens)
    agent.messages.append(Message(role="user", content="Keep this history"))
    history = agent.messages
    tools = agent.tool_registry
    replacement = OllamaProvider(model="gpt-4")

    agent.set_provider(replacement)

    assert agent.provider is replacement
    assert agent.model == "gpt-4"
    assert agent.max_tokens == expected
    assert agent.messages is history
    assert agent.messages[0].content == "Keep this history"
    assert agent.tool_registry is tools


def make_runtime():
    provider = OllamaProvider(model="llama3.2")
    agent = Agent(provider)
    agent.messages.append(Message(role="user", content="Existing conversation"))
    settings = Settings(providers=ProviderSettings(ollama={
        "model": "mistral", "base_url": "http://localhost:19876/v1",
    }))
    return SimpleNamespace(
        provider=provider, agent=agent, settings=settings,
        output_handler=SimpleNamespace(provider=provider),
        command_processor=SimpleNamespace(provider=provider),
        tool_executor=SimpleNamespace(provider=provider),
        core_context=SimpleNamespace(provider=provider),
        session_manager=object(), tool_registry=agent.tool_registry, plugins=object(),
    )


@pytest.mark.asyncio
async def test_slash_switch_honors_saved_local_settings_and_updates_runtime(monkeypatch):
    monkeypatch.delenv("HENCHMAN_API_KEY", raising=False)
    runtime = make_runtime()
    original_history = runtime.agent.messages
    output = StringIO()
    ctx = CommandContext(console=Console(file=output), session=None, agent=runtime.agent,
                         tool_registry=runtime.tool_registry, repl=runtime,
                         args=["set", "ollama"])

    await ModelCommand().execute(ctx)

    assert runtime.provider.default_model == "mistral"
    assert runtime.provider.base_url == "http://localhost:19876/v1"
    assert runtime.agent.model == "mistral"
    assert runtime.agent.messages is original_history
    for component in (runtime.agent, runtime.output_handler, runtime.command_processor,
                      runtime.tool_executor, runtime.core_context):
        assert component.provider is runtime.provider
    assert "Configured" in output.getvalue()
    assert "Connected" not in output.getvalue()
    assert "Testing" not in output.getvalue()
    assert "No API key" not in output.getvalue()


class ProviderApp(_ProviderMixin):
    """Minimal host retaining the production provider switch behavior."""

    def __init__(self):
        self.__dict__.update(vars(make_runtime()))
        self._initialize_core_components = Mock()
        self._announce_provider_switch = Mock()
        self._show_provider_error = Mock()


def test_tui_switch_keeps_core_state_and_uses_saved_settings():
    app = ProviderApp()
    retained = {name: getattr(app, name) for name in (
        "agent", "core_context", "session_manager", "tool_registry", "plugins",
    )}
    history = app.agent.messages

    app._switch_provider("ollama")

    assert app.provider.default_model == "mistral"
    assert app.agent.model == "mistral"
    assert app.agent.messages is history
    assert app.core_context.provider is app.provider
    assert all(getattr(app, name) is value for name, value in retained.items())
    app._initialize_core_components.assert_not_called()
    app._show_provider_error.assert_not_called()


def test_tui_invalid_provider_leaves_runtime_unchanged():
    app = ProviderApp()
    original = app.provider
    history = app.agent.messages

    app._switch_provider("does-not-exist")

    assert app.provider is original
    assert app.agent.provider is original
    assert app.core_context.provider is original
    assert app.agent.messages is history
    app._show_provider_error.assert_called_once()


@pytest.mark.asyncio
async def test_slash_switch_preserves_cached_specialists_and_their_overrides():
    from henchman.agents.pool import AgentPool
    from henchman.config.schema import AgentConfig
    from henchman.core.eventbus import EventBus
    from henchman.providers import get_default_registry

    runtime = make_runtime()
    configs = {
        role: AgentConfig(name=role, role=role, description=role, tools=["read_file"], **options)
        for role, options in {
            "inherited": {},
            "pinned": {"provider": "ollama", "model": "codellama"},
            "model_only": {"model": "gpt-4"},
        }.items()
    }
    pool = AgentPool(configs, runtime.provider, get_default_registry(),
                     runtime.tool_registry, EventBus(), provider_settings=runtime.settings.providers)
    cached = {role: pool.get_agent(role) for role in configs}
    for agent in cached.values():
        agent.messages.append(Message(role="user", content="Specialist history"))
    histories = {role: agent.messages for role, agent in cached.items()}
    pinned_provider = cached["pinned"].provider
    runtime.orchestrator = SimpleNamespace(default_provider=runtime.provider, pool=pool)
    output = StringIO()
    ctx = CommandContext(console=Console(file=output), session=None, agent=runtime.agent,
                         tool_registry=runtime.tool_registry, repl=runtime,
                         args=["set", "ollama", "mistral"])

    await ModelCommand().execute(ctx)

    assert runtime.orchestrator.default_provider is runtime.provider
    assert pool.default_provider is runtime.provider
    assert runtime.agent.model == "mistral"
    assert cached["inherited"].provider is runtime.provider
    assert cached["inherited"].model == "mistral"
    assert cached["model_only"].model == "gpt-4"
    assert cached["model_only"].provider.base_url == "http://localhost:19876/v1"
    assert cached["pinned"].provider is pinned_provider
    for role, agent in cached.items():
        assert pool.get_agent(role) is agent
        assert agent.messages is histories[role]
        assert agent.messages[-1].content == "Specialist history"


@pytest.mark.asyncio
async def test_slash_invalid_configuration_keeps_all_runtime_references():
    runtime = make_runtime()
    runtime.settings.providers.ollama = {"unsupported_option": True}
    original = runtime.provider
    output = StringIO()
    ctx = CommandContext(console=Console(file=output), session=None, agent=runtime.agent,
                         tool_registry=runtime.tool_registry, repl=runtime,
                         args=["set", "ollama"])

    await ModelCommand().execute(ctx)

    assert runtime.provider is original
    assert runtime.agent.model == "llama3.2"
    for component in (runtime.agent, runtime.output_handler, runtime.command_processor,
                      runtime.tool_executor, runtime.core_context):
        assert component.provider is original
    assert "Failed to switch provider" in output.getvalue()


@pytest.mark.asyncio
async def test_slash_cloud_switch_preserves_config_and_sends_selected_model(monkeypatch):
    from unittest.mock import AsyncMock

    runtime = make_runtime()
    runtime.settings.providers.openai_compat = {
        "api_key": "saved-key", "base_url": "http://localhost:19877/v1",
        "model": "saved-model", "temperature": 0.25,
    }
    monkeypatch.setenv("HENCHMAN_API_KEY", "environment-key")
    ctx = CommandContext(console=Console(file=StringIO()), session=None, agent=runtime.agent,
                         tool_registry=runtime.tool_registry, repl=runtime,
                         args=["set", "openai_compat", "selected-model"])

    await ModelCommand().execute(ctx)

    assert runtime.provider.api_key == "saved-key"
    assert runtime.provider.base_url == "http://localhost:19877/v1"
    assert runtime.agent.model == "selected-model"
    assert runtime.settings.providers.openai_compat["model"] == "saved-model"

    async def response():
        for chunk in []:
            yield chunk

    create = AsyncMock(return_value=SDKResponse(response()))
    monkeypatch.setattr(runtime.provider._client.chat.completions, "create", create)
    chunks = [chunk async for chunk in runtime.provider.chat_completion_stream(runtime.agent.messages)]

    assert chunks == []
    assert create.call_args.kwargs["model"] == "selected-model"
    assert create.call_args.kwargs["temperature"] == 0.25
    assert create.call_args.kwargs["messages"][0]["content"] == "Existing conversation"
