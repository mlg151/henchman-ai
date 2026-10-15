"""Scoped, bounded tool discovery changes schemas, never execution permissions."""

import pytest

from henchman.tools.base import Tool, ToolKind, ToolResult
from henchman.tools.builtins.tier1_tools import ToolSearchTool
from henchman.tools.registry import ToolRegistry


class NamedTool(Tool):
    description = "Executable example alpha tool"
    parameters = {"type": "object", "properties": {}}
    kind = ToolKind.WRITE

    def __init__(self, name: str) -> None:
        self._name = name
        self.executions = 0

    @property
    def name(self) -> str:
        return self._name

    async def execute(self, **kwargs: object) -> ToolResult:
        self.executions += 1
        return ToolResult(content=self.name)


def bound_search(*names: str) -> tuple[ToolRegistry, ToolSearchTool]:
    registry = ToolRegistry()
    for name in names:
        registry.register(NamedTool(name))
    search = ToolSearchTool()
    search.bind_runtime(tool_registry=registry)
    registry.register(search)
    return registry, search


def test_discovery_requires_enabled_and_current_registered_search() -> None:
    registry = ToolRegistry()
    search = ToolSearchTool()
    registry.register(search)
    assert not registry.supports_tool_discovery
    search.bind_runtime(tool_registry=registry)
    assert registry.supports_tool_discovery
    registry.unregister("tool_search")
    assert not registry.supports_tool_discovery
    registry.register(search)
    assert registry.supports_tool_discovery


def test_priorities_are_bounded_unique_snapshots_of_current_membership() -> None:
    registry, _ = bound_search(*(f"tool_{index}" for index in range(7)))
    registry.prioritize_tools(
        ["missing", "tool_0", "tool_0", *(f"tool_{index}" for index in range(7))]
    )
    assert registry.discovered_tools == [f"tool_{index}" for index in range(5)]
    snapshot = registry.discovered_tools
    snapshot.clear()
    assert len(registry.discovered_tools) == 5
    registry.unregister("tool_2")
    assert "tool_2" not in registry.discovered_tools
    registry.prioritize_tools(["tool_6", "missing"])
    assert registry.discovered_tools == ["tool_6"]


async def test_exact_name_ranks_first_and_inventory_remains_complete() -> None:
    registry, search = bound_search(
        "zulu", "alpha", "alpha_2", "alpha_3", "alpha_4", "alpha_5", "alpha_6"
    )
    result = await search.execute(query="zulu")
    assert result.success
    assert registry.discovered_tools == ["zulu"]
    result = await search.execute(query="alpha", limit=100)
    assert result.success
    assert registry.discovered_tools == ["alpha", "alpha_2", "alpha_3", "alpha_4", "alpha_5"]
    for name in ("alpha", "alpha_2", "alpha_3", "alpha_4", "alpha_5", "alpha_6", "zulu"):
        assert f"- {name}:" in result.content
    assert "Prioritized schemas:" in result.content
    assert "exact" in result.content.lower()
    assert "tool_search" not in registry.discovered_tools


async def test_exact_name_beats_alphabetically_earlier_description_match() -> None:
    registry, search = bound_search("aaa", "alpha")
    result = await search.execute(query="ALPHA")
    assert registry.discovered_tools == ["alpha", "aaa"]
    assert result.content.index("- alpha:") < result.content.index("- aaa:")


async def test_failed_and_capability_only_queries_preserve_priorities() -> None:
    registry, search = bound_search("alpha")
    await search.execute(query="alpha")
    failed = await search.execute(query="no-such-tool-9836")
    assert not failed.success
    assert registry.discovered_tools == ["alpha"]
    capability = await search.execute(query="dialog")
    assert capability.success
    assert "Capability truth:" in capability.content
    assert registry.discovered_tools == ["alpha"]


async def test_search_observes_dynamic_registration_and_removal() -> None:
    registry, search = bound_search("alpha")
    registry.register(NamedTool("late"))
    assert (await search.execute(query="late")).success
    assert registry.discovered_tools == ["late"]
    registry.unregister("late")
    assert registry.discovered_tools == []
    assert not (await search.execute(query="late")).success


