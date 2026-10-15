import pytest

from henchman.agents.presets import get_default_team


def test_get_default_team():
    team = get_default_team()
    assert len(team) == 5
    assert "tech_lead" in team
    assert "planner" in team
    assert "explorer" in team
    assert "engineer" in team
    assert "data_engineer" in team


def test_tech_lead_tools():
    team = get_default_team()
    lead = team["tech_lead"]
    assert "read_file" in lead.tools
    assert "ls" in lead.tools
    assert "glob" in lead.tools
    assert "grep" in lead.tools
    assert "shell" in lead.tools
    assert "web_fetch" in lead.tools
    assert "web_search" in lead.tools
    assert "rag_search" in lead.tools
    assert "kg_query" in lead.tools
    assert "kg_update" in lead.tools
    assert "delegate_task" in lead.tools
    assert "ask_user" in lead.tools
    # Leader must NOT have write/edit tools
    assert "write_file" not in lead.tools
    assert "edit_file" not in lead.tools


def test_planner_tools():
    team = get_default_team()
    planner = team["planner"]
    assert "read_file" in planner.tools
    assert "write_file" in planner.tools
    assert "glob" in planner.tools
    assert "grep" in planner.tools
    assert "web_fetch" in planner.tools
    assert "web_search" in planner.tools
    assert "kg_query" in planner.tools
    assert "kg_update" in planner.tools
    assert "shell" not in planner.tools


def test_explorer_tools():
    team = get_default_team()
    explorer = team["explorer"]
    assert "read_file" in explorer.tools
    assert "write_file" in explorer.tools
    assert "web_fetch" in explorer.tools
    assert "web_search" in explorer.tools
    assert "kg_query" in explorer.tools
    assert "kg_update" in explorer.tools
    assert "shell" in explorer.tools


def test_engineer_tools():
    team = get_default_team()
    engineer = team["engineer"]
    assert "read_file" in engineer.tools
    assert "write_file" in engineer.tools
    assert "edit_file" in engineer.tools
    assert "shell" in engineer.tools
    assert "glob" in engineer.tools
    assert "grep" in engineer.tools
    # New Python development tools
    assert "python_exec" in engineer.tools
    assert "pytest_run" in engineer.tools
    assert "lint_check" in engineer.tools
    assert "diff_view" in engineer.tools
    assert "pip_inspect" in engineer.tools
    assert "python_ast" in engineer.tools
    assert "code_format" in engineer.tools
    assert "traceback_parse" in engineer.tools
    assert "import_graph" in engineer.tools
    assert "coverage_map" in engineer.tools
    # Engineer doesn't have web/search tools
    assert "web_fetch" not in engineer.tools
    assert "web_search" not in engineer.tools


def test_data_engineer_tools():
    team = get_default_team()
    data_eng = team["data_engineer"]
    assert "read_file" in data_eng.tools
    assert "write_file" in data_eng.tools
    assert "edit_file" in data_eng.tools
    assert "shell" in data_eng.tools
    assert "glob" in data_eng.tools
    assert "grep" in data_eng.tools
    assert "web_fetch" in data_eng.tools
    assert "web_search" in data_eng.tools
    # New Python development tools
    assert "python_exec" in data_eng.tools
    assert "pytest_run" in data_eng.tools
    assert "lint_check" in data_eng.tools
    assert "diff_view" in data_eng.tools
    assert "pip_inspect" in data_eng.tools
    assert "python_ast" in data_eng.tools
    assert "code_format" in data_eng.tools
    assert "traceback_parse" in data_eng.tools
    assert "import_graph" in data_eng.tools
    assert "coverage_map" in data_eng.tools
    # Data engineer doesn't have KG tools
    assert "kg_query" not in data_eng.tools
    assert "kg_update" not in data_eng.tools


@pytest.mark.parametrize("role", ["tech_lead", "planner", "explorer", "engineer", "data_engineer"])
async def test_default_roles_execute_registered_reuse_discovery_tools(role, tmp_path):
    """Scoped agents can inspect existing implementations before adding new code."""
    from unittest.mock import MagicMock

    from henchman.agents.pool import AgentPool
    from henchman.cli.tool_manager import ToolManager
    from henchman.core.eventbus import EventBus
    from henchman.providers.base import ModelProvider
    from henchman.tools.base import ToolKind

    source = tmp_path / "helpers.py"
    source.write_text("class ExistingHelper:\n    pass\n", encoding="utf-8")
    manager = ToolManager()
    manager.register_builtin_tools()
    pool = AgentPool(get_default_team(), MagicMock(spec=ModelProvider), None, manager.registry, EventBus())
    registry = pool.get_agent(role).tool_registry
    requests = {
        "file_overview": {"path": str(source)},
        "symbol_trace": {"symbol": "ExistingHelper", "path": str(tmp_path)},
        "pattern_search": {"description": "ExistingHelper", "path": str(tmp_path)},
    }
    for name, arguments in requests.items():
        result = await registry.execute(name, arguments)
        assert result.success, result.content
        assert "ExistingHelper" in result.content
        assert registry.get(name).kind == ToolKind.READ


async def test_custom_role_allowlist_remains_restricted_with_discovery_tools_registered(tmp_path):
    from unittest.mock import MagicMock

    from henchman.agents.pool import AgentPool
    from henchman.cli.tool_manager import ToolManager
    from henchman.core.eventbus import EventBus
    from henchman.providers.base import ModelProvider

    source = tmp_path / "helpers.py"
    source.write_text("class ExistingHelper:\n    pass\n", encoding="utf-8")
    manager = ToolManager()
    manager.register_builtin_tools()
    team = get_default_team()
    team["engineer"].tools = ["file_overview"]
    pool = AgentPool(team, MagicMock(spec=ModelProvider), None, manager.registry, EventBus())
    registry = pool.get_agent("engineer").tool_registry
    allowed = await registry.execute("file_overview", {"path": str(source)})
    assert allowed.success
    for name in ("symbol_trace", "pattern_search"):
        result = await registry.execute(name, {"path": str(source)})
        assert not result.success
        assert registry.get(name) is None


def test_execution_presets_can_track_multiple_background_jobs():
    for preset in get_default_team().values():
        if {"shell", "python_exec"}.intersection(preset.tools):
            assert {"task_get", "task_list", "task_output", "task_stop"} <= set(preset.tools)


def test_default_agents_can_complete_explicit_goals():
    for preset in get_default_team().values():
        assert "goal_status" in preset.tools
