"""Tests for thinking token streaming and tool result spacing.

Issue 1: Thinking tokens appear on separate lines instead of
         accumulating into a single collapsible widget.
Issue 2: Tool result header missing space between emoji and "Result:".
"""

import pytest


# ---------------------------------------------------------------------------
# Issue 1: Thinking tokens should stream into a single widget
# ---------------------------------------------------------------------------


class TestThinkingStreamAccumulation:
    """Thinking chunks for the same agent must accumulate in one widget."""

    def test_on_agent_thought_uses_streaming_api(self):
        """on_agent_thought_message should use append_thinking_chunk, not add_thinking_message.

        Using add_thinking_message creates a NEW widget per thought chunk,
        causing each token to appear on a separate line. The streaming API
        (append_thinking_chunk) accumulates into a single widget.
        """
        from unittest.mock import MagicMock, patch

        from henchman.cli.textual_app import HenchmanTextualApp
        from henchman.cli.textual_messages import AgentThoughtMessage

        app = HenchmanTextualApp.__new__(HenchmanTextualApp)

        mock_pane = MagicMock()
        mock_thinking = MagicMock()

        with (patch.object(app, "query_one") as mock_query,):
            # First call returns chat pane, second returns thinking pane
            mock_query.side_effect = [mock_pane, mock_thinking]

            msg = AgentThoughtMessage.__new__(AgentThoughtMessage)
            msg.thought = "Thinking about something"
            msg.source_agent = "Agent"

            app.on_agent_thought_message(msg)

            # Should call append_thinking_chunk (streaming), NOT add_thinking_message
            mock_pane.append_thinking_chunk.assert_called_once_with(
                "Agent", "Thinking about something"
            )
            mock_pane.add_thinking_message.assert_not_called()

    def test_multiple_thoughts_same_agent_accumulate(self):
        """Multiple thought messages from same agent go into one widget."""
        from henchman.cli.textual_widgets import ChatPane

        pane = ChatPane()
        pane.append_thinking_chunk("Agent", "Hello ")
        pane.append_thinking_chunk("Agent", "world!")

        # Only one widget should exist for this agent
        assert "Agent" in pane._active_thinking
        widget = pane._active_thinking["Agent"]
        assert widget._content_text == "Hello world!"

    def test_different_agents_get_separate_widgets(self):
        """Different agents get separate thinking widgets."""
        from henchman.cli.textual_widgets import ChatPane

        pane = ChatPane()
        pane.append_thinking_chunk("Alice", "I think...")
        pane.append_thinking_chunk("Bob", "My thoughts...")

        assert "Alice" in pane._active_thinking
        assert "Bob" in pane._active_thinking
        assert pane._active_thinking["Alice"] is not pane._active_thinking["Bob"]

    def test_empty_source_agent_defaults_to_empty_string(self):
        """When source_agent is None, use empty string for streaming key."""
        from unittest.mock import MagicMock, patch

        from henchman.cli.textual_app import HenchmanTextualApp
        from henchman.cli.textual_messages import AgentThoughtMessage

        app = HenchmanTextualApp.__new__(HenchmanTextualApp)
        mock_pane = MagicMock()
        mock_thinking = MagicMock()

        with patch.object(app, "query_one") as mock_query:
            mock_query.side_effect = [mock_pane, mock_thinking]

            msg = AgentThoughtMessage.__new__(AgentThoughtMessage)
            msg.thought = "Thinking..."
            msg.source_agent = None

            app.on_agent_thought_message(msg)

            mock_pane.append_thinking_chunk.assert_called_once_with("", "Thinking...")


# ---------------------------------------------------------------------------
# Issue 2: Tool result header must have space after emoji
# ---------------------------------------------------------------------------


class TestToolResultSpacing:
    """Tool result display must have proper spacing."""

    def test_tool_result_header_has_space_after_emoji(self):
        """The ToolMessage header for results should have visible space after emoji."""
        from henchman.cli.textual_widgets import ToolMessage

        msg = ToolMessage(thought="Result: command succeeded")
        # render() returns the header text for collapsed state
        header = str(msg.render())
        assert "🛠️" in header
        assert "Result:" in header
        # Ensure there's whitespace between emoji and Result
        idx_emoji = header.index("🛠️")
        idx_result = header.index("Result:")
        between = header[idx_emoji + len("🛠️") : idx_result]
        assert (
            len(between.strip()) == 0 and len(between) >= 1
        ), f"Expected whitespace between emoji and 'Result:', got {between!r}"

    def test_tool_pane_result_has_space_after_arrow(self):
        """The tool pane '← Result' should have space after arrow."""
        from unittest.mock import MagicMock, patch

        from henchman.cli.textual_app import HenchmanTextualApp
        from henchman.cli.textual_messages import ToolCallResultMessage

        app = HenchmanTextualApp.__new__(HenchmanTextualApp)

        mock_pane = MagicMock()
        mock_tool_pane = MagicMock()

        with patch.object(app, "query_one") as mock_query:
            mock_query.side_effect = [mock_pane, mock_tool_pane]

            msg = ToolCallResultMessage.__new__(ToolCallResultMessage)
            msg.result = "success"

            app.on_tool_call_result_message(msg)

            # Check the tool pane .write() call has space after ←
            write_call = mock_tool_pane.write.call_args[0][0]
            assert "← " in write_call, f"Missing space after ←: {write_call!r}"

    def test_tool_result_chat_pane_formatting(self):
        """Tool result in chat pane should use 'Result: ' prefix with space."""
        from unittest.mock import MagicMock, patch

        from henchman.cli.textual_app import HenchmanTextualApp
        from henchman.cli.textual_messages import ToolCallResultMessage

        app = HenchmanTextualApp.__new__(HenchmanTextualApp)

        mock_pane = MagicMock()
        mock_tool_pane = MagicMock()

        with patch.object(app, "query_one") as mock_query:
            mock_query.side_effect = [mock_pane, mock_tool_pane]

            msg = ToolCallResultMessage.__new__(ToolCallResultMessage)
            msg.result = "output data"

            app.on_tool_call_result_message(msg)

            # Check add_tool_message was called with "Result: " (with space)
            call_args = mock_pane.add_tool_message.call_args[0][0]
            assert call_args.startswith(
                "Result: "
            ), f"Expected 'Result: ' prefix, got: {call_args!r}"
