"""Tests for thinking messages in chat window (TUI)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from henchman.cli.textual_app import (
    ChatPane,
    HenchmanTextualApp,
    TextualConfig,
)


class TestThinkingInChat:
    """Tests for thinking messages displayed in chat window."""

    @pytest.fixture
    def mock_provider(self):
        """Create a mock provider."""
        provider = MagicMock()
        provider.name = "test-provider"
        return provider

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings."""
        settings = MagicMock()
        settings.ui.theme = "dark"
        settings.ui.keybindings = {}
        return settings

    @pytest.fixture
    def textual_app(self, mock_provider, mock_settings):
        """Create a Textual app instance for testing."""
        config = TextualConfig()
        app = HenchmanTextualApp(
            provider=mock_provider,
            config=config,
            settings=mock_settings,
            environment_context="Test context",
        )
        return app

    def test_thinking_message_widget_exists(self):
        """Test that ThinkingMessage widget is defined."""
        from henchman.cli.textual_widgets import ThinkingMessage

        assert ThinkingMessage is not None

    def test_tool_message_widget_exists(self):
        """Test that ToolMessage widget is defined."""
        from henchman.cli.textual_widgets import ToolMessage

        assert ToolMessage is not None

    def test_thinking_message_styling(self):
        """Test that ThinkingMessage has proper styling."""
        from henchman.cli.textual_widgets import ThinkingMessage

        msg = ThinkingMessage("Test thought", "Agent")
        # Check that it has the thinking prefix
        assert "🤔" in str(msg.render())
        # Check that it has dim styling class
        assert "thinking-message" in msg.classes

    def test_tool_message_styling(self):
        """Test that ToolMessage has proper styling."""
        from henchman.cli.textual_widgets import ToolMessage

        msg = ToolMessage("Test tool call")
        # Check that it has the tool prefix
        assert "🛠️" in str(msg.render())
        # Check that it has tool styling class
        assert "tool-message" in msg.classes

    def test_thinking_message_accumulates_content(self):
        """Test that ThinkingMessage accumulates content as paragraphs."""
        from henchman.cli.textual_widgets import ThinkingMessage

        msg = ThinkingMessage("Initial thought", "Agent")
        initial_content = str(msg.render())

        # Append more content
        msg.append(" More thinking.")

        # Content should be accumulated in internal state
        assert "Initial thought" in msg._content_text
        assert "More thinking" in msg._content_text

        # When expanded, full content is visible
        msg.toggle_expansion()
        updated_content = str(msg.render())
        assert "Initial thought" in updated_content
        assert "More thinking" in updated_content
        # Should be in paragraph format, not line-by-line
        assert "\n\n" not in updated_content or updated_content.count("\n") < 3

    def test_thinking_message_not_token_by_token(self):
        """Test that thinking messages don't show one token per line."""
        from henchman.cli.textual_widgets import ThinkingMessage

        msg = ThinkingMessage("", "Agent")

        # Simulate token-by-token streaming
        tokens = ["This", " is", " a", " complete", " sentence."]
        for token in tokens:
            msg.append(token)

        final_content = str(msg.render())
        # Should not have excessive newlines for each token
        line_count = final_content.count("\n")
        assert line_count < 5  # Reasonable paragraph formatting

    def test_chat_pane_displays_thinking_messages(self):
        """Test that ChatPane can display ThinkingMessage widgets."""
        pane = ChatPane()

        # Use add_thinking_message API (handles unmounted case)
        from henchman.cli.textual_widgets import ThinkingMessage

        pane.add_thinking_message("Test thought", "Agent")

        # Should be in children
        assert len(pane.children) == 1
        assert isinstance(pane.children[0], ThinkingMessage)

    def test_chat_pane_displays_tool_messages(self):
        """Test that ChatPane can display ToolMessage widgets."""
        pane = ChatPane()

        # Use add_tool_message API (handles unmounted case)
        from henchman.cli.textual_widgets import ToolMessage

        pane.add_tool_message("Test tool call")

        # Should be in children
        assert len(pane.children) == 1
        assert isinstance(pane.children[0], ToolMessage)

    def test_thinking_message_with_agent_name(self):
        """Test that thinking messages show agent name."""
        from henchman.cli.textual_widgets import ThinkingMessage

        msg = ThinkingMessage("Planning approach", "Engineer")
        content = str(msg.render())

        assert "Engineer" in content
        assert "🤔" in content
        assert "Planning approach" in content

    def test_tool_message_with_thought(self):
        """Test that tool messages show tool thought/description."""
        from henchman.cli.textual_widgets import ToolMessage

        msg = ToolMessage("Reading file contents")
        content = str(msg.render())

        assert "🛠️" in content
        assert "Reading file contents" in content

    def test_chat_pane_clears_thinking_messages(self):
        """Test that ChatPane can clear thinking messages."""
        pane = ChatPane()

        from henchman.cli.textual_widgets import ToolMessage

        # Add mixed messages via helper methods
        pane.add_thinking_message("Thought 1", "Agent")
        pane.add_tool_message("Tool 1")
        pane.add_thinking_message("Thought 2", "Agent")

        assert len(pane.children) == 3

        # Clear thinking messages
        pane.clear_thinking_messages()

        # Should only have tool message left
        assert len(pane.children) == 1
        assert isinstance(pane.children[0], ToolMessage)

    def test_no_separate_thinking_pane_in_layout(self):
        """Test that thinking content flows through ChatPane.

        ThinkingPane still exists for backward compatibility but the primary
        display is via ThinkingMessage widgets in ChatPane.
        """
        pane = ChatPane()
        from henchman.cli.textual_widgets import ThinkingMessage

        msg = pane.add_thinking_message("Test thought", "Agent")
        assert isinstance(msg, ThinkingMessage)
        thinking_msgs = [c for c in pane.children if isinstance(c, ThinkingMessage)]
        assert len(thinking_msgs) == 1

    def test_no_separate_tool_pane_in_layout(self):
        """Test that tool content flows through ChatPane.

        ToolPane still exists for backward compatibility but the primary
        display is via ToolMessage widgets in ChatPane.
        """
        pane = ChatPane()
        from henchman.cli.textual_widgets import ToolMessage

        msg = pane.add_tool_message("Test tool")
        assert isinstance(msg, ToolMessage)
        tool_msgs = [c for c in pane.children if isinstance(c, ToolMessage)]
        assert len(tool_msgs) == 1
