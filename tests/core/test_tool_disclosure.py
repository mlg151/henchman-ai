"""Context-sized declarations keep the coding catalog discoverable."""

from copy import deepcopy
from typing import Any

import pytest

from henchman.agents.orchestrator import Orchestrator
from henchman.cli.tool_manager import ToolManager
from henchman.core.agent import Agent
from henchman.core.events import EventType
from henchman.providers import OpenRouterProvider
from henchman.providers.base import (
    FinishReason,
    Message,
    ModelProvider,
    StreamChunk,
)
from henchman.providers.request_budget import OutputBudget
from henchman.tools.base import Tool, ToolKind, ToolResult
from henchman.tools.builtins.tier1_tools import ToolSearchTool
from henchman.tools.registry import ToolRegistry


class CatalogTool(Tool):
    name = "catalog"
    description = "Catalog tool"
    kind = ToolKind.READ
    parameters = {"type": "object", "properties": {}}

    def __init__(self, name: str, description: str) -> None:
        self.name = name
        self.description = description

    async def execute(self, **params: object) -> ToolResult:
        return ToolResult("Done")


class BudgetProvider(ModelProvider):
    name = "budget-test"

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def prepare_output_budget(self, default_max_tokens: int) -> OutputBudget:
        return OutputBudget(20, {"max_tokens": 20})

    def estimate_input_tokens(self, messages, tools) -> int:
        return sum(len(m.content or "") for m in messages) + sum(
            len(t.description) for t in tools or []
        )

    async def chat_completion_stream(self, messages, tools=None, **kwargs):
        self.calls.append({"messages": deepcopy(messages), "tools": tools, **kwargs})
        yield StreamChunk(content="Done.", finish_reason=FinishReason.STOP)


def catalog() -> ToolRegistry:
    registry = ToolRegistry()
    search = ToolSearchTool()
    search.bind_runtime(tool_registry=registry)
    registry.register(search)
    registry.register(CatalogTool("read_file", "Read"))
    registry.register(CatalogTool("edit_file", "Edit"))
    for i in range(15):
        registry.register(CatalogTool(f"special_{i}", f"Special{i} " + "x" * 180))
    return registry


def prepare(registry, messages=None, *, capacity=1000):
    from henchman.core.tool_selection import prepare_agent_request

    return prepare_agent_request(
        BudgetProvider(), messages or [Message("system", "Rules"), Message("user", "Task")],
        registry, context_window=capacity, conversation_limit=capacity,
        protect_from_index=1,
    )


def test_oversized_catalog_offers_discovery_and_core_tools_without_changing_registry() -> None:
    registry = catalog()
    names = registry.list_tools()
    request = prepare(registry)
    selected = {tool.name for tool in request.tools}
    assert {"tool_search", "read_file", "edit_file"} <= selected
    assert not any(name.startswith("special_") for name in selected)
    assert request.estimated_input_tokens + request.output_tokens <= 1000
    assert registry.list_tools() == names


@pytest.mark.asyncio
async def test_exact_discovery_exposes_the_actual_requested_schema_next_call() -> None:
    registry = catalog()
    original = registry.get("special_12").to_declaration()
    result = await registry.execute("tool_search", {"query": "special_12"})
    assert result.success
    request = prepare(registry)
    assert original in request.tools
    assert request.estimated_input_tokens + request.output_tokens <= 1000


def test_fitting_catalog_is_preserved_in_original_order() -> None:
    registry = catalog()
    assert prepare(registry, capacity=10000).tools == registry.get_declarations()


def test_catalog_without_discovery_retains_explicit_overflow() -> None:
    from henchman.providers.base import ContextTooLargeError

    registry = catalog()
    registry.unregister("tool_search")
    with pytest.raises(ContextTooLargeError):
        prepare(registry)


@pytest.mark.asyncio
async def test_requested_schema_that_cannot_fit_is_reported_instead_of_silently_omitted() -> None:
    from henchman.providers.base import ContextTooLargeError

    registry = catalog()
    registry.register(CatalogTool("huge", "x" * 3000))
    await registry.execute("tool_search", {"query": "huge"})
    with pytest.raises(ContextTooLargeError):
        prepare(registry)


def test_tool_selection_cannot_truncate_mandatory_instructions() -> None:
    from henchman.providers.base import ContextTooLargeError

    messages = [Message("system", "x" * 1000), Message("user", "Task")]
    original = deepcopy(messages)
    with pytest.raises(ContextTooLargeError):
        prepare(catalog(), messages)
    assert messages == original


