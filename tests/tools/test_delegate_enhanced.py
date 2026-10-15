"""Tests for enhanced delegation tool."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from src.henchman.tools.builtins.delegate import DelegateTaskTool


def test_delegate_tool_has_enhanced_description() -> None:
    """Test that delegation tool includes enhanced guidance."""
    tool = DelegateTaskTool()
    description = tool.description

    # Check for essential guidance sections
    assert "Delegate a task to a specialist agent" in description
    assert "CLEAN context" in description
    assert "MUST provide all relevant information" in description
    assert "Do not assume the agent remembers anything" in description


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
    assert "depends_on" in params["properties"]

    # Check required fields
    assert "required" in params
    assert "agent" in params["required"]
    assert "task" in params["required"]


def test_delegate_tool_kind() -> None:
    """Delegation can execute specialist actions and needs execution policy."""
    tool = DelegateTaskTool()
    assert tool.kind.name == "EXECUTE"


def test_delegate_tool_files_description_emphasizes_importance() -> None:
    """Test that files field description emphasizes importance (#3)."""
    tool = DelegateTaskTool()
    files_desc = tool.parameters["properties"]["files"]["description"]
    assert "STRONGLY RECOMMENDED" in files_desc


def test_delegate_tool_depends_on_field() -> None:
    """Test that depends_on field exists with correct schema (#10)."""
    tool = DelegateTaskTool()
    depends_on = tool.parameters["properties"]["depends_on"]
    assert depends_on["type"] == "string"
    assert "prior agent work" in depends_on["description"]
