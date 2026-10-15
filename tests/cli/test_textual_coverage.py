"""Tests for textual_bridge.py and textual_screens.py coverage."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from henchman.core.events import AgentEvent, EventType

if TYPE_CHECKING:
    from henchman.cli.textual_bridge import EventBridge, MessagePoster, TuiConsoleAdapter
    from henchman.tools.base import ConfirmationRequest

# ---------------------------------------------------------------------------
# textual_bridge.py tests
# ---------------------------------------------------------------------------


class TestTuiConsoleAdapter:
    """Tests for TuiConsoleAdapter class."""

    def _make_adapter(self) -> TuiConsoleAdapter:
        """Create a TuiConsoleAdapter with mock app."""
        from henchman.cli.textual_bridge import TuiConsoleAdapter

        app = MagicMock()
        return TuiConsoleAdapter(app)

    def test_init_creates_rich_console(self) -> None:
        """Test TuiConsoleAdapter creates a Rich console on init."""
        adapter = self._make_adapter()
        assert adapter.console is not None

    def test_flush_to_chat_with_content(self) -> None:
        """Test flush_to_chat posts message when buffer has content."""
        from henchman.cli.textual_bridge import TuiConsoleAdapter

        app = MagicMock()
        adapter = TuiConsoleAdapter(app)
        adapter._buf.write("Some output text")
        adapter._buf.seek(0)
        adapter.flush_to_chat()
        app.post_message.assert_called_once()

    def test_flush_to_chat_empty_buffer(self) -> None:
        """Test flush_to_chat does not post when buffer is empty."""
        adapter = self._make_adapter()
        adapter.flush_to_chat()
        adapter._app.post_message.assert_not_called()

    def test_print_calls_flush(self) -> None:
        """Test print writes to buffer and flushes."""
        adapter = self._make_adapter()
        adapter.print("Hello world")
        # If something was in buffer, post_message would be called
        # (or nothing if output was whitespace-only)


class TestMessageCreationHelpers:
    """Tests for message creation helper functions."""

    def test_extract_dict_field_with_dict(self) -> None:
        """Test _extract_dict_field extracts field from dict data."""
        from henchman.cli.textual_bridge import _extract_dict_field

        event = AgentEvent(type=EventType.AGENT_STARTED, data={"agent": "engineer", "task": "code"})
        result = _extract_dict_field(event, "agent")
        assert result == "engineer"

    def test_extract_dict_field_missing_key(self) -> None:
        """Test _extract_dict_field returns default for missing key."""
        from henchman.cli.textual_bridge import _extract_dict_field

        event = AgentEvent(type=EventType.AGENT_STARTED, data={"agent": "engineer"})
        result = _extract_dict_field(event, "missing_key", "default_val")
        assert result == "default_val"

    def test_extract_dict_field_not_dict(self) -> None:
        """Test _extract_dict_field returns default when data is not dict."""
        from henchman.cli.textual_bridge import _extract_dict_field

        event = AgentEvent(type=EventType.CONTENT, data="string content")
        result = _extract_dict_field(event, "key", "fallback")
        assert result == "fallback"

    def test_extract_dict_field_none_data(self) -> None:
        """Test _extract_dict_field returns default when data is None."""
        from henchman.cli.textual_bridge import _extract_dict_field

        event = AgentEvent(type=EventType.CONTENT, data=None)
        result = _extract_dict_field(event, "key", "fallback")
        assert result == "fallback"


class TestMessagePoster:
    """Tests for MessagePoster class."""

    def _make_poster(self) -> MessagePoster:
        """Create a MessagePoster with mock app."""
        from henchman.cli.textual_bridge import MessagePoster

        app = MagicMock()
        return MessagePoster(app)

    def test_post_calls_app(self) -> None:
        """Test post sends message to app."""
        poster = self._make_poster()
        msg = MagicMock()
        poster.post(msg)
        poster.app.post_message.assert_called_once_with(msg)

    def test_post_message_with_data(self) -> None:
        """Test post_message creates and sends message with event data."""
        from henchman.cli.textual_bridge import AgentContentMessage, MessagePoster

        app = MagicMock()
        poster = MessagePoster(app)
        event = AgentEvent(type=EventType.CONTENT, data="hello")
        poster.post_message(event, AgentContentMessage)
        app.post_message.assert_called_once()

    def test_post_message_no_data(self) -> None:
        """Test post_message skips when event has no data."""
        from henchman.cli.textual_bridge import AgentContentMessage, MessagePoster

        app = MagicMock()
        poster = MessagePoster(app)
        event = AgentEvent(type=EventType.FINISHED, data=None)
        poster.post_message(event, AgentContentMessage)
        app.post_message.assert_not_called()

    def test_post_status_message(self) -> None:
        """Test post_status_message posts a status update."""
        from henchman.cli.textual_bridge import MessagePoster

        app = MagicMock()
        poster = MessagePoster(app)
        event = AgentEvent(type=EventType.CONTENT, data="data")
        poster.post_status_message(event, "Processing...")
        app.post_message.assert_called_once()
class TestEventBridge:
    """Tests for EventBridge class."""

    def _make_bridge(self) -> EventBridge:
        """Create an EventBridge with mock app."""
        from henchman.cli.textual_bridge import EventBridge

        app = MagicMock()
        return EventBridge(app)

    def test_dispatch_content_event(self) -> None:
        """Test dispatch handles CONTENT event."""
        bridge = self._make_bridge()
        event = AgentEvent(type=EventType.CONTENT, data="hello")
        bridge._dispatch(event)
        bridge.app.post_message.assert_called()

    def test_dispatch_thought_event(self) -> None:
        """Test dispatch handles THOUGHT event."""
        bridge = self._make_bridge()
        event = AgentEvent(type=EventType.THOUGHT, data="thinking...")
        bridge._dispatch(event)
        bridge.app.post_message.assert_called()

    def test_dispatch_tool_call_request(self) -> None:
        """Test dispatch handles TOOL_CALL_REQUEST event."""
        from henchman.providers.base import ToolCall
        bridge = self._make_bridge()
        tc = ToolCall(id="tc-1", name="read_file", arguments={})
        event = AgentEvent(type=EventType.TOOL_CALL_REQUEST, data=tc)
        bridge._dispatch(event)
        bridge.app.post_message.assert_called()

    def test_dispatch_error_event(self) -> None:
        """Test dispatch handles ERROR event."""
        bridge = self._make_bridge()
        event = AgentEvent(type=EventType.ERROR, data="Something failed")
        bridge._dispatch(event)
        bridge.app.post_message.assert_called()

    def test_dispatch_finished_event(self) -> None:
        """Test dispatch handles FINISHED event."""
        bridge = self._make_bridge()
        event = AgentEvent(type=EventType.FINISHED, data=None)
        bridge._dispatch(event)
        bridge.app.post_message.assert_called()

    def test_dispatch_context_compacted(self) -> None:
        """Test dispatch handles CONTEXT_COMPACTED event."""
        bridge = self._make_bridge()
        event = AgentEvent(type=EventType.CONTEXT_COMPACTED, data=None)
        bridge._dispatch(event)
        bridge.app.post_message.assert_called()

    def test_dispatch_turn_status(self) -> None:
        """Test dispatch handles TURN_STATUS event."""
        bridge = self._make_bridge()
        event = AgentEvent(
            type=EventType.TURN_STATUS,
            data={"iteration": 1, "limit": 25, "tokens": 1000, "cost": 0.001},
        )
        bridge._dispatch(event)
        bridge.app.post_message.assert_called()

    def test_dispatch_agent_started(self) -> None:
        """Test dispatch handles AGENT_STARTED event."""
        bridge = self._make_bridge()
        event = AgentEvent(type=EventType.AGENT_STARTED, data={"agent": "engineer"})
        bridge._dispatch(event)
        bridge.app.post_message.assert_called()

    def test_dispatch_agent_completed(self) -> None:
        """Test dispatch handles AGENT_COMPLETED event."""
        bridge = self._make_bridge()
        event = AgentEvent(
            type=EventType.AGENT_COMPLETED,
            data={"agent": "engineer", "summary": "done"},
        )
        bridge._dispatch(event)
        bridge.app.post_message.assert_called()

    def test_dispatch_agent_delegated(self) -> None:
        """Test dispatch handles AGENT_DELEGATED event."""
        bridge = self._make_bridge()
        event = AgentEvent(
            type=EventType.AGENT_DELEGATED,
            data={"from": "orchestrator", "to": "engineer", "reason": ""},
        )
        bridge._dispatch(event)
        bridge.app.post_message.assert_called()

    def test_dispatch_agent_message(self) -> None:
        """Test dispatch handles AGENT_MESSAGE event."""
        bridge = self._make_bridge()
        event = AgentEvent(
            type=EventType.AGENT_MESSAGE,
            data="Task completed",
        )
        bridge._dispatch(event)
        bridge.app.post_message.assert_called()

    def test_create_handler_with_message_class(self) -> None:
        """Test _create_handler with message_class."""
        from henchman.cli.textual_bridge import AgentContentMessage, EventBridge

        app = MagicMock()
        bridge = EventBridge(app)
        handler = bridge._create_handler(message_class=AgentContentMessage)
        assert callable(handler)

    def test_create_handler_with_status_text(self) -> None:
        """Test _create_handler with status_text."""
        from henchman.cli.textual_bridge import EventBridge

        app = MagicMock()
        bridge = EventBridge(app)
        handler = bridge._create_handler(status_text="Processing...")
        assert callable(handler)

    def test_create_handler_with_prefix(self) -> None:
        """Test _create_handler with prefix."""
        from henchman.cli.textual_bridge import EventBridge

        app = MagicMock()
        bridge = EventBridge(app)
        handler = bridge._create_handler(prefix="[agent] ")
        assert callable(handler)

    def test_create_handler_raises_without_options(self) -> None:
        """Test _create_handler raises ValueError when no options provided."""
        from henchman.cli.textual_bridge import EventBridge

        app = MagicMock()
        bridge = EventBridge(app)
        with pytest.raises(ValueError, match="Must specify one of"):
            bridge._create_handler()

    def test_on_tool_req_with_data(self) -> None:
        """Test _on_tool_req posts ToolCallRequestMessage."""
        from henchman.cli.textual_bridge import EventBridge
        from henchman.providers.base import ToolCall

        app = MagicMock()
        bridge = EventBridge(app)
        tc = ToolCall(id="tc-1", name="read_file", arguments={})
        event = AgentEvent(type=EventType.TOOL_CALL_REQUEST, data=tc)
        bridge._on_tool_req(event)
        app.post_message.assert_called_once()

    def test_on_error_with_data(self) -> None:
        """Test _on_error posts error message."""
        from henchman.cli.textual_bridge import EventBridge

        app = MagicMock()
        bridge = EventBridge(app)
        event = AgentEvent(type=EventType.ERROR, data="Error message")
        bridge._on_error(event)
        assert app.post_message.call_count >= 1

    def test_on_finished(self) -> None:
        """Test _on_finished posts finished message."""
        from henchman.cli.textual_bridge import EventBridge

        app = MagicMock()
        bridge = EventBridge(app)
        event = AgentEvent(type=EventType.FINISHED, data=None)
        bridge._on_finished(event)
        app.post_message.assert_called_once()

    def test_on_ctx_compact(self) -> None:
        """Test _on_ctx_compact posts compaction notice."""
        from henchman.cli.textual_bridge import EventBridge

        app = MagicMock()
        bridge = EventBridge(app)
        event = AgentEvent(type=EventType.CONTEXT_COMPACTED, data=None)
        bridge._on_ctx_compact(event)
        assert app.post_message.call_count >= 1

    def test_on_turn_status(self) -> None:
        """Test _on_turn_status posts status update."""
        from henchman.cli.textual_bridge import EventBridge

        app = MagicMock()
        bridge = EventBridge(app)
        event = AgentEvent(
            type=EventType.TURN_STATUS,
            data={"iteration": 1, "limit": 25},
        )
        bridge._on_turn_status(event)
        app.post_message.assert_called()

    def test_on_turn_status_no_data(self) -> None:
        """Test _on_turn_status with no data."""
        from henchman.cli.textual_bridge import EventBridge

        app = MagicMock()
        bridge = EventBridge(app)
        event = AgentEvent(type=EventType.TURN_STATUS, data=None)
        bridge._on_turn_status(event)

    def test_on_agent_start(self) -> None:
        """Test _on_agent_start posts status message."""
        from henchman.cli.textual_bridge import EventBridge

        app = MagicMock()
        bridge = EventBridge(app)
        event = AgentEvent(type=EventType.AGENT_STARTED, data={"agent": "engineer"})
        bridge._on_agent_start(event)
        app.post_message.assert_called()

    def test_on_agent_done(self) -> None:
        """Test _on_agent_done posts completion message."""
        from henchman.cli.textual_bridge import EventBridge

        app = MagicMock()
        bridge = EventBridge(app)
        event = AgentEvent(
            type=EventType.AGENT_COMPLETED,
            data={"agent": "engineer", "summary": "task done"},
        )
        bridge._on_agent_done(event)
        app.post_message.assert_called()

    def test_on_delegated(self) -> None:
        """Test _on_delegated posts delegation message."""
        from henchman.cli.textual_bridge import EventBridge

        app = MagicMock()
        bridge = EventBridge(app)
        event = AgentEvent(
            type=EventType.AGENT_DELEGATED,
            data={"from": "orchestrator", "to": "engineer", "reason": "need coding"},
        )
        bridge._on_delegated(event)
        assert app.post_message.call_count >= 1

    def test_on_agent_msg(self) -> None:
        """Test _on_agent_msg posts message."""
        from henchman.cli.textual_bridge import EventBridge

        app = MagicMock()
        bridge = EventBridge(app)
        event = AgentEvent(type=EventType.AGENT_MESSAGE, data="Task complete")
        bridge._on_agent_msg(event)
        app.post_message.assert_called_once()

    def test_on_agent_msg_no_data(self) -> None:
        """Test _on_agent_msg with no data."""
        from henchman.cli.textual_bridge import EventBridge

        app = MagicMock()
        bridge = EventBridge(app)
        event = AgentEvent(type=EventType.AGENT_MESSAGE, data=None)
        bridge._on_agent_msg(event)
        app.post_message.assert_not_called()

    def test_update_status_bar(self) -> None:
        """Test _update_status_bar updates status bar widget."""
        from henchman.cli.textual_bridge import EventBridge

        app = MagicMock()
        bridge = EventBridge(app)
        bridge._update_status_bar({"tokens": 1000, "cost": 0.002})
        # Should try to query and update status bar

    def test_update_status_bar_no_tokens(self) -> None:
        """Test _update_status_bar with empty data."""
        from henchman.cli.textual_bridge import EventBridge

        app = MagicMock()
        bridge = EventBridge(app)
        bridge._update_status_bar({})
        # Should do nothing (no tokens or cost)


# ---------------------------------------------------------------------------
# textual_screens.py tests
# ---------------------------------------------------------------------------


class TestConfirmToolScreen:
    """Tests for ConfirmToolScreen."""

    def _make_request(self) -> ConfirmationRequest:
        """Create a test ConfirmationRequest."""
        from henchman.tools.base import ConfirmationRequest

        return ConfirmationRequest(
            tool_name="shell",
            params={"command": "ls"},
            description="Run shell command",
            risk_level="medium",
        )

    def test_init(self) -> None:
        """Test ConfirmToolScreen can be instantiated."""
        from henchman.cli.textual_screens import ConfirmToolScreen

        request = self._make_request()
        screen = ConfirmToolScreen(request)
        assert screen._request is request

    def test_build_params_label_with_params(self) -> None:
        """Test _build_params_label returns label when params present."""
        from henchman.cli.textual_screens import ConfirmToolScreen

        request = self._make_request()
        screen = ConfirmToolScreen(request)
        labels = screen._build_params_label()
        assert len(labels) == 1

    def test_build_params_label_no_params(self) -> None:
        """Test _build_params_label returns empty list when no params."""
        from henchman.cli.textual_screens import ConfirmToolScreen
        from henchman.tools.base import ConfirmationRequest

        request = ConfirmationRequest(
            tool_name="shell",
            params=None,
            description="Run shell",
        )
        screen = ConfirmToolScreen(request)
        labels = screen._build_params_label()
        assert len(labels) == 0

    def test_build_params_label_non_serializable(self) -> None:
        """Test _build_params_label handles non-JSON-serializable params."""
        from henchman.cli.textual_screens import ConfirmToolScreen
        from henchman.tools.base import ConfirmationRequest

        # Use object that can't be JSON serialized
        request = ConfirmationRequest(
            tool_name="shell",
            params={"obj": object()},  # Not JSON serializable
            description="Run shell",
        )
        screen = ConfirmToolScreen(request)
        # Should not raise
        labels = screen._build_params_label()
        assert len(labels) == 1

    def test_action_approve(self) -> None:
        """Test action_approve calls dismiss with True."""
        from henchman.cli.textual_screens import ConfirmToolScreen

        request = self._make_request()
        screen = ConfirmToolScreen(request)
        screen.dismiss = MagicMock()
        screen.action_approve()
        screen.dismiss.assert_called_once_with(result=True)

    def test_action_deny(self) -> None:
        """Test action_deny calls dismiss with False."""
        from henchman.cli.textual_screens import ConfirmToolScreen

        request = self._make_request()
        screen = ConfirmToolScreen(request)
        screen.dismiss = MagicMock()
        screen.action_deny()
        screen.dismiss.assert_called_once_with(result=False)

    def test_on_button_pressed_yes(self) -> None:
        """Test on_button_pressed with yes button."""
        from henchman.cli.textual_screens import ConfirmToolScreen

        request = self._make_request()
        screen = ConfirmToolScreen(request)
        screen.dismiss = MagicMock()
        event = MagicMock()
        event.button.id = "btn-yes"
        screen.on_button_pressed(event)
        screen.dismiss.assert_called_once_with(True)

    def test_on_button_pressed_no(self) -> None:
        """Test on_button_pressed with no button."""
        from henchman.cli.textual_screens import ConfirmToolScreen

        request = self._make_request()
        screen = ConfirmToolScreen(request)
        screen.dismiss = MagicMock()
        event = MagicMock()
        event.button.id = "btn-no"
        screen.on_button_pressed(event)
        screen.dismiss.assert_called_once_with(False)


class TestHelpScreen:
    """Tests for HelpScreen."""

    def test_on_button_pressed_close(self) -> None:
        """Test on_button_pressed closes the help screen."""
        from henchman.cli.textual_screens import HelpScreen

        screen = HelpScreen()
        mock_app = MagicMock()
        # Use object.__setattr__ to bypass property protection
        with patch.object(type(screen), "app", new_callable=lambda: property(lambda _: mock_app)):
            screen.on_button_pressed(MagicMock(button=MagicMock(id="close-help")))
        mock_app.pop_screen.assert_called_once()


class TestProviderScreen:
    """Tests for ProviderScreen."""

    def test_on_button_pressed_cancel(self) -> None:
        """Test on_button_pressed with cancel button."""
        from henchman.cli.textual_screens import ProviderScreen

        screen = ProviderScreen()
        mock_app = MagicMock()
        event = MagicMock()
        event.button.id = "btn-cancel"
        with patch.object(type(screen), "app", new_callable=lambda: property(lambda _: mock_app)):
            screen.on_button_pressed(event)
        mock_app.pop_screen.assert_called_once()

    def test_on_button_pressed_switch_blank(self) -> None:
        """Test on_button_pressed with switch button but blank selection."""
        from textual.widgets import Select

        from henchman.cli.textual_screens import ProviderScreen

        screen = ProviderScreen()
        mock_app = MagicMock()
        sel = MagicMock()
        sel.value = Select.BLANK
        event = MagicMock()
        event.button.id = "btn-switch"
        with patch.object(type(screen), "app", new_callable=lambda: property(lambda _: mock_app)):
            screen.query_one = MagicMock(return_value=sel)
            screen.on_button_pressed(event)
        mock_app.pop_screen.assert_called_once()

    def test_on_button_pressed_switch_valid(self) -> None:
        """Test on_button_pressed with switch button and valid selection."""
        from henchman.cli.textual_screens import ProviderScreen

        screen = ProviderScreen()
        mock_app = MagicMock()
        sel = MagicMock()
        sel.value = "deepseek"
        event = MagicMock()
        event.button.id = "btn-switch"
        with patch.object(type(screen), "app", new_callable=lambda: property(lambda _: mock_app)):
            screen.query_one = MagicMock(return_value=sel)
            screen.on_button_pressed(event)
        mock_app.post_message.assert_called_once()
        mock_app.pop_screen.assert_called_once()

    def test_build_provider_options_empty(self) -> None:
        """Test _build_options with no providers configured."""
        from henchman.cli.textual_screens import ProviderScreen

        settings = MagicMock()
        settings.providers = MagicMock()
        # All provider configs are empty dicts
        for name in ["deepseek", "openai", "anthropic", "ollama"]:
            setattr(settings.providers, name, {})
        options = ProviderScreen._build_options(settings)
        assert options == [("No providers configured", "none")]

    def test_current_provider_name(self) -> None:
        """Test _current_provider_name extracts provider name."""
        from henchman.cli.textual_screens import ProviderScreen

        settings = MagicMock()
        settings.providers.default = "deepseek"
        result = ProviderScreen._current_provider_name(settings)
        assert result == "deepseek"

    def test_current_provider_name_no_settings(self) -> None:
        """Test _current_provider_name returns 'unknown' when no settings."""
        from henchman.cli.textual_screens import ProviderScreen

        result = ProviderScreen._current_provider_name(None)
        assert result == "unknown"


class TestSessionScreen:
    """Tests for SessionScreen."""

    def test_init(self) -> None:
        """Test SessionScreen can be instantiated with sessions."""
        from henchman.cli.textual_screens import SessionScreen

        session = MagicMock()
        session.id = "sess-1"
        session.tag = "my-session"
        session.updated_at = "2025-01-01"
        session.message_count = 5
        screen = SessionScreen(sessions=[session])
        assert len(screen._sessions) == 1

    def test_build_entries(self) -> None:
        """Test _build_entries creates entries from sessions."""
        from henchman.cli.textual_screens import SessionScreen

        session = MagicMock()
        session.id = "sess-1"
        session.tag = "my-session"
        session.updated_at = "2025-01-01"
        session.message_count = 5
        screen = SessionScreen(sessions=[session])
        entries = screen._build_entries()
        assert len(entries) == 1
        assert entries[0][1] == "sess-1"

    def test_action_cancel(self) -> None:
        """Test action_cancel dismisses with None."""
        from henchman.cli.textual_screens import SessionScreen

        screen = SessionScreen(sessions=[])
        screen.dismiss = MagicMock()
        screen.action_cancel()
        screen.dismiss.assert_called_once_with(None)

    def test_on_button_pressed_cancel(self) -> None:
        """Test on_button_pressed cancel button."""
        from henchman.cli.textual_screens import SessionScreen

        screen = SessionScreen(sessions=[])
        screen.dismiss = MagicMock()
        event = MagicMock()
        event.button.id = "btn-cancel"
        screen.on_button_pressed(event)
        screen.dismiss.assert_called_once_with(None)

    def test_on_button_pressed_resume_valid(self) -> None:
        """Test on_button_pressed resume with valid selection."""
        from henchman.cli.textual_screens import SessionScreen

        screen = SessionScreen(sessions=[])
        screen.dismiss = MagicMock()
        sel = MagicMock()
        sel.value = "sess-1"
        screen.query_one = MagicMock(return_value=sel)
        event = MagicMock()
        event.button.id = "btn-resume"
        screen.on_button_pressed(event)
        screen.dismiss.assert_called_once_with("resume:sess-1")

    def test_on_button_pressed_delete_valid(self) -> None:
        """Test on_button_pressed delete with valid selection."""
        from henchman.cli.textual_screens import SessionScreen

        screen = SessionScreen(sessions=[])
        screen.dismiss = MagicMock()
        sel = MagicMock()
        sel.value = "sess-1"
        screen.query_one = MagicMock(return_value=sel)
        event = MagicMock()
        event.button.id = "btn-delete"
        screen.on_button_pressed(event)
        screen.dismiss.assert_called_once_with("delete:sess-1")

    def test_on_button_pressed_no_selection(self) -> None:
        """Test on_button_pressed with no selection."""
        from textual.widgets import Select

        from henchman.cli.textual_screens import SessionScreen

        screen = SessionScreen(sessions=[])
        screen.dismiss = MagicMock()
        sel = MagicMock()
        sel.value = Select.BLANK
        screen.query_one = MagicMock(return_value=sel)
        event = MagicMock()
        event.button.id = "btn-resume"
        screen.on_button_pressed(event)
        screen.dismiss.assert_called_once_with(None)
