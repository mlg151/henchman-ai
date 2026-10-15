"""Provider displays follow the acting agent without changing team defaults."""

from types import MethodType, SimpleNamespace
from unittest.mock import MagicMock

import pytest

from henchman.cli import textual_mixins
from henchman.cli.output_handler import OutputHandler
from henchman.cli.textual_app import HenchmanTextualApp
from henchman.cli.textual_mixins import (
    _ContextTreeMixin,
    _InputHandlerMixin,
    _ProviderMixin,
    _StatusBarMixin,
    _WorkspaceMixin,
)
from henchman.core.agent import Agent
from henchman.providers import OpenRouterProvider
from henchman.providers.ollama import OllamaProvider


@pytest.fixture
async def providers():
    default = OllamaProvider(model="team-default")
    leader = OpenRouterProvider(api_key="offline", model="leader-model")
    specialist = OllamaProvider(model="specialist-model")
    try:
        yield default, leader, specialist
    finally:
        for provider in (default, leader, specialist):
            await provider._client.close()


def output_handler(provider):
    return OutputHandler(
        renderer=MagicMock(), tool_manager=MagicMock(),
        session_manager=SimpleNamespace(current=None), provider=provider,
        settings=SimpleNamespace(context=SimpleNamespace(max_tokens=8000)),
    )


async def test_toolbar_reports_active_provider_and_explicit_capacity(providers, monkeypatch):
    default, leader, _ = providers
    agent = Agent(leader, context_window=700000)
    handler = output_handler(default)
    monkeypatch.setattr("henchman.utils.tokens.TokenCounter.count_messages", lambda *_a, **_kw: 350000)
    text = "".join(part for _, part in handler.get_toolbar_status(agent))
    assert "leader-model" in text
    assert "team-default" not in text
    assert "Tokens: 50%" in text
    assert handler._get_max_tokens(agent) == 700000
    assert handler.provider is default


async def test_toolbar_uses_active_model_when_capacity_is_unset(providers, monkeypatch):
    default, leader, _ = providers
    agent = Agent(leader)
    handler = output_handler(default)
    monkeypatch.setattr("henchman.utils.tokens.get_model_limit", lambda model: {
        "team-default": 8000, "leader-model": 32000,
    }[model])
    assert handler._get_max_tokens(agent) == 32000
    assert handler._get_max_tokens() == 8000


def runtime(default, active, *, direct=None):
    agents = {"engineer": Agent(direct)} if direct else {}
    return SimpleNamespace(
        provider=default,
        config=SimpleNamespace(agent_role="engineer" if direct else None, system_prompt=""),
        core_context=SimpleNamespace(
            agent=Agent(active),
            orchestrator=SimpleNamespace(pool=SimpleNamespace(get_agent=agents.__getitem__)),
            session_manager=SimpleNamespace(current=None), mcp_manager=None,
            tool_manager=SimpleNamespace(auto_approve=False),
        ),
        settings=SimpleNamespace(plan_mode=False, ui=SimpleNamespace(theme="default")),
        _count_tools=lambda: 2, _mcp_status_fragment=lambda: "",
        _welcome_mcp_info=lambda: "", _update_status_bar=lambda: None,
    )


@pytest.mark.parametrize("direct", [False, True])
async def test_textual_status_welcome_and_workspace_use_actual_agent(providers, monkeypatch, direct):
    default, leader, specialist = providers
    obj = runtime(default, leader, direct=specialist if direct else None)
    expected_provider = "ollama" if direct else "openrouter"
    expected_model = "specialist-model" if direct else "leader-model"
    chat, summary, settings_panel = MagicMock(), MagicMock(), MagicMock()
    panels = {"#chat-pane": chat, "#agent-summary-panel": summary, "#settings-panels": settings_panel}
    monkeypatch.setattr(textual_mixins, "_query_one_or_none", lambda _obj, name, _kind: panels.get(name))

    status = _StatusBarMixin._build_status_text(obj)
    assert f"{expected_provider}:{expected_model}" in status
    _ContextTreeMixin._show_welcome(obj)
    assert f"{expected_provider}:{expected_model}" in chat.add_system_message.call_args_list[0].args[0]
    _WorkspaceMixin._refresh_workspace_widgets(obj)
    assert summary.update_summary.call_args.kwargs["provider_name"] == expected_provider
    assert summary.update_summary.call_args.kwargs["model_name"] == expected_model
    assert settings_panel.update_settings.call_args.kwargs["provider"] == expected_provider
    _ProviderMixin._announce_provider_switch(obj, "old", expected_provider)
    assert obj.sub_title.endswith(f"- {expected_provider}")
    assert obj.provider is default


