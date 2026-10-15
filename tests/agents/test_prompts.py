from henchman.agents.prompts import (
    AGENT_WORKSPACE,
    BLOCKER_PROTOCOL,
    CLEANUP_HABIT,
    CONVENTION_AWARENESS,
    DATA_ENGINEER_INSTRUCTIONS,
    DELEGATION_CHECKLIST,
    DELEGATION_EXAMPLES,
    DELEGATION_SUMMARY_SCHEMA,
    ENGINEER_INSTRUCTIONS,
    LINT_ON_WRITE_RULE,
    PLANNER_INSTRUCTIONS,
    RE_DELEGATION_RULE,
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
    """Leader prompt references Planner, Explorer, Engineer, and Data Engineer."""
    prompt = get_agent_prompt("tech_lead")
    assert "Planner" in prompt
    assert "Explorer" in prompt
    assert "Engineer" in prompt
    assert "Data Engineer" in prompt


def test_leader_prompt_has_recon_first():
    """Leader prompt includes mandatory reconnaissance."""
    prompt = get_agent_prompt("tech_lead")
    assert "Mandatory Reconnaissance" in prompt


def test_leader_prompt_has_scope_sentinel():
    """Leader prompt includes scope sentinel."""
    prompt = get_agent_prompt("tech_lead")
    assert "Scope Sentinel" in prompt


def test_leader_prompt_has_no_write_tools():
    """Leader prompt states it cannot write or edit files."""
    prompt = get_agent_prompt("tech_lead")
    assert "CANNOT WRITE OR EDIT FILES" in prompt
    assert "delegate_task" in prompt


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


def test_get_agent_prompt_data_engineer():
    """Data Engineer prompt includes expected keywords."""
    prompt = get_agent_prompt("data_engineer")
    assert "Data Engineer" in prompt
    assert "AWS" in prompt
    assert "PySpark" in prompt
    assert "Pandas" in prompt
    assert "Airflow" in prompt


def test_data_engineer_prompt_has_delegation_summary():
    """Data Engineer prompt includes structured delegation summary."""
    prompt = get_agent_prompt("data_engineer")
    assert "Structured Delegation Summary" in prompt


def test_data_engineer_prompt_has_agent_workspace():
    """Data Engineer prompt includes .agent_tasks workspace convention."""
    prompt = get_agent_prompt("data_engineer")
    assert ".agent_tasks/" in prompt


def test_data_engineer_prompt_has_verification_lock():
    """Data Engineer prompt includes verification lock."""
    prompt = get_agent_prompt("data_engineer")
    assert "Verification Tool-Lock" in prompt


def test_data_engineer_prompt_has_lint_on_write():
    """Data Engineer prompt includes lint-on-write rule."""
    prompt = get_agent_prompt("data_engineer")
    assert "Lint-on-Write" in prompt


def test_data_engineer_instructions_nonempty():
    """Data Engineer instructions have content."""
    assert len(DATA_ENGINEER_INSTRUCTIONS) > 100


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
    for role in ("tech_lead", "planner", "explorer", "engineer", "data_engineer"):
        prompt = get_agent_prompt(role, environment_context=env_block)
        assert "<environment_context>" in prompt, f"{role} missing env context"


# ------------------------------------------------------------------
# v0.2.8 — Teamwork Prompt Improvements (20 items)
# ------------------------------------------------------------------


def test_new_prompt_fragments_are_nonempty():
    """All new teamwork prompt fragments have content."""
    assert len(DELEGATION_CHECKLIST) > 20
    assert len(DELEGATION_EXAMPLES) > 20
    assert len(RE_DELEGATION_RULE) > 20
    assert len(BLOCKER_PROTOCOL) > 20
    assert len(CONVENTION_AWARENESS) > 20


def test_delegation_checklist_in_leader():
    """Leader prompt includes delegation brief self-check (#1)."""
    prompt = get_agent_prompt("tech_lead")
    assert "Delegation Brief Self-Check" in prompt
    assert "files" in prompt.lower()


def test_delegation_examples_in_leader():
    """Leader prompt includes bad-vs-good delegation examples (#2)."""
    prompt = get_agent_prompt("tech_lead")
    assert "BAD vs GOOD" in prompt
    assert "GOOD" in prompt


def test_re_delegation_rule_in_leader():
    """Leader prompt includes re-delegation after failure rule (#4)."""
    prompt = get_agent_prompt("tech_lead")
    assert "Re-Delegation After Failure" in prompt


def test_delegation_summary_has_blockers_field():
    """Delegation summary schema includes BLOCKERS field (#11)."""
    assert "BLOCKERS:" in DELEGATION_SUMMARY_SCHEMA


def test_delegation_summary_has_handoff_notes_field():
    """Delegation summary schema includes HANDOFF_NOTES field (#11)."""
    assert "HANDOFF_NOTES:" in DELEGATION_SUMMARY_SCHEMA


def test_delegation_summary_has_artifacts_field():
    """Delegation summary schema includes ARTIFACTS field (#12)."""
    assert "ARTIFACTS:" in DELEGATION_SUMMARY_SCHEMA


def test_delegation_summary_has_failure_analysis():
    """Delegation summary schema includes FAILURE_ANALYSIS section (#15)."""
    assert "FAILURE_ANALYSIS:" in DELEGATION_SUMMARY_SCHEMA
    assert "What failed:" in DELEGATION_SUMMARY_SCHEMA
    assert "What was tried:" in DELEGATION_SUMMARY_SCHEMA
    assert "Suggested fix:" in DELEGATION_SUMMARY_SCHEMA


def test_delegation_summary_has_output_audience():
    """Delegation summary schema includes output audience note (#9)."""
    assert "Output Audience" in DELEGATION_SUMMARY_SCHEMA
    assert "Tech Lead" in DELEGATION_SUMMARY_SCHEMA


def test_blocker_protocol_in_all_specialists():
    """All specialist prompts include blocker protocol (#14)."""
    for role in ("planner", "explorer", "engineer", "data_engineer"):
        prompt = get_agent_prompt(role)
        assert "Early Blocker Protocol" in prompt, f"{role} missing blocker protocol"


def test_convention_awareness_in_all_specialists():
    """All specialist prompts include convention awareness (#18)."""
    for role in ("planner", "explorer", "engineer", "data_engineer"):
        prompt = get_agent_prompt(role)
        assert "Convention Awareness" in prompt, f"{role} missing convention awareness"


def test_engineer_has_plan_awareness():
    """Engineer prompt includes plan awareness for planner handoff (#20)."""
    prompt = get_agent_prompt("engineer")
    assert "Plan Awareness" in prompt
    assert ".agent_tasks/" in prompt


def test_planner_has_engineer_handoff():
    """Planner prompt includes engineer handoff guidance (#20)."""
    prompt = get_agent_prompt("planner")
    assert "Engineer Handoff" in prompt
    assert "function signatures" in prompt


def test_get_agent_prompt_with_team_descriptions():
    """Team descriptions produce enriched roster (#8)."""
    members = ["Leader (tech_lead)", "Engineer (engineer)"]
    descriptions = {
        "tech_lead": "Orchestrates and verifies work",
        "engineer": "Implements code and runs tests",
    }
    prompt = get_agent_prompt(
        "tech_lead",
        team_members=members,
        team_descriptions=descriptions,
    )
    assert "Your Team" in prompt
    assert "Orchestrates and verifies work" in prompt
    assert "Implements code and runs tests" in prompt


def test_get_agent_prompt_team_descriptions_fallback():
    """Without team_descriptions, falls back to simple member list."""
    members = ["Leader (tech_lead)", "Engineer (engineer)"]
    prompt = get_agent_prompt("tech_lead", team_members=members)
    assert "Team Members" in prompt
    assert "Leader (tech_lead)" in prompt
