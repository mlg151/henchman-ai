"""Tests for enhanced delegation tool."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from src.henchman.tools.builtins.delegate import DelegateTaskTool


def test_delegate_tool_has_enhanced_description() -> None:
    """Test that delegation tool includes enhanced guidance."""
    tool = DelegateTaskTool()
    description = tool.description

    # Check for enhanced guidance sections
    assert "DELEGATION PRIORITY RULES" in description
    assert "ALWAYS consider delegation before doing work yourself" in description
    assert "Architecture/design → Planner" in description
    assert "Research/exploration → Explorer" in description
    assert "Implementation/testing → Engineer" in description
    assert "Documentation → Explorer" in description
    assert "Complex debugging → Engineer" in description


def test_delegate_tool_parameters() -> None:
    """Test that delegation tool has correct parameters."""
    tool = DelegateTaskTool()
    params = tool.parameters

    assert params["type"] == "object"
    assert "properties" in params
    assert "agent" in params["properties"]
    assert "task" in params["properties"]
    assert "done_when" in params["properties"]
    assert "context" in params["properties"]
    assert "files" in params["properties"]
    assert "background" in params["properties"]
    assert "requirements" in params["properties"]

    # Check required fields
    assert "required" in params
    assert "agent" in params["required"]
    assert "task" in params["required"]


def test_delegate_tool_kind() -> None:
    """Test that delegation tool is read-only (auto-approved)."""
    tool = DelegateTaskTool()
    assert tool.kind.name == "READ"
