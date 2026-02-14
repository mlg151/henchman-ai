from henchman.agents.presets import get_default_team


def test_get_default_team():
    team = get_default_team()
    assert len(team) == 3
    assert "planner" in team
    assert "explorer" in team
    assert "engineer" in team


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
    assert "web_fetch" not in engineer.tools
    assert "web_search" not in engineer.tools
