from henchman.agents.prompts import (
    AGENT_WORKSPACE,
    CLEANUP_HABIT,
    DELEGATION_SUMMARY_SCHEMA,
    ENGINEER_INSTRUCTIONS,
    LINT_ON_WRITE_RULE,
    PLANNER_INSTRUCTIONS,
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


def test_get_agent_prompt_planner():
    prompt = get_agent_prompt("planner")
    assert "Planner" in prompt
    assert "Architect" in prompt


def test_get_agent_prompt_engineer():
    prompt = get_agent_prompt("engineer")
    assert "Engineer" in prompt
    assert "Implementation" in prompt


def test_leader_prompt_references_specialists():
    """Leader prompt references Planner, Explorer, and Engineer."""
    prompt = get_agent_prompt("tech_lead")
    assert "Planner" in prompt
    assert "Explorer" in prompt
    assert "Engineer" in prompt


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


def test_leader_prompt_has_knowledge_graph():
    """Leader prompt mentions knowledge graph."""
    prompt = get_agent_prompt("tech_lead")
    assert "kg_query" in prompt
    assert "Knowledge Graph" in prompt


def test_explorer_prompt_has_knowledge_graph():
    """Explorer prompt mentions knowledge graph tools."""
    prompt = get_agent_prompt("explorer")
    assert "kg_query" in prompt
    assert "kg_update" in prompt


def test_prompt_fragments_are_nonempty():
    """All cross-cutting prompt fragments have content."""
    assert len(RECON_FIRST_RULE) > 20
    assert len(SCOPE_SENTINEL) > 20
    assert len(DELEGATION_SUMMARY_SCHEMA) > 20
    assert len(LINT_ON_WRITE_RULE) > 20
    assert len(CLEANUP_HABIT) > 20
    assert len(VERIFICATION_LOCK) > 20
    assert len(AGENT_WORKSPACE) > 20


def test_planner_prompt_has_delegation_summary():
    """Planner prompt includes structured delegation summary."""
    prompt = get_agent_prompt("planner")
    assert "Structured Delegation Summary" in prompt


def test_planner_prompt_has_agent_workspace():
    """Planner prompt includes .agent_tasks workspace convention."""
    prompt = get_agent_prompt("planner")
    assert ".agent_tasks/" in prompt


def test_planner_prompt_has_knowledge_graph():
    """Planner prompt mentions knowledge graph tools."""
    prompt = get_agent_prompt("planner")
    assert "kg_query" in prompt
    assert "kg_update" in prompt


def test_engineer_prompt_has_delegation_summary():
    """Engineer prompt includes structured delegation summary."""
    prompt = get_agent_prompt("engineer")
    assert "Structured Delegation Summary" in prompt


def test_engineer_prompt_has_verification_lock():
    """Engineer prompt includes verification lock."""
    prompt = get_agent_prompt("engineer")
    assert "Verification Tool-Lock" in prompt


def test_engineer_prompt_has_lint_on_write():
    """Engineer prompt includes lint-on-write rule."""
    prompt = get_agent_prompt("engineer")
    assert "Lint-on-Write" in prompt


def test_planner_instructions_nonempty():
    """Planner instructions have content."""
    assert len(PLANNER_INSTRUCTIONS) > 100


def test_engineer_instructions_nonempty():
    """Engineer instructions have content."""
    assert len(ENGINEER_INSTRUCTIONS) > 100


def test_get_agent_prompt_with_environment_context():
    """Environment context block is injected when provided."""
    env_block = "<environment_context>\n* Working directory: /tmp\n</environment_context>"
    prompt = get_agent_prompt("tech_lead", environment_context=env_block)
    assert "<environment_context>" in prompt
    assert "Working directory: /tmp" in prompt


def test_get_agent_prompt_without_environment_context():
    """No environment block when not provided."""
    prompt = get_agent_prompt("tech_lead")
    assert "<environment_context>" not in prompt


def test_get_agent_prompt_env_context_all_roles():
    """All roles include the environment context when provided."""
    env_block = "<environment_context>\n* OS: Linux\n</environment_context>"
    for role in ("tech_lead", "planner", "explorer", "engineer"):
        prompt = get_agent_prompt(role, environment_context=env_block)
        assert "<environment_context>" in prompt, f"{role} missing env context"
