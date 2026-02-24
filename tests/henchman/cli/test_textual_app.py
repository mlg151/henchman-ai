"""tests/henchman/cli/test_textual_app.py
Unit and widget tests for textual_app.py TUI components."""

# Henchman imports - patch imports if needed
import contextlib
from unittest.mock import MagicMock

import pytest

# Core imports for testing
from textual.app import App
from textual.containers import VerticalScroll

with contextlib.suppress(ImportError):
    from henchman.cli.textual_app import (
        ChatMessage,
        ChatPane,
        ThinkingMessage,
        ToolMessage,
    )

from henchman.providers.base import ToolCall


@pytest.fixture
def mock_app():
    """Mock Textual App for widget testing."""

    class MockApp(App[None]):
        pass

    app = MockApp()
    app.query_one = MagicMock(return_value=VerticalScroll())
    return app


@pytest.fixture
def chat_pane():
    """Fresh ChatPane instance."""
    return ChatPane()


class TestChatMessage:
    """Tests for ChatMessage widget."""

    def test_init_with_prefix_content(self):
        msg = ChatMessage("[bold cyan]Test:[/]", "Hello")
        assert msg._prefix == "[bold cyan]Test:[/]"
        assert msg._content == "Hello"

    def test_append_streams_content(self):
        msg = ChatMessage("[bold cyan]Test:[/]", "")
        msg.append("Hello ")
        msg.append("World")
        assert msg._content == "Hello World"
        # Check renderable has prefix + content
        assert "[bold cyan]Test:[/]" in str(msg.renderable)
        assert "Hello World" in str(msg.renderable)

    def test_set_content_replaces(self):
        msg = ChatMessage("[bold cyan]Test:[/]", "Old")
        msg.set_content("New")
        assert msg._content == "New"


class TestThinkingMessage:
    """Tests for FIXED ThinkingMessage: collapsed default, NO HTML tags visible."""

    def test_init_collapsed_no_html_tags(self):
        """Current code FAILS: shows HTML <div>, not collapsed."""
        msg = ThinkingMessage(thought="Detailed thinking here...", agent_name="AgentX")
        render_str = str(msg.render())
        # FAIL: HTML tags VISIBLE
        assert "<div class" not in render_str
        assert "thinking-header" not in render_str  # No raw CSS classes as text
        # COLLAPSED: only summary/header visible, NOT full content
        assert "AgentX thinking: Detailed" in render_str
        assert "(click to expand)" in render_str or "[click]" in render_str
        assert "Detailed thinking here..." not in render_str  # Full hidden
        assert msg._is_expanded is False

    def test_append_updates_header_and_hidden_content(self):
        msg = ThinkingMessage("", "AgentX")
        msg.append("Planning steps")
        render_str = str(msg.render())
        assert "thinking: Planning steps" in render_str

    def test_long_summary_truncates(self):
        long = "A" * 60
        msg = ThinkingMessage(long)
        summary = msg._get_summary()
        assert len(summary) <= 50
        assert summary.endswith("...")

    def test_toggle_expansion_changes_state(self):
        msg = ThinkingMessage("test")
        msg.toggle_expansion()
        assert msg._is_expanded is True
        msg.toggle_expansion()
        assert msg._is_expanded is False


class TestChatPane:
    """Tests for ChatPane methods."""

    def test_add_user_message_adds_widget(self, chat_pane):
        chat_pane.add_user_message("Hello")
        assert len(chat_pane.children) == 1
        child = chat_pane.children[0]
        assert isinstance(child, ChatMessage)
        assert "[bold green]You:[/]" in str(child.renderable)

    def test_begin_agent_stream_creates_active(self, chat_pane):
        msg = chat_pane.begin_agent_stream("AgentX")
        assert len(chat_pane._active) == 1
        assert "AgentX" in chat_pane._active
        assert isinstance(msg, ChatMessage)

    def test_append_agent_chunk_auto_begin(self, chat_pane):
        chat_pane.append_agent_chunk("AgentX", "hi")
        assert len(chat_pane.children) >= 1
        assert len(chat_pane._active) == 1

    def test_begin_thinking_stream(self, chat_pane):
        msg = chat_pane.begin_thinking_stream("AgentX")
        assert isinstance(msg, ThinkingMessage)
        assert len(chat_pane._active_thinking) == 1
        assert msg._agent_name == "AgentX"

    def test_append_thinking_auto_begin(self, chat_pane):
        chat_pane.append_thinking_chunk("AgentX", "think")
        assert (
            len([c for c in chat_pane.children if isinstance(c, ThinkingMessage)]) == 1
        )

    def test_clear_thinking_removes(self, chat_pane):
        chat_pane.begin_thinking_stream()
        chat_pane.clear_thinking_messages()
        assert len(chat_pane._active_thinking) == 0
        assert not any(isinstance(c, ThinkingMessage) for c in chat_pane.children)


class TestToolMessage:
    """Tests for NEW ToolMessage: collapsible tool call/result boxes."""

    @pytest.fixture
    def tool_message(self):

        tool_call = ToolCall(id="tc1", name="read_file", arguments={"path": "foo.py"})
        return ToolMessage(tool_call)  # Will fail until implemented

    def test_init_tool_box_collapsed(self, tool_message):
        render_str = str(tool_message.render())
        # Collapsed: header only
        assert "🔧 read_file(path=foo.py)" in render_str
        assert "arguments" not in render_str  # Full args hidden
        assert tool_message._is_expanded is False

    def test_toggle_shows_args(self, tool_message):
        tool_message.toggle_expansion()
        render_str = str(tool_message.render())
        assert '{"path": "foo.py"}' in render_str  # Full args visible


# Run with: pytest tests/henchman/cli/test_textual_app.py::TestThinkingMessage -v
