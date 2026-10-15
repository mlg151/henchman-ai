"""Tool discovery is bound to each agent's own catalog and authorization."""

from unittest.mock import AsyncMock

import pytest

from henchman.agents.config import AgentConfig
from henchman.agents.pool import AgentPool, create_scoped_registry
from henchman.agents.presets import get_default_team
from henchman.core.eventbus import EventBus
from henchman.providers.ollama import OllamaProvider
from henchman.tools.base import Tool, ToolKind, ToolResult
from henchman.tools.builtins.tier1_tools import ToolSearchTool
from henchman.tools.registry import ToolRegistry


class NamedTool(Tool):
    description = "Scoped test operation"

    def __init__(self, name: str) -> None:
        self._name = name
        self.calls = 0

    @property
    def name(self) -> str:
        return self._name

    @property
    def kind(self) -> ToolKind:
        return ToolKind.WRITE

    async def execute(self, **params: object) -> ToolResult:
        self.calls += 1
        return ToolResult("Executed")


def _parent() -> tuple[ToolRegistry, ToolSearchTool, NamedTool]:
    registry = ToolRegistry()
    search = ToolSearchTool()
    search.bind_runtime(tool_registry=registry)
    registry.register(search)
    visible = NamedTool("scoped_probe")
    registry.register(visible)
    registry.register(NamedTool("root_secret"))
    return registry, search, visible


@pytest.mark.parametrize("extra", [False, True])
async def test_scoped_builtin_search_never_leaks_parent_only_tools(extra: bool) -> None:
    parent, original_search, visible = _parent()
    scoped = create_scoped_registry(
        parent,
        allowed_tools=["scoped_probe"] if extra else ["scoped_probe", "tool_search"],
        extra_tools=[original_search] if extra else None,
    )
    search = scoped.get("tool_search")
    assert search is not None
    result = await search.execute()
    assert result.success
    assert "scoped_probe" in result.content
    assert "root_secret" not in result.content
    assert search is not original_search
    assert scoped.get("scoped_probe") is visible
    root_result = await original_search.execute()
    assert "root_secret" in root_result.content


async def test_cached_and_future_agents_have_independent_discovery_priority() -> None:
    parent, root_search, _visible = _parent()
    parent.register(NamedTool("future_probe"))
    configs = {
        "cached": AgentConfig(
            name="Cached", role="cached", description="Test", tools=["tool_search", "scoped_probe"]
        ),
        "future": AgentConfig(
            name="Future", role="future", description="Test", tools=["tool_search", "future_probe"]
        ),
    }
    pool = AgentPool(configs, OllamaProvider(), None, parent, EventBus())
    cached = pool.get_agent("cached")
    search = cached.tool_registry.get("tool_search")
    assert search is not None
    assert (await search.execute(query="scoped_probe")).success
    assert cached.tool_registry.discovered_tools == ["scoped_probe"]
    assert parent.discovered_tools == []
    assert (await root_search.execute(query="root_secret")).success
    future = pool.get_agent("future")
    future_search = future.tool_registry.get("tool_search")
    assert future_search is not None
    assert future.tool_registry.discovered_tools == []
    assert (await future_search.execute(query="future_probe")).success
    assert future.tool_registry.discovered_tools == ["future_probe"]
    assert cached.tool_registry.discovered_tools == ["scoped_probe"]
    assert parent.discovered_tools == ["root_secret"]
    assert pool.get_agent("cached") is cached


def test_default_specialists_include_discovery_but_explicit_custom_lists_control_it() -> None:
    team = get_default_team()
    for role, config in team.items():
        if role != "tech_lead":
            assert "tool_search" in config.tools
    parent, _search, _visible = _parent()
    custom = AgentConfig(name="Custom", role="custom", description="Test", tools=["scoped_probe"])
    pool = AgentPool({"custom": custom}, OllamaProvider(), None, parent, EventBus())
    registry = pool.get_agent("custom").tool_registry
    assert registry.list_tools() == ["scoped_probe"]
    assert not registry.supports_tool_discovery


async def test_discovered_tools_still_obey_current_parent_authorization() -> None:
    parent, _original, visible = _parent()
    scoped = create_scoped_registry(parent, ["tool_search", "scoped_probe"])
    search = scoped.get("tool_search")
    assert search is not None
    assert (await search.execute(query="scoped_probe")).success
    deny = AsyncMock(return_value=False)
    parent.set_confirmation_handler(deny)
    result = await scoped.execute("scoped_probe", {})
    assert not result.success
    assert visible.calls == 0
    deny.assert_awaited_once()


def test_unrelated_search_named_tool_is_not_cloned_or_rebound() -> None:
    parent = ToolRegistry()
    custom = NamedTool("tool_search")
    parent.register(custom)
    scoped = create_scoped_registry(parent, ["tool_search"])
    assert scoped.get("tool_search") is custom


def test_custom_extra_replacing_builtin_search_does_not_enable_builtin_discovery() -> None:
    parent, _search, _visible = _parent()
    custom = NamedTool("tool_search")
    scoped = create_scoped_registry(parent, ["tool_search"], extra_tools=[custom])
    assert scoped.get("tool_search") is custom
    assert not scoped.supports_tool_discovery
