"""Team tool metadata follows live scopes without granting or instantiating them."""

from unittest.mock import Mock

import pytest

from henchman.agents.config import AgentConfig
from henchman.agents.pool import AgentPool
from henchman.core.eventbus import EventBus
from henchman.providers.base import ModelProvider
from henchman.tools.base import Tool, ToolResult
from henchman.tools.builtins.delegate import DelegateTaskTool
from henchman.tools.builtins.tier1_tools import ToolSearchTool
from henchman.tools.registry import ToolRegistry


class ProbeTool(Tool):
    description = "A registered capability for scope tests"

    def __init__(self, name: str) -> None:
        self._name = name
        self.calls = 0

    @property
    def name(self) -> str:
        return self._name

    async def execute(self, **params: object) -> ToolResult:
        self.calls += 1
        return ToolResult("Executed")


def config(role: str, tools: list[str], **kwargs: object) -> AgentConfig:
    return AgentConfig(name=role, role=role, description="Role", tools=tools, **kwargs)


def team(*, caller_tools: list[str] | None = None) -> tuple[AgentPool, ToolRegistry]:
    parent = ToolRegistry()
    parent.register(DelegateTaskTool())
    search = ToolSearchTool()
    search.bind_runtime(tool_registry=parent)
    parent.register(search)
    parent.register(ProbeTool("pytest_run"))
    configs = {
        "tech_lead": config(
            "tech_lead",
            caller_tools or ["tool_search", "delegate_task"],
            system_prompt="CUSTOM LEADER PROMPT",
        ),
        "engineer": config("engineer", ["pytest_run"]),
        "explorer": config("explorer", ["tool_search"]),
    }
    return AgentPool(configs, Mock(spec=ModelProvider), None, parent, EventBus()), parent


async def search(pool: AgentPool, **kwargs: object) -> ToolResult:
    return await pool.get_agent("tech_lead").tool_registry.execute(
        "tool_search",
        {"scope": "team", "query": "pytest_run", **kwargs},
    )


async def test_team_lookup_reports_roles_without_granting_or_prioritizing_tools() -> None:
    pool, parent = team()
    leader = pool.get_agent("tech_lead")
    before = leader.tool_registry.get_declarations()
    leader.tool_registry.prioritize_tools(["delegate_task"])
    result = await search(pool)
    assert result.success
    assert "pytest_run" in result.content and "- engineer" in result.content
    assert "metadata" in result.content.lower()
    assert "authorization" in result.content.lower() and "readiness" in result.content.lower()
    assert leader.tool_registry.get("pytest_run") is None
    assert not (await leader.tool_registry.execute("pytest_run", {})).success
    assert leader.tool_registry.get_declarations() == before
    assert leader.tool_registry.discovered_tools == ["delegate_task"]
    assert parent.discovered_tools == []
    assert not leader.tool_registry.is_auto_approved("pytest_run")
    assert parent.get("pytest_run").calls == 0
    assert leader.system_prompt == "CUSTOM LEADER PROMPT"


async def test_lookup_never_builds_uncached_pinned_providers(monkeypatch) -> None:
    pool, _ = team()
    pool.configs["engineer"].provider = "unbuildable-provider"
    leader = pool.get_agent("tech_lead")

    def forbidden(*_args, **_kwargs):
        raise AssertionError("Discovery instantiated a provider")

    monkeypatch.setattr("henchman.agents.pool.create_configured_provider", forbidden)
    result = await search(pool)
    assert result.success and "- engineer" in result.content
    assert pool._agents == {"tech_lead": leader}


async def test_registration_removal_replacement_and_exact_query_are_live() -> None:
    pool, parent = team()
    parent.unregister("pytest_run")
    result = await search(pool)
    assert result.success and "No enabled candidate" in result.content
    parent.register(ProbeTool("pytest_run"))
    assert "- engineer" in (await search(pool)).content
    parent.unregister("pytest_run")
    assert "- engineer" not in (await search(pool)).content
    parent.register(ProbeTool("pytest_run"))
    assert "- engineer" in (await search(pool)).content
    assert "No enabled candidate" in (await search(pool, query="pytest")).content
    assert "No enabled candidate" in (await search(pool, query="PYTEST_RUN")).content


async def test_cached_actual_scope_wins_over_config_and_parent() -> None:
    pool, parent = team()
    engineer = pool.get_agent("engineer")
    engineer.tool_registry.unregister("pytest_run")
    assert "- engineer" not in (await search(pool)).content
    local = ProbeTool("pytest_run")
    engineer.tool_registry.register(local)
    parent.unregister("pytest_run")
    pool.configs["engineer"].tools = ["different_tool"]
    assert "- engineer" in (await search(pool)).content
    engineer.tool_registry.register(ProbeTool("local_only"))
    assert "- engineer" in (await search(pool, query="local_only")).content
    assert local.calls == 0


