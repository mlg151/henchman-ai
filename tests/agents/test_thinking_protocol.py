"""Tests for thinking protocol in prompts."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

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
    assert "THINKING PROTOCOL:" in LEADER_INSTRUCTIONS


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
    # Check leader thinking format - updated to match current THINKING_PROTOCOL
    assert "## Phase 1: Problem Analysis" in THINKING_PROTOCOL
    assert "## Phase 2: Context Gathering" in THINKING_PROTOCOL
    assert "## Phase 3: Solution Design" in THINKING_PROTOCOL
    assert "## Phase 4: Execution Planning" in THINKING_PROTOCOL
    assert "1. What exactly needs to be solved?" in THINKING_PROTOCOL
    assert "12. How will we verify success?" in THINKING_PROTOCOL

    # Check specialist thinking format
    assert "SPECIALIST THINKING" in SPECIALIST_THINKING
    assert "THINKING (Specialist):" in SPECIALIST_THINKING


def test_delegation_priority_rules() -> None:
    """Test that delegation tool includes context guidance."""
    from henchman.tools.builtins.delegate import DelegateTaskTool

    tool = DelegateTaskTool()
    description = tool.description

    assert "Delegate a task to a specialist agent" in description
    assert "CLEAN context" in description
    assert "MUST provide all relevant information" in description
