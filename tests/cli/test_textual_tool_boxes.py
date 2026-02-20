"""Tests for Tool boxes in ChatPane."""

import pytest
from unittest.mock import MagicMock

from henchman.cli.textual_app import ChatPane, ToolMessage
from henchman.providers.base import ToolCall

def test_tool_message_collapsed():
    \"\"\"Test ToolMessage is collapsed by default.\"\"\"
    msg = ToolMessage(thought="test tool")
    # Check CSS classes or render
    assert \"display: none\" in msg.DEFAULT_CSS or \"collapsed\" in msg.classes
    rendered = msg.render()
    assert \"<div class=\"tool-content\">\" not in rendered  # No visible content initially
    assert \"Click to expand\" in rendered

def test_tool_message_expanded():
    \"\"\"Test ToolMessage expands and shows content.\"\"\"
    msg = ToolMessage(tool_call=MagicMock(name=\"test_tool\", arguments={ \"param\": \"value\" }))
    msg.toggle_expansion()
    rendered = msg.render()
    assert \"tool-content\" in rendered
    assert \"test_tool\" in rendered

def test_tool_message_append():
    \"\"\"Test appending to tool result.\"\"\"
    msg = ToolMessage(tool_call=MagicMock())
    msg.append(\"result content\")
    rendered = msg.render()
    assert \"result content\" in rendered
