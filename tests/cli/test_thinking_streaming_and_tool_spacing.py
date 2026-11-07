"""Tests for thinking token streaming and tool result spacing.

Issue 1: Thinking tokens appear on separate lines instead of
         accumulating into a single collapsible widget.
Issue 2: Tool result header missing space between emoji and "Result:".
"""


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

        with (
            patch.object(app, "query_one") as mock_query,
        ):
            # First call returns chat pane, second returns thinking pane
            mock_query.side_effect = [mock_pane, mock_thinking]

            msg = AgentThoughtMessage("Thinking about something", "Agent")

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

            msg = AgentThoughtMessage("Thinking...", source_agent=None)

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
        assert len(between.strip()) == 0 and len(between) >= 1, (
            f"Expected whitespace between emoji and 'Result:', got {between!r}"
        )

    async def test_tool_pane_result_has_separate_label_and_output(self, tmp_path, monkeypatch):
        """The shared evidence projection keeps a readable result label and body."""
        from henchman.cli.textual_messages import ToolCallResultMessage
        from henchman.cli.textual_widgets import ChatPane, ToolPane
        from tests.cli.ui_scenarios import InteractionApp, settle_layout

        monkeypatch.chdir(tmp_path)
        app = InteractionApp(tmp_path)
        async with app.run_test() as pilot:
            app.post_message(ToolCallResultMessage({"result": "command succeeded", "success": True}))
            await settle_layout(pilot)
            pane = app.query_one(ToolPane)
            assert pane._activity_store is app.query_one(ChatPane)._tool_activity
            assert "1. Result output\ncommand succeeded" in pane._projection
            assert "Outcome: Succeeded" in pane._projection

    async def test_tool_result_chat_pane_formatting(self, tmp_path, monkeypatch):
        """The compact result row separates status, tool and actor labels."""
        from henchman.cli.textual_messages import ToolCallResultMessage
        from henchman.cli.textual_widgets import ToolMessage
        from tests.cli.ui_scenarios import InteractionApp, settle_layout

        monkeypatch.chdir(tmp_path)
        app = InteractionApp(tmp_path)
        async with app.run_test() as pilot:
            app.post_message(ToolCallResultMessage(
                {"tool_name": "shell", "result": "output data", "success": True}, "Worker",
            ))
            await settle_layout(pilot)
            rows = list(app.query(ToolMessage))
            assert len(rows) == 1
            assert "Succeeded · shell · Worker" in str(rows[0].render())
            assert "output data" not in str(rows[0].render())
            rows[0].action_expand()
            assert "1. Result output\noutput data" in str(rows[0].render())
