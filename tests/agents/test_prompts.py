from henchman.agents.prompts import (
    AGENT_WORKSPACE,
    CLEANUP_HABIT,
    DELEGATION_SUMMARY_SCHEMA,
    LINT_ON_WRITE_RULE,
    RECON_FIRST_RULE,
    SCOPE_SENTINEL,
    VERIFICATION_LOCK,
    get_agent_prompt,
)


def test_get_agent_prompt_leader():
    prompt = get_agent_prompt("tech_lead")
    assert "The Leader" in prompt
    assert "Henchman" in prompt


def test_get_agent_prompt_explorer():
    prompt = get_agent_prompt("explorer")
    assert "Explorer" in prompt
    assert "Research" in prompt


def test_get_agent_prompt_with_team():
    prompt = get_agent_prompt("tech_lead", team_members=["Explorer"])
    assert "Explorer" in prompt


def test_get_agent_prompt_with_delegation():
    prompt = get_agent_prompt("tech_lead", delegatable_agents=["explorer"])
    assert "explorer" in prompt
    assert "delegate_task" in prompt


def test_leader_prompt_has_recon_first():
    """Leader prompt includes mandatory reconnaissance."""
    prompt = get_agent_prompt("tech_lead")
    assert "Mandatory Reconnaissance" in prompt


def test_leader_prompt_has_scope_sentinel():
    """Leader prompt includes scope sentinel."""
    prompt = get_agent_prompt("tech_lead")
    assert "Scope Sentinel" in prompt


def test_leader_prompt_has_lint_on_write():
    """Leader prompt includes lint-on-write rule."""
    prompt = get_agent_prompt("tech_lead")
    assert "Lint-on-Write" in prompt


def test_leader_prompt_has_verification_lock():
    """Leader prompt includes verification lock."""
    prompt = get_agent_prompt("tech_lead")
    assert "Verification Tool-Lock" in prompt


def test_leader_prompt_has_cleanup_habit():
    """Leader prompt includes clean-up habit."""
    prompt = get_agent_prompt("tech_lead")
    assert "Clean-Up Habit" in prompt


def test_leader_prompt_has_agent_workspace():
    """Leader prompt includes .agent_tasks workspace convention."""
    prompt = get_agent_prompt("tech_lead")
    assert ".agent_tasks/" in prompt


def test_explorer_prompt_has_delegation_summary():
    """Explorer prompt includes structured delegation summary."""
    prompt = get_agent_prompt("explorer")
    assert "Structured Delegation Summary" in prompt


def test_explorer_prompt_has_agent_workspace():
    """Explorer prompt includes .agent_tasks workspace convention."""
    prompt = get_agent_prompt("explorer")
    assert ".agent_tasks/" in prompt


def test_prompt_fragments_are_nonempty():
    """All cross-cutting prompt fragments have content."""
    assert len(RECON_FIRST_RULE) > 20
    assert len(SCOPE_SENTINEL) > 20
    assert len(DELEGATION_SUMMARY_SCHEMA) > 20
    assert len(LINT_ON_WRITE_RULE) > 20
    assert len(CLEANUP_HABIT) > 20
    assert len(VERIFICATION_LOCK) > 20
    assert len(AGENT_WORKSPACE) > 20
