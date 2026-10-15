"""Shared planning guidance reaches default leader and specialist prompts."""

import pytest

from henchman.agents.prompts import (
    DATA_ENGINEER_INSTRUCTIONS,
    DELEGATION_CHECKLIST,
    ENGINEER_INSTRUCTIONS,
    EXPLORER_INSTRUCTIONS,
    LEADER_INSTRUCTIONS,
    LINT_ON_WRITE_RULE,
    PLANNER_INSTRUCTIONS,
    SPECIALIST_THINKING,
    THINKING_PROTOCOL,
    VERIFICATION_LOCK,
    get_agent_prompt,
)
from henchman.cli.prompts import BASE_CONSTRAINTS, BASE_RULES, DEFAULT_SYSTEM_PROMPT


@pytest.mark.parametrize(
    "role", [None, "tech_lead", "planner", "explorer", "engineer", "data_engineer"]
)
def test_base_policies_compose_into_cli_and_team_defaults(role: str | None) -> None:
    """Check shared wiring; policy effectiveness requires a behavioral evaluation."""
    prompt = DEFAULT_SYSTEM_PROMPT if role is None else get_agent_prompt(role)
    assert prompt.count(BASE_RULES) == 1
    assert prompt.count(BASE_CONSTRAINTS) == 1


def test_thinking_protocol_in_leader_prompt() -> None:
    """The leader contains one canonical planning fragment."""
    assert LEADER_INSTRUCTIONS.count(THINKING_PROTOCOL) == 1


def test_leader_receives_one_canonical_delegation_checklist() -> None:
    """Check composition only; model adherence needs behavioral evaluation."""
    assert get_agent_prompt("tech_lead").count(DELEGATION_CHECKLIST) == 1


@pytest.mark.parametrize("role", ["engineer", "data_engineer"])
def test_editing_roles_receive_one_canonical_lint_policy(role: str) -> None:
    """Changing the shared policy must reach both default editing roles."""
    assert get_agent_prompt(role).count(LINT_ON_WRITE_RULE) == 1


@pytest.mark.parametrize("role", ["tech_lead", "engineer", "data_engineer"])
def test_verifying_roles_receive_one_canonical_evidence_policy(role: str) -> None:
    """Composition retains one shared verification policy per verifying role."""
    assert get_agent_prompt(role).count(VERIFICATION_LOCK) == 1


def test_delegation_matrix_in_leader_prompt() -> None:
    """Test that delegation matrix is included in leader prompt."""
    assert "DELEGATION DECISION MATRIX" in LEADER_INSTRUCTIONS
    assert "Architecture" in LEADER_INSTRUCTIONS
    assert "Planner" in LEADER_INSTRUCTIONS
    assert "Research" in LEADER_INSTRUCTIONS
    assert "Explorer" in LEADER_INSTRUCTIONS
    assert "Implementation" in LEADER_INSTRUCTIONS
    assert "Engineer" in LEADER_INSTRUCTIONS


@pytest.mark.parametrize(
    "instructions",
    [
        PLANNER_INSTRUCTIONS,
        EXPLORER_INSTRUCTIONS,
        ENGINEER_INSTRUCTIONS,
        DATA_ENGINEER_INSTRUCTIONS,
    ],
)
def test_specialists_receive_one_canonical_planning_fragment(instructions: str) -> None:
    """Role composition keeps shared planning policy consistent."""
    assert instructions.count(SPECIALIST_THINKING) == 1


def test_delegation_priority_rules() -> None:
    """Test that delegation tool includes context guidance."""
    from henchman.tools.builtins.delegate import DelegateTaskTool

    tool = DelegateTaskTool()
    description = tool.description

    assert "Delegate a task to a specialist agent" in description
    assert "CLEAN context" in description
    assert "MUST provide all relevant information" in description