async def test_textual_model_only_override_and_initialization_fallback(providers):
    default, _, specialist = providers
    obj = runtime(default, specialist)
    assert "ollama:specialist-model" in _StatusBarMixin._build_status_text(obj)
    obj.core_context = None
    assert "ollama:team-default" in _StatusBarMixin._build_status_text(obj)


def test_textual_legacy_provider_model_fallback():
    legacy = SimpleNamespace(name="legacy", model="legacy-model")
    obj = SimpleNamespace(
        provider=legacy, settings=None, _count_tools=lambda: 0,
        _mcp_status_fragment=lambda: "",
    )
    assert "legacy:legacy-model" in _StatusBarMixin._build_status_text(obj)


async def test_textual_mount_subtitle_uses_configured_leader(providers):
    default, leader, _ = providers
    obj = runtime(default, leader)
    for name in (
        "_initialize_core_components", "_apply_theme", "_populate_context_tree",
        "_show_welcome", "query_one", "_load_history", "_refresh_workspace_widgets",
        "call_after_refresh", "_activate_chat_tab",
    ):
        setattr(obj, name, MagicMock())
    HenchmanTextualApp.on_mount(obj)
    assert obj.sub_title.endswith("- openrouter")
    assert obj.provider is default


async def test_textual_switch_changes_pinned_direct_agent_and_reports_its_previous_provider(
    providers, monkeypatch,
):
    from henchman.agents.orchestrator import Orchestrator
    from henchman.config.schema import Settings

    default, replacement, _ = providers
    settings = Settings.model_validate({
        "providers": {
            "ollama": {"model": "saved-default"},
            "openrouter": {"api_key": "offline", "model": "saved-cloud"},
        },
        "agents": {"agents": {
            "tech_lead": {"provider": "openrouter", "model": "pinned-leader"},
            "engineer": {"provider": "ollama", "model": "pinned-engineer"},
        }},
    })
    orch = Orchestrator(default_provider=default, settings=settings)
    actor, leader = orch.pool.get_agent("engineer"), orch.tech_lead
    original_actor_provider, original_leader_provider = actor.provider, leader.provider
    actor.set_context_limit(525000, context_window=700000)
    history, tools, prompt = actor.messages, actor.tool_registry, actor.system_prompt
    obj = runtime(default, leader.provider)
    obj.settings, obj.orchestrator, obj.agent = settings, orch, leader
    obj.config.agent_role = "engineer"
    obj.core_context.agent, obj.core_context.orchestrator = leader, orch
    obj._announce_provider_switch = MethodType(_ProviderMixin._announce_provider_switch, obj)
    obj._show_provider_error = lambda exc: pytest.fail(str(exc))
    chat = MagicMock()
    monkeypatch.setattr(textual_mixins, "_query_one_or_none", lambda *_args: chat)
    monkeypatch.setattr("henchman.providers.factory.create_configured_provider", lambda *_args, **_kw: replacement)
    try:
        _ProviderMixin._switch_provider(obj, "openrouter")
        assert actor.provider is replacement
        assert leader.provider is original_leader_provider
        assert actor.messages is history and actor.tool_registry is tools
        assert actor.system_prompt == prompt
        assert actor.context_window == 700000 and actor.max_tokens == 525000
        assert orch.default_provider is replacement
        assert "[cyan]ollama[/] -> [cyan]openrouter[/]" in chat.add_system_message.call_args.args[0]
    finally:
        await original_actor_provider._client.close()
        await original_leader_provider._client.close()


