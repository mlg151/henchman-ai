"""Scoped registries retain role boundaries as runtime tools change."""

from unittest.mock import AsyncMock

import pytest

from henchman.agents.pool import create_scoped_registry
from henchman.tools.base import Tool, ToolKind, ToolResult
from henchman.tools.builtins.tier1_tools import ToolSearchTool
from henchman.tools.registry import ToolRegistry


class NamedTool(Tool):
    description = "Live scope operation"

    def __init__(self, name: str, result: str = "executed") -> None:
        self._name = name
        self.result = result
        self.calls = 0

    @property
    def name(self) -> str:
        return self._name

    @property
    def kind(self) -> ToolKind:
        return ToolKind.WRITE

    async def execute(self, **params: object) -> ToolResult:
        self.calls += 1
        return ToolResult(self.result)


def register_search(parent: ToolRegistry) -> ToolSearchTool:
    search = ToolSearchTool()
    search.bind_runtime(tool_registry=parent)
    parent.register(search)
    return search


async def test_late_allowed_tools_appear_in_lookup_declarations_and_execution() -> None:
    parent = ToolRegistry()
    allowed = ["late"]
    scoped = create_scoped_registry(parent, allowed)
    allowed.append("secret")
    late = NamedTool("late")
    parent.register(late)
    parent.register(NamedTool("secret"))

    assert scoped.get("late") is late
    assert scoped.list_tools() == ["late"]
    assert len(scoped) == 1
    assert [tool.name for tool in scoped.get_declarations()] == ["late"]
    assert (await scoped.execute("late", {})).success
    assert late.calls == 1
    assert scoped.get("secret") is None
    assert not (await scoped.execute("secret", {})).success


async def test_parent_removal_and_replacement_are_live_through_nested_scopes() -> None:
    parent = ToolRegistry()
    original = NamedTool("operation", "original")
    parent.register(original)
    scoped = create_scoped_registry(parent, ["operation"])
    nested = create_scoped_registry(scoped, ["operation", "secret"])
    parent.unregister("operation")
    assert len(scoped) == len(nested) == 0
    assert nested.get_declarations() == []
    assert not (await nested.execute("operation", {})).success

    replacement = NamedTool("operation", "replacement")
    parent.register(replacement)
    parent.register(NamedTool("secret"))
    assert nested.get("operation") is replacement
    assert nested.get("secret") is None
    assert (await nested.execute("operation", {})).content == "replacement"
    assert original.calls == 0


async def test_extra_overrides_and_local_exclusions_win_over_parent_updates() -> None:
    parent = ToolRegistry()
    parent.register(NamedTool("operation"))
    extra = NamedTool("operation", "extra")
    local_only = NamedTool("local_only")
    scoped = create_scoped_registry(
        parent, ["operation", "late"], extra_tools=[extra, local_only]
    )
    parent.unregister("operation")
    parent.register(NamedTool("operation", "replacement"))
    assert scoped.get("operation") is extra
    assert scoped.get("local_only") is local_only
    scoped.unregister("operation")
    scoped.unregister("late")
    parent.register(NamedTool("late"))
    assert scoped.get("operation") is scoped.get("late") is None
    assert scoped.list_tools() == ["local_only"]
    assert not (await scoped.execute("operation", {})).success
    restored = NamedTool("operation", "restored")
    scoped.register(restored)
    assert (await scoped.execute("operation", {})).content == "restored"


def test_direct_scope_register_overrides_inherited_but_rejects_duplicate_local() -> None:
    from henchman.tools.scoped_registry import ScopedToolRegistry

    parent = ToolRegistry()
    parent.register(NamedTool("operation"))
    scoped = ScopedToolRegistry(parent, ["operation"])
    local = NamedTool("operation")
    scoped.register(local)
    assert scoped.get("operation") is local
    with pytest.raises(ValueError, match="already registered"):
        scoped.register(NamedTool("operation"))


async def test_late_search_binds_lazily_with_stable_identity_and_scoped_inventory() -> None:
    parent = ToolRegistry()
    scoped = create_scoped_registry(parent, ["tool_search", "visible"])
    assert not scoped.supports_tool_discovery
    root_search = register_search(parent)
    parent.register(NamedTool("visible"))
    parent.register(NamedTool("secret"))
    assert scoped.supports_tool_discovery
    search = scoped.get("tool_search")
    assert search is not None and search is not root_search
    assert scoped.get("tool_search") is search
    result = await search.execute(query="visible")
    assert result.success
    assert "secret" not in result.content
    assert scoped.discovered_tools == ["visible"]
    assert parent.discovered_tools == []