async def test_disabled_self_and_same_instance_aliases_are_excluded() -> None:
    pool, _ = team(caller_tools=["tool_search", "delegate_task", "pytest_run"])
    leader = pool.get_agent("tech_lead")
    pool.configs["engineer"].enabled = False
    pool.configs["leader_alias"] = config("leader_alias", ["pytest_run"])
    pool._agents["leader_alias"] = leader
    result = await search(pool)
    assert result.success and "No enabled candidate" in result.content
    assert "- tech_lead" not in result.content and "- leader_alias" not in result.content
    pool.configs["engineer"].enabled = True
    assert "- engineer" in (await search(pool)).content


async def test_role_pagination_is_stable_and_bounded() -> None:
    pool, _ = team()
    for role in ("zeta", "alpha", "beta"):
        pool.configs[role] = config(role, ["pytest_run"])
    first = await search(pool, limit=2)
    assert "- alpha" in first.content and "- beta" in first.content
    assert "- engineer" not in first.content and "- zeta" not in first.content
    assert "total=4 offset=0 limit=2 next_offset=2" in first.content
    last = await search(pool, limit=2, offset=2)
    assert "- engineer" in last.content and "- zeta" in last.content
    assert "next_offset=none" in last.content
    beyond = await search(pool, limit=2, offset=8)
    assert beyond.success and "- engineer" not in beyond.content


async def test_lookup_tracks_caller_delegation_scope_and_current_registration() -> None:
    pool, parent = team(caller_tools=["tool_search"])
    leader = pool.get_agent("tech_lead")
    assert not (await search(pool)).success
    leader.tool_registry.register(DelegateTaskTool())
    assert "- engineer" in (await search(pool)).content
    leader.tool_registry.unregister("delegate_task")
    assert not (await search(pool)).success

    second, second_parent = team()
    second.get_agent("tech_lead")
    second_parent.unregister("delegate_task")
    assert not (await search(second)).success
    second_parent.register(DelegateTaskTool())
    assert "- engineer" in (await search(second)).content


async def test_replacing_bound_search_preserves_registry_team_lookup() -> None:
    pool, parent = team()
    leader = pool.get_agent("tech_lead")
    old = leader.tool_registry.get("tool_search")
    assert "- engineer" in (await search(pool)).content
    parent.unregister("tool_search")
    replacement = ToolSearchTool()
    replacement.bind_runtime(tool_registry=parent)
    parent.register(replacement)
    assert leader.tool_registry.get("tool_search") is not old
    assert "- engineer" in (await search(pool)).content


@pytest.mark.parametrize("bound", [False, True])
async def test_unbound_and_root_lookup_fail_explicitly(bound: bool) -> None:
    tool = ToolSearchTool()
    if bound:
        registry = ToolRegistry()
        registry.register(DelegateTaskTool())
        tool.bind_runtime(tool_registry=registry)
    result = await tool.execute(scope="team", query="pytest_run")
    assert not result.success and "unavailable" in result.content.lower()


@pytest.mark.parametrize(
    "params",
    [
        {"scope": "global"},
        {"scope": None},
        {"scope": []},
        {"query": ""},
        {"query": "   "},
        {"query": "pytest run"},
        {"query": None},
        {"query": 123},
        {"query": []},
        {"limit": 0},
        {"limit": True},
        {"limit": 101},
        {"offset": -1},
        {"offset": "0"},
    ],
)
async def test_invalid_team_queries_do_not_call_resolver_or_mutate_priorities(params) -> None:
    registry = ToolRegistry()
    registry.register(DelegateTaskTool())
    registry.prioritize_tools(["delegate_task"])
    calls = []
    registry.bind_team_tool_resolver(lambda name: calls.append(name) or ["engineer"])
    tool = ToolSearchTool()
    tool.bind_runtime(tool_registry=registry)
    result = await tool.execute(**{"scope": "team", "query": "pytest_run", **params})
    assert not result.success
    assert calls == []
    assert registry.discovered_tools == ["delegate_task"]


async def test_default_agent_miss_does_not_claim_team_absence() -> None:
    pool, _ = team()
    registry = pool.get_agent("tech_lead").tool_registry
    result = await registry.execute("tool_search", {"query": "pytest_run"})
    assert not result.success
    assert "agent" in result.content.lower() and "scope" in result.content.lower()
    assert "team" in result.content.lower()
    assert "- engineer" not in result.content
