"""Tests for BUG-028 through BUG-035: TUI/Textual widget bugs.

Each test class covers one bug using TDD: first verify the bug exists,
then verify the fix resolves it.
"""

import inspect
from unittest.mock import MagicMock

from henchman.cli.textual_mixins import (
    _HistoryMixin,
    _InitMixin,
    _InputHandlerMixin,
    _MessageHandlerMixin,
)
from henchman.cli.textual_widgets import (
    ChatMessage,
    ChatPane,
    HenchmanTextArea,
)

# ===================================================================
# BUG-028: Agent errors leave stale entries in ChatPane._active
# ===================================================================


class TestBug028StaleActiveEntries:
    """BUG-028: Exception in process_user_input must call finish_agent_stream."""

    def test_process_user_input_calls_finish_agent_stream_on_exception(self):
        """process_user_input must call finish_agent_stream for active agents
        in both except and finally blocks."""
        source = inspect.getsource(_InputHandlerMixin.process_user_input)

        # Verify the fix pattern: finish_agent_stream is called for all
        # active agents in the exception handlers
        assert "chat.finish_agent_stream" in source, (
            "process_user_input must call finish_agent_stream"
        )

        # The except Exception block should call finish_agent_stream
        # Look for it between 'except Exception' and 'finally:'
        assert "finish_agent_stream" in source.split("finally:")[0].split(
            "except Exception"
        )[-1], (
            "finish_agent_stream must be called in the except Exception block"
        )

        # Also check the CancelledError handler
        assert "finish_agent_stream" in source.split(
            "except asyncio.CancelledError"
        ).pop(1).split("except")[0] if "except asyncio.CancelledError" in source else (
            "finish_agent_stream must be called in CancelledError handler"
        )

    def test_source_shows_loop_over_active_agents(self):
        """The fix should iterate chat._active to finish all active streams."""
        source = inspect.getsource(_InputHandlerMixin.process_user_input)
        # Should iterate over active items (for name in list(chat._active))
        assert "for " in source and "_active" in source, (
            "Should iterate over active agents to finish streams"
        )


# ===================================================================
# BUG-029: No finish_thinking_stream method
# ===================================================================


class TestBug029FinishThinkingStream:
    """BUG-029: Missing finish_thinking_stream() method on ChatPane."""

    def test_finish_thinking_stream_exists(self):
        assert hasattr(ChatPane, "finish_thinking_stream")

    def test_finish_thinking_stream_removes_entry(self):
        pane = ChatPane()
        pane._active_thinking = {"Assistant": MagicMock()}
        pane.finish_thinking_stream("Assistant")
        assert "Assistant" not in pane._active_thinking

    def test_finish_thinking_stream_noop_for_missing(self):
        pane = ChatPane()
        pane._active_thinking = {}
        # Should not raise
        pane.finish_thinking_stream("Nonexistent")

    def test_finish_thinking_stream_does_not_clear_other_agents(self):
        pane = ChatPane()
        pane._active_thinking = {"A": MagicMock(), "B": MagicMock()}
        pane.finish_thinking_stream("A")
        assert "B" in pane._active_thinking
        assert "A" not in pane._active_thinking


# ===================================================================
# BUG-030: StatusBar and Footer reversed stacking
# ===================================================================


class TestBug030StatusBarFooterStacking:
    """BUG-030: compose() yields Footer before StatusBar."""

    def test_compose_order_footer_before_statusbar(self):
        from henchman.cli.textual_app import HenchmanTextualApp

        source = inspect.getsource(HenchmanTextualApp.compose)
        statusbar_line = None
        footer_line = None
        for i, line in enumerate(source.split("\n")):
            striped = line.strip()
            if "StatusBar" in striped and "yield" in striped:
                statusbar_line = i
            if "Footer" in striped and "yield" in striped:
                footer_line = i
        assert footer_line is not None and statusbar_line is not None
        assert footer_line < statusbar_line


# ===================================================================
# BUG-031: HenchmanTextArea on_key is dead code
# ===================================================================


class TestBug031DeadOnKeyHandler:
    """BUG-031: on_key handler removed since BINDINGS handle enter/shift+enter."""

    def test_on_key_not_overridden(self):
        assert "on_key" not in HenchmanTextArea.__dict__

    def test_helper_methods_removed(self):
        assert not hasattr(HenchmanTextArea, "_handle_enter_key")
        assert not hasattr(HenchmanTextArea, "_handle_shift_enter_key")


# ===================================================================
# BUG-032: History navigation discards unsaved input buffer
# ===================================================================


class TestBug032HistoryDiscardsInput:
    """BUG-032: _navigate_history saves/restores _saved_input_buffer."""

    def test_history_saves_input_before_overwriting(self):
        text = "unsent input"
        obj = MagicMock()
        obj.command_history = ["msg1", "msg2"]
        obj.history_index = 2

        widget = MagicMock()
        widget.text = text
        obj.query_one = MagicMock(return_value=widget)

        _HistoryMixin._navigate_history(obj, -1)
        # Saved before populating history text
        assert obj._saved_input_buffer == text

    def test_history_restores_saved_input_when_past_newest(self):
        obj = MagicMock()
        obj.command_history = ["msg1", "msg2"]
        obj.history_index = 1

        widget = MagicMock()
        widget.text = "anything"
        obj.query_one = MagicMock(return_value=widget)
        obj._saved_input_buffer = "my saved text"

        _HistoryMixin._navigate_history(obj, 1)
        # When past newest, restores saved buffer
        loaded = widget.load_text.call_args[0][0]
        assert loaded == "my saved text"


# ===================================================================
# BUG-033: First chunk not scrolled into view
# ===================================================================


class TestBug033FirstChunkScrolling:
    """BUG-033: Scroll after append regardless of newly_created."""

    def test_no_if_not_newly_created_guard(self):
        source = inspect.getsource(ChatPane.append_agent_chunk)
        assert "if not newly_created" not in source

    def test_scroll_called_after_first_chunk(self):
        pane = ChatPane()
        pane.mount = MagicMock()
        pane._scroll_to_bottom = MagicMock()
        pane._active = {}
        pane.append_agent_chunk("Assistant", "Hello")
        assert pane._scroll_to_bottom.called

    def test_scroll_called_after_subsequent_chunk(self):
        pane = ChatPane()
        pane.mount = MagicMock()
        pane._scroll_to_bottom = MagicMock()
        pane._active = {"Assistant": MagicMock(spec=ChatMessage)}
        pane.append_agent_chunk("Assistant", " World")
        assert pane._scroll_to_bottom.called


# ===================================================================
# BUG-034: _streaming_messages dict is never populated
# ===================================================================


class TestBug034DeadStreamingMessages:
    """BUG-034: _streaming_messages removed from _init_state and handler."""

    def test_no_streaming_messages_in_init_state(self):
        source = inspect.getsource(_InitMixin._init_state)
        assert "_streaming_messages" not in source

    def test_no_streaming_messages_in_finished_handler(self):
        source = inspect.getsource(_MessageHandlerMixin.on_agent_finished_message)
        assert "_streaming_messages" not in source


# ===================================================================
# BUG-035: ChatPane.on_mount reinitializes tracking maps
# ===================================================================


class TestBug035OnMountReinitializes:
    """BUG-035: ChatPane.on_mount removed to avoid wiping state."""

    def test_on_mount_not_overridden(self):
        assert "on_mount" not in ChatPane.__dict__
