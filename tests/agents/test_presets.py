from henchman.agents.presets import get_default_team


def test_get_default_team():
    team = get_default_team()
    assert len(team) == 1
    assert "explorer" in team

    explorer = team["explorer"]
    assert "read_file" in explorer.tools
    assert "write_file" in explorer.tools
    assert "web_fetch" in explorer.tools
    assert "web_search" in explorer.tools