@pytest.mark.asyncio
async def test_new_user_turn_releases_previous_discovery_priorities() -> None:
    registry = catalog()
    provider = BudgetProvider()
    agent = Agent(provider, tool_registry=registry, context_window=1000, max_tokens=900)
    await registry.execute("tool_search", {"query": "special_12"})
    assert registry.discovered_tools == ["special_12"]
    events = [event async for event in agent.run("New independent task")]
    assert not any(event.type == EventType.ERROR for event in events)
    assert registry.discovered_tools == []
    assert "special_12" not in {tool.name for tool in provider.calls[0]["tools"]}


@pytest.mark.asyncio
async def test_default_leader_makes_a_complete_first_request_in_8k(monkeypatch) -> None:
    """Real prompts, tool schemas and provider accounting; only inference is scripted."""
    manager = ToolManager()
    manager.register_builtin_tools()
    provider = OpenRouterProvider(api_key="offline", model="scripted")
    calls = []

    async def stream(messages, tools=None, **kwargs):
        calls.append((deepcopy(messages), tools, kwargs))
        yield StreamChunk(content="Hello!", finish_reason=FinishReason.STOP)

    monkeypatch.setattr(provider, "chat_completion_stream", stream)
    orch = Orchestrator(default_provider=provider, tool_registry=manager.registry)
    history = deepcopy(orch.tech_lead.messages)
    events = [event async for event in orch.tech_lead.run("Hello")]
    assert not any(event.type == EventType.ERROR for event in events)
    assert len(calls) == 1
    messages, tools, options = calls[0]
    assert options["max_tokens"] == 2000
    assert provider.estimate_input_tokens(messages, tools) + options["max_tokens"] <= 8000
    assert "tool_search" in {tool.name for tool in tools}
    assert len(tools) < len(manager.registry)
    assert orch.tech_lead.messages[:len(history)] == history


@pytest.mark.parametrize("choice_options", [
    {"tool_choice": {"type": "function", "function": {"name": "pytest_run"}}},
    {"tool_choice": "none", "extra_body": {
        "tool_choice": {"type": "function", "function": {"name": "pytest_run"}},
    }},
])
def test_fallback_preserves_provider_forced_tool_schema(choice_options) -> None:
    from henchman.core.tool_selection import prepare_agent_request

    manager = ToolManager()
    manager.register_builtin_tools()
    provider = OpenRouterProvider(api_key="offline", model="scripted", **choice_options)
    orch = Orchestrator(default_provider=provider, tool_registry=manager.registry)
    request = prepare_agent_request(
        provider, [*orch.tech_lead.messages, Message("user", "Run selected tests")],
        manager.registry, context_window=8000, conversation_limit=6000,
        protect_from_index=1,
    )
    params = provider._build_request_params(request.messages, request.tools, request.request_options)
    wire = {**params, **(params.get("extra_body") or {})}
    name = wire["tool_choice"]["function"]["name"]
    assert name == "pytest_run"
    assert name in {tool["function"]["name"] for tool in wire["tools"]}
    assert request.estimated_input_tokens + request.output_tokens <= 8000


@pytest.mark.parametrize("required_name", ["excluded_tool", "huge_tool"])
def test_forced_tool_cannot_broaden_scope_or_evade_capacity(required_name: str) -> None:
    from henchman.core.tool_selection import prepare_agent_request
    from henchman.providers.base import ContextTooLargeError

    manager = ToolManager()
    manager.register_builtin_tools()
    manager.registry.register(CatalogTool("huge_tool", "large input " * 10000))
    provider = OpenRouterProvider(
        api_key="offline", model="scripted",
        tool_choice={"type": "function", "function": {"name": required_name}},
    )
    orch = Orchestrator(default_provider=provider, tool_registry=manager.registry)
    expected = ValueError if required_name == "excluded_tool" else ContextTooLargeError
    with pytest.raises(expected):
        prepare_agent_request(
            provider, [*orch.tech_lead.messages, Message("user", "Task")],
            manager.registry, context_window=8000, conversation_limit=6000,
            protect_from_index=1,
        )


@pytest.mark.asyncio
async def test_default_leader_can_continue_after_broad_discovery() -> None:
    from henchman.core.tool_selection import prepare_agent_request
    from henchman.providers.base import ToolCall

    manager = ToolManager()
    manager.register_builtin_tools()
    provider = OpenRouterProvider(api_key="offline", model="scripted")
    orch = Orchestrator(default_provider=provider, tool_registry=manager.registry)
    result = await manager.registry.execute("tool_search", {})
    assert result.success
    messages = [
        *orch.tech_lead.messages, Message("user", "Find available tools"),
        Message("assistant", "", tool_calls=[ToolCall("search", "tool_search", {})]),
        Message("tool", result.content, tool_call_id="search"),
    ]
    request = prepare_agent_request(
        provider, messages, manager.registry, context_window=8000,
        conversation_limit=6000, protect_from_index=1,
    )
    assert request.estimated_input_tokens + request.output_tokens <= 8000
    assert request.messages == messages
    assert result.content == messages[-1].content