@pytest.fixture
async def direct_runtime(providers):
    from io import StringIO

    from rich.console import Console

    from henchman.agents.orchestrator import Orchestrator
    from henchman.cli.command_processor import CommandProcessor
    from henchman.cli.repl import ReplConfig
    from henchman.cli.session_manager import ReplSessionManager
    from henchman.config.schema import Settings

    default, _, _ = providers
    settings = Settings.model_validate({
        "providers": {
            "openrouter": {"api_key": "offline", "model": "saved-cloud"},
            "ollama": {"model": "saved-local"},
        },
        "agents": {"agents": {
            "tech_lead": {"provider": "openrouter", "model": "pinned-leader"},
            "engineer": {"provider": "ollama", "model": "pinned-engineer"},
        }},
    })
    orch = Orchestrator(default_provider=default, settings=settings)
    actor, leader = orch.pool.get_agent("engineer"), orch.tech_lead
    initial_providers = [actor.provider, leader.provider]
    sink = StringIO()
    handler = output_handler(default)
    handler.session_manager = ReplSessionManager(auto_save=False)
    handler.renderer.console = Console(file=sink, width=120, color_system=None)
    manager = SimpleNamespace(registry=orch.tool_registry)
    processor = CommandProcessor(handler, manager, handler.session_manager, default)
    obj = SimpleNamespace(
        provider=default, settings=settings, config=ReplConfig(agent_role="engineer"),
        orchestrator=orch, agent=leader, command_processor=processor,
        core_context=SimpleNamespace(agent=leader, orchestrator=orch),
        output_handler=handler, renderer=handler.renderer, tool_registry=orch.tool_registry,
        _tui_adapter=None, _interactive_loop_active=False,
    )
    try:
        yield obj, actor, leader, sink
    finally:
        clients = {id(provider): provider._client for provider in (
            *initial_providers, actor.provider, leader.provider, obj.provider,
        )}
        for client in clients.values():
            await client.close()


@pytest.mark.parametrize("ui", ["repl", "textual"])
@pytest.mark.parametrize("operation", ["show", "set"])
@pytest.mark.parametrize("direct", [False, True])
async def test_slash_model_commands_target_configured_actor(direct_runtime, ui, operation, direct):
    from copy import deepcopy
    from unittest.mock import AsyncMock

    from henchman.cli.repl import Repl
    from henchman.providers.base import Message

    obj, actor, leader, sink = direct_runtime
    obj.config.agent_role = "engineer" if direct else None
    selected, inactive = (actor, leader) if direct else (leader, actor)
    inactive_provider = inactive.provider
    actor.messages.append(Message("user", "Retain specialist history"))
    leader.messages.append(Message("user", "Retain leader history"))
    actor_history, leader_history = actor.messages, leader.messages
    history_snapshot = deepcopy((actor_history, leader_history))
    actor_tools, leader_tools = actor.tool_registry, leader.tool_registry
    saved_config = obj.settings.agents.model_dump()
    command = "/model" if operation == "show" else "/model set openrouter selected-model --context-length 700000"
    if ui == "repl":
        obj.input_handler = SimpleNamespace(process_input=AsyncMock(return_value=(command, True, True)))
        await Repl.process_input(obj, command)
    else:
        await _InputHandlerMixin._handle_command(obj, command, MagicMock())

    if operation == "show":
        assert ("pinned-engineer" if direct else "pinned-leader") in sink.getvalue()
        assert ("pinned-leader" if direct else "pinned-engineer") not in sink.getvalue()
    else:
        assert selected.provider.name == "openrouter"
        assert selected.provider.default_model == "selected-model"
        assert selected.context_window == 700000 and selected.max_tokens == 525000
        assert obj.settings.context.max_tokens == 700000
        assert inactive.provider is inactive_provider
    assert actor.messages is actor_history and leader.messages is leader_history
    assert (actor.messages, leader.messages) == history_snapshot
    assert actor.tool_registry is actor_tools and leader.tool_registry is leader_tools
    assert obj.settings.agents.model_dump() == saved_config


@pytest.mark.parametrize("direct", [False, True])
async def test_repl_toolbar_uses_configured_role_provider(direct_runtime, monkeypatch, direct):
    from henchman.cli.repl import Repl

    obj, _, _, _ = direct_runtime
    obj.config.agent_role = "engineer" if direct else None
    input_handler = MagicMock()
    input_handler.prompt_session = None
    monkeypatch.setattr("henchman.cli.repl.InputHandler", lambda **_kwargs: input_handler)
    Repl._init_input_handler(obj)
    toolbar = input_handler.initialize_prompt_session.call_args.kwargs["bottom_toolbar"]
    text = "".join(part for _, part in toolbar())
    assert ("pinned-engineer" if direct else "pinned-leader") in text
    assert ("pinned-leader" if direct else "pinned-engineer") not in text
