"""Tests for thinking protocol in prompts."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from src.henchman.agents.prompts import (
    ENGINEER_INSTRUCTIONS,
    EXPLORER_INSTRUCTIONS,
    LEADER_INSTRUCTIONS,
    PLANNER_INSTRUCTIONS,
    SPECIALIST_THINKING,
    THINKING_PROTOCOL,
)


def test_thinking_protocol_in_leader_prompt() -> None:
    """Test that thinking protocol is included in leader prompt."""
    assert THINKING_PROTOCOL in LEADER_INSTRUCTIONS
    assert "THINKING PROTOCOL" in LEADER_INSTRUCTIONS
    assert "Start EVERY response with:" in LEADER_INSTRUCTIONS
    assert "THINKING:" in LEADER_INSTRUCTIONS


def test_delegation_matrix_in_leader_prompt() -> None:
    """Test that delegation matrix is included in leader prompt."""
    assert "DELEGATION DECISION MATRIX" in LEADER_INSTRUCTIONS
    assert "Architecture" in LEADER_INSTRUCTIONS
    assert "Planner" in LEADER_INSTRUCTIONS
    assert "Research" in LEADER_INSTRUCTIONS
    assert "Explorer" in LEADER_INSTRUCTIONS
    assert "Implementation" in LEADER_INSTRUCTIONS
    assert "Engineer" in LEADER_INSTRUCTIONS


def test_specialist_thinking_in_planner_prompt() -> None:
    """Test that specialist thinking is included in planner prompt."""
    assert SPECIALIST_THINKING in PLANNER_INSTRUCTIONS
    assert "SPECIALIST THINKING" in PLANNER_INSTRUCTIONS
    assert "THINKING (Specialist):" in PLANNER_INSTRUCTIONS


def test_specialist_thinking_in_explorer_prompt() -> None:
    """Test that specialist thinking is included in explorer prompt."""
    assert SPECIALIST_THINKING in EXPLORER_INSTRUCTIONS
    assert "SPECIALIST THINKING" in EXPLORER_INSTRUCTIONS
    assert "THINKING (Specialist):" in EXPLORER_INSTRUCTIONS


def test_specialist_thinking_in_engineer_prompt() -> None:
    """Test that specialist thinking is included in engineer prompt."""
    assert SPECIALIST_THINKING in ENGINEER_INSTRUCTIONS
    assert "SPECIALIST THINKING" in ENGINEER_INSTRUCTIONS
    assert "THINKING (Specialist):" in ENGINEER_INSTRUCTIONS


def test_thinking_format_requirements() -> None:
    """Test that thinking format includes required sections."""
    # Check leader thinking format
    assert "1. Problem:" in THINKING_PROTOCOL
    assert "2. Context:" in THINKING_PROTOCOL
    assert "3. Options:" in THINKING_PROTOCOL
    assert "4. Decision:" in THINKING_PROTOCOL
    assert "5. Plan:" in THINKING_PROTOCOL

    # Check specialist thinking format
    assert "1. Understanding:" in SPECIALIST_THINKING
    assert "2. Approach:" in SPECIALIST_THINKING
    assert "3. Risks:" in SPECIALIST_THINKING
    assert "4. Verification:" in SPECIALIST_THINKING


def test_delegation_priority_rules() -> None:
    """Test that delegation tool includes priority rules."""
    from henchman.tools.builtins.delegate import DelegateTaskTool

    tool = DelegateTaskTool()
    description = tool.description

    assert "DELEGATION PRIORITY RULES" in description
    assert "ALWAYS consider delegation before doing work yourself" in description
    assert "Architecture/design → Planner" in description
    assert "Research/exploration → Explorer" in description
    assert "Implementation/testing → Engineer" in description