async def test_copied_search_cannot_expose_or_prioritize_parent_tools() -> None:
    parent, original = bound_search("parent_only", "shared")
    child = ToolRegistry()
    child.register(NamedTool("shared"))
    cloned = original.for_registry(child)
    child.register(cloned)
    assert cloned is not original
    assert child.supports_tool_discovery
    assert parent.supports_tool_discovery
    assert not (await cloned.execute(query="parent_only")).success
    await original.execute(query="parent_only")
    await cloned.execute(query="shared")
    assert parent.discovered_tools == ["parent_only"]
    assert child.discovered_tools == ["shared"]


async def test_discovery_does_not_execute_or_autoapprove_discovered_tools() -> None:
    registry, _ = bound_search("alpha")
    registry.set_plan_mode(enabled=True)
    result = await registry.execute("tool_search", {"query": "alpha"})
    assert result.success
    assert registry.discovered_tools == ["alpha"]
    denied = await registry.execute("alpha", {})
    assert not denied.success
    tool = registry.get("alpha")
    assert isinstance(tool, NamedTool)
    assert tool.executions == 0


def test_description_explains_schema_discovery() -> None:
    assert "schema" in ToolSearchTool().description.lower()
    assert "context" in ToolSearchTool().description.lower()


def test_unrelated_same_name_replacement_does_not_support_schema_discovery() -> None:
    registry, original = bound_search("alpha")
    assert registry.supports_tool_discovery
    registry.unregister("tool_search")
    registry.register(NamedTool("tool_search"))
    assert not registry.supports_tool_discovery
    registry.unregister("tool_search")
    registry.register(original)
    assert registry.supports_tool_discovery


def inventory_lines(result: ToolResult) -> list[str]:
    return [line for line in result.content.splitlines() if line.startswith("- ")]


async def test_default_page_is_bounded_and_all_pages_cover_inventory_once() -> None:
    registry, search = bound_search(*(f"tool_{index:02}" for index in range(12)))
    first = await search.execute()
    assert len(inventory_lines(first)) == 5
    assert "offset=0" in first.content and "next_offset=5" in first.content
    assert registry.discovered_tools == [f"tool_{index:02}" for index in range(5)]
    complete = inventory_lines(await search.execute(limit=100))
    combined: list[str] = []
    for offset in range(0, len(complete), 3):
        page = await search.execute(limit=3, offset=offset)
        entries = inventory_lines(page)
        assert len(entries) <= 3
        assert f"total={len(complete)}" in page.content
        assert f"offset={offset}" in page.content
        combined.extend(entries)
    assert combined == complete
    assert len(combined) == len(set(combined))
    assert "Capability truth:" in page.content
    assert "next_offset=none" in page.content


async def test_page_priorities_include_only_shown_executable_names() -> None:
    registry, search = bound_search("aaa", "alpha", "beta", "gamma", "zeta")
    first = await search.execute(query="alpha", limit=1)
    assert inventory_lines(first)[0].startswith("- alpha:")
    assert registry.discovered_tools == ["alpha"]
    second = await search.execute(query="alpha", limit=2, offset=1)
    assert len(inventory_lines(second)) == 2
    assert registry.discovered_tools == ["aaa", "beta"]
    await search.execute(limit=1, offset=len(registry.list_tools()))
    assert registry.discovered_tools == ["aaa", "beta"]
    empty = await search.execute(offset=1000)
    assert empty.success
    assert not inventory_lines(empty)
    assert registry.discovered_tools == ["aaa", "beta"]
    assert "offset=0" in empty.content


@pytest.mark.parametrize("params", [
    {"limit": 0}, {"limit": -1}, {"limit": 101}, {"limit": True},
    {"limit": 1.0}, {"limit": "5"}, {"limit": None},
    {"offset": -1}, {"offset": True}, {"offset": 1.0},
    {"offset": "0"}, {"offset": None},
])
async def test_invalid_pagination_fails_before_query_or_priority_mutation(
    params: dict[str, object], monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry, search = bound_search("alpha")
    registry.prioritize_tools(["alpha"])

    def forbidden() -> None:
        pytest.fail("Invalid pagination must fail before resolving tools")

    monkeypatch.setattr(search, "_resolve_tools", forbidden)
    result = await search.execute(**params)
    assert not result.success
    assert registry.discovered_tools == ["alpha"]
    assert next(iter(params)) in result.content