async def test_search_replacement_rebinds_nested_scopes_and_clears_stale_priorities() -> None:
    parent = ToolRegistry()
    register_search(parent)
    parent.register(NamedTool("visible"))
    scoped = create_scoped_registry(parent, ["tool_search", "visible"])
    nested = create_scoped_registry(scoped, ["tool_search", "visible"])
    previous = nested.get("tool_search")
    assert previous is not None
    await previous.execute(query="visible")
    assert nested.discovered_tools == ["visible"]
    parent.unregister("tool_search")
    replacement = register_search(parent)
    assert nested.discovered_tools == []
    assert nested.supports_tool_discovery
    current = nested.get("tool_search")
    assert current is not None
    assert current is not previous and current is not replacement
    assert current is not scoped.get("tool_search")
    assert nested.discovered_tools == []
    await current.execute(query="visible")
    assert nested.discovered_tools == ["visible"]
    assert scoped.discovered_tools == parent.discovered_tools == []


def test_search_removed_or_replaced_with_custom_tool_disables_discovery() -> None:
    parent = ToolRegistry()
    register_search(parent)
    scoped = create_scoped_registry(parent, ["tool_search"])
    assert scoped.supports_tool_discovery
    parent.unregister("tool_search")
    assert not scoped.supports_tool_discovery
    custom = NamedTool("tool_search")
    parent.register(custom)
    assert scoped.get("tool_search") is custom
    assert not scoped.supports_tool_discovery


async def test_local_search_override_is_cloned_and_bound_only_to_its_scope() -> None:
    parent = ToolRegistry()
    original = register_search(parent)
    parent.register(NamedTool("visible"))
    parent.register(NamedTool("secret"))
    scoped = create_scoped_registry(
        parent, ["visible"], extra_tools=[original]
    )
    assert scoped.supports_tool_discovery
    local = scoped.get("tool_search")
    assert local is not None and local is not original
    parent.unregister("tool_search")
    register_search(parent)
    assert scoped.get("tool_search") is local
    result = await local.execute()
    assert "visible" in result.content and "secret" not in result.content
    scoped.unregister("tool_search")
    assert not scoped.supports_tool_discovery


def test_priorities_filter_live_membership_and_remain_independent() -> None:
    parent = ToolRegistry()
    scoped = create_scoped_registry(parent, ["late"])
    parent.register(NamedTool("late"))
    scoped.prioritize_tools(["late", "hidden"])
    assert scoped.discovered_tools == ["late"]
    assert parent.discovered_tools == []
    parent.unregister("late")
    assert scoped.discovered_tools == []


@pytest.mark.parametrize("inherit", [False, True])
async def test_parent_auto_approval_is_live_only_when_requested(inherit: bool) -> None:
    parent = ToolRegistry()
    tool = NamedTool("operation")
    parent.register(tool)
    deny = AsyncMock(return_value=False)
    parent.set_confirmation_handler(deny)
    scoped = create_scoped_registry(
        parent, ["operation"], inherit_auto_approve=inherit
    )
    assert not (await scoped.execute("operation", {})).success
    parent.add_auto_approve_policy("operation")
    assert scoped.is_auto_approved("operation") is inherit
    assert (await scoped.execute("operation", {})).success is inherit
    parent.remove_auto_approve_policy("operation")
    assert not (await scoped.execute("operation", {})).success
    scoped.add_auto_approve_policy("operation")
    assert (await scoped.execute("operation", {})).success
    parent.set_plan_mode(enabled=True)
    result = await scoped.execute("operation", {})
    assert not result.success and "Plan Mode" in result.content
    assert tool.calls == int(inherit) + 1


async def test_nested_inherited_approvals_and_current_confirmation_remain_live() -> None:
    parent = ToolRegistry()
    parent.register(NamedTool("operation"))
    scoped = create_scoped_registry(
        parent, ["operation"], inherit_auto_approve=True
    )
    nested = create_scoped_registry(
        scoped, ["operation"], inherit_auto_approve=True
    )
    parent.set_confirmation_handler(AsyncMock(return_value=False))
    parent.add_auto_approve_policy("operation")
    assert (await nested.execute("operation", {})).success
    parent.remove_auto_approve_policy("operation")
    assert not (await nested.execute("operation", {})).success
    parent.set_confirmation_handler(AsyncMock(return_value=True))
    assert (await nested.execute("operation", {})).success
