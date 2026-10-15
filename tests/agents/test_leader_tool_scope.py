"""The configured leader scope governs declarations, discovery and execution."""

from unittest.mock import AsyncMock

import pytest

from henchman.agents.config import AgentConfig
from henchman.agents.orchestrator import Orchestrator
from henchman.agents.presets import get_default_team
from henchman.cli.tool_manager import ToolManager
from henchman.config.schema import Settings
from henchman.providers.ollama import OllamaProvider
from henchman.tools.base import Tool, ToolKind, ToolResult
from henchman.tools.builtins.tier1_tools import ToolSearchTool
from henchman.tools.registry import ToolRegistry


class ScopeTool(Tool):
    description = "Scope test operation"
    kind = ToolKind.EXECUTE

    def __init__(self, name: str) -> None:
        self._name = name
        self.calls = 0

    @property
    def name(self) -> str:
        return self._name

    async def execute(self, **params: object) -> ToolResult:
        self.calls += 1
        return ToolResult("Executed")


def custom_leader(parent: ToolRegistry, tools: list[str], *, approvals: list[str] | None = None) -> Orchestrator:
    settings = Settings()
    settings.agents.agents["tech_lead"] = AgentConfig(
        name="Leader", role="tech_lead", description="Test leader",
        tools=tools, auto_approve=approvals or [],
    )
    return Orchestrator(default_provider=OllamaProvider(), tool_registry=parent, settings=settings)


def parent_with_search() -> ToolRegistry:
    parent = ToolRegistry()
    search = ToolSearchTool()
    search.bind_runtime(tool_registry=parent)
    parent.register(search)
    return parent


def test_default_primary_exposes_full_live_catalog_with_local_scope() -> None:
    manager = ToolManager()
    manager.register_builtin_tools()
    orch = Orchestrator(default_provider=OllamaProvider(), tool_registry=manager.registry)
    assert get_default_team()["tech_lead"].tools == ["*"]
    expected = set(manager.registry.list_tools())
    assert set(orch.tech_lead.tool_registry.list_tools()) == expected
    assert orch.tech_lead.tool_registry is not manager.registry
    assert orch.tech_lead.tool_registry.get("verify_plan_execution") is not None
    assert orch.tech_lead.tool_registry.get("edit_file") is not None
    assert orch.tech_lead.tool_registry.get("python_exec") is not None
    assert manager.registry.get("edit_file") is not None
    assert orch.pool.get_agent("engineer").tool_registry.get("edit_file") is not None


@pytest.mark.asyncio
async def test_custom_leader_does_not_gain_unlisted_delegation_or_write_tools() -> None:
    parent = parent_with_search()
    hidden = ScopeTool("hidden_write")
    parent.register(hidden)
    orch = custom_leader(parent, ["tool_search"])
    registry = orch.tech_lead.tool_registry
    assert [tool.name for tool in registry.get_declarations()] == ["tool_search"]
    assert registry.get("delegate_task") is None
    assert (await registry.execute("hidden_write", {})).success is False
    assert hidden.calls == 0
    search = await registry.execute("tool_search", {"query": "hidden_write"})
    assert "- hidden_write:" not in search.content
    assert parent.get("hidden_write") is hidden


@pytest.mark.asyncio
async def test_leader_local_approval_applies_only_to_allowed_tools_and_obeys_plan_mode() -> None:
    parent = ToolRegistry()
    allowed, excluded = ScopeTool("allowed"), ScopeTool("excluded")
    parent.register(allowed)
    parent.register(excluded)
    handler = AsyncMock(return_value=False)
    parent.set_confirmation_handler(handler)
    orch = custom_leader(parent, ["allowed"], approvals=["allowed", "excluded"])
    registry = orch.tech_lead.tool_registry
    assert (await registry.execute("allowed", {})).success
    assert not (await registry.execute("excluded", {})).success
    assert allowed.calls == 1 and excluded.calls == 0
    handler.assert_not_awaited()
    parent.set_plan_mode(enabled=True)
    assert not (await registry.execute("allowed", {})).success
    assert allowed.calls == 1


