"""Tests for Tool boxes in ChatPane."""

from unittest.mock import MagicMock

from henchman.cli.textual_app import ToolMessage


def test_tool_message_collapsed():
    """Test ToolMessage is collapsed by default."""
    msg = ToolMessage(thought="test tool")
    assert msg._is_expanded is False
    rendered = str(msg.render())
    assert "🛠️  test tool" in rendered


def test_tool_message_expanded():
    """Test ToolMessage expands and shows content."""
    tc = MagicMock()
    tc.name = "test_tool"
    tc.arguments = {"param": "value"}
    msg = ToolMessage(tool_call=tc)
    msg.toggle_expansion()
    assert msg._is_expanded is True
    assert "expanded" in msg.classes
    rendered = str(msg.render())
    assert "test_tool" in rendered
    assert '"param"' in rendered


def test_tool_message_append():
    """Test appending to tool result."""
    msg = ToolMessage(tool_call=MagicMock())
    msg.append("result content")
    rendered = str(msg.render())
    # Appended content visible in expanded view
    msg.toggle_expansion()
    rendered_expanded = str(msg.render())
    assert "result content" in rendered_expanded