@pytest.mark.asyncio
async def test_leader_preserves_live_root_approval_decisions() -> None:
    parent = ToolRegistry()
    tool = ScopeTool("allowed")
    parent.register(tool)
    handler = AsyncMock(return_value=False)
    parent.set_confirmation_handler(handler)
    orch = custom_leader(parent, ["allowed"])
    registry = orch.tech_lead.tool_registry
    assert not (await registry.execute("allowed", {})).success
    assert handler.await_count == 1
    parent.add_auto_approve_policy("allowed")
    assert (await registry.execute("allowed", {})).success
    assert tool.calls == 1
    assert handler.await_count == 1
    parent.remove_auto_approve_policy("allowed")
    assert not (await registry.execute("allowed", {})).success
    assert handler.await_count == 2


@pytest.mark.asyncio
async def test_leader_sees_allowed_late_tools_and_replacements_without_root_leak() -> None:
    parent = parent_with_search()
    orch = custom_leader(parent, ["tool_search", "late_allowed"])
    registry = orch.tech_lead.tool_registry
    assert registry.get("late_allowed") is None
    first, hidden = ScopeTool("late_allowed"), ScopeTool("late_hidden")
    parent.register(first)
    parent.register(hidden)
    assert registry.get("late_allowed") is first
    assert registry.get("late_hidden") is None
    assert {tool.name for tool in registry.get_declarations()} == {"tool_search", "late_allowed"}
    search = await registry.execute("tool_search", {"query": "late_allowed"})
    assert search.success
    assert registry.discovered_tools == ["late_allowed"]
    parent.unregister("late_allowed")
    assert registry.get("late_allowed") is None
    assert registry.discovered_tools == []
    second = ScopeTool("late_allowed")
    parent.register(second)
    assert registry.get("late_allowed") is second
    parent.add_auto_approve_policy("late_allowed")
    assert (await registry.execute("late_allowed", {})).success
    assert first.calls == 0 and second.calls == 1


def test_explicit_empty_root_registry_is_retained_for_late_registration() -> None:
    parent = ToolRegistry()
    orch = custom_leader(parent, ["late_allowed"])
    assert orch.tool_registry is parent
    late = ScopeTool("late_allowed")
    parent.register(late)
    assert orch.tech_lead.tool_registry.get("late_allowed") is late


@pytest.mark.asyncio
async def test_async_mcp_registration_reaches_existing_allowed_agent_scopes() -> None:
    import asyncio
    from types import SimpleNamespace
    from typing import cast

    from henchman.cli.core_init import CoreContext, initialize_mcp

    parent = parent_with_search()
    parent.set_confirmation_handler(AsyncMock(return_value=True))
    orch = custom_leader(parent, ["tool_search", "mcp_allowed"])
    orch.pool.configs["explorer"] = AgentConfig(
        name="Explorer", role="explorer", description="Test explorer",
        tools=["tool_search", "mcp_allowed"],
    )
    cached = orch.pool.get_agent("explorer")
    allowed, hidden = ScopeTool("mcp_allowed"), ScopeTool("mcp_hidden")

    class McpStub:
        def __init__(self) -> None:
            self.clients: dict[str, object] = {}

        async def connect_all(self) -> None:
            self.clients["connected"] = object()

        def get_all_tools(self) -> list[Tool]:
            return [allowed, hidden]

    context = SimpleNamespace(
        mcp_manager=McpStub(), tool_registry=parent, background_tasks=set(),
    )
    assert cached.tool_registry.get("mcp_allowed") is None
    initialize_mcp(cast(CoreContext, context))
    assert context.background_tasks
    await asyncio.gather(*context.background_tasks)
    for agent in (orch.tech_lead, cached):
        assert agent.tool_registry.get("mcp_allowed") is allowed
        assert agent.tool_registry.get("mcp_hidden") is None
        assert (await agent.tool_registry.execute("mcp_allowed", {})).success
        assert not (await agent.tool_registry.execute("mcp_hidden", {})).success
        result = await agent.tool_registry.execute("tool_search", {"query": "mcp_"})
        assert "- mcp_allowed:" in result.content
        assert "- mcp_hidden:" not in result.content
    assert allowed.calls == 2 and hidden.calls == 0
    assert parent.get("mcp_hidden") is hidden
