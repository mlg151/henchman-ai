"""Comprehensive functional/integration tests for the Textual TUI.

Uses Textual's built-in run_test() pilot framework to render real widgets
in headless mode and simulate user interactions via the Pilot object.

These tests complement the existing mock-based unit tests by exercising
actual widget rendering, composition, and interaction flows.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from textual.widgets import (
    Footer,
    Header,
    OptionList,
    RichLog,
    TabbedContent,
    TextArea,
    Tree,
)

from henchman.cli.textual_app import (
    AgentContentMessage,
    AgentFinishedMessage,
    AgentStatusMessage,
    AgentThoughtMessage,
    ChatPane,
    EventBridge,
    HenchmanTextArea,
    HenchmanTextualApp,
    StatusBar,
    TextualConfig,
    ThinkingPane,
    ToolCallRequestMessage,
    ToolCallResultMessage,
    ToolPane,
)
from henchman.core.events import AgentEvent, EventType

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _richlog_has_content(widget: RichLog) -> bool:
    """Check whether a RichLog widget has received any content.

    Textual v8 defers rendering until widget size is known, so content
    may live in `_deferred_renders` rather than `lines`.
    """
    return bool(widget.lines) or bool(widget._deferred_renders)


def _chatpane_has_content(pane: ChatPane) -> bool:
    """Check whether a ChatPane widget has mounted any message children."""
    return len(list(pane.children)) > 0


def _make_app(
    provider_name: str = "test-mock",
) -> HenchmanTextualApp:
    """Create an app with mocked provider/settings and patched init."""
    provider = MagicMock()
    provider.name = provider_name

    settings = MagicMock()
    settings.ui.theme = "dark"
    settings.ui.keybindings = {}
    settings.ui.mcp_logging = False
    settings.mcp_servers = None

    config = TextualConfig(
        system_prompt="You are a test assistant.",
        auto_approve_tools=True,
    )

    app = HenchmanTextualApp(
        provider=provider,
        config=config,
        settings=settings,
        environment_context="test-env",
    )
    return app


def _patch_core_init():
    """Return a context manager that patches _initialize_core_components.

    This avoids heavy side-effects (agent creation, tool registration, MCP,
    plugin loading, etc.) so the tests focus purely on UI behaviour.
    """
    mock_core_context = MagicMock()
    mock_core_context.orchestrator = MagicMock()
    mock_core_context.tool_manager = MagicMock()
    mock_core_context.session_manager = MagicMock()
    mock_core_context.plugin_manager = MagicMock()
    mock_core_context.mcp_manager = MagicMock()
    mock_core_context.agent = MagicMock()
    mock_core_context.tool_registry = MagicMock()

    def _fake_init(self_app):
        self_app.core_context = mock_core_context
        self_app._ui_renderer = MagicMock()  # renderer is a property reading _ui_renderer
        self_app.output_handler = MagicMock()
        self_app.command_processor = MagicMock()
        self_app.tool_executor = MagicMock()
        # Mirror what the real init does: update status bar with provider name
        try:
            status_bar = self_app.query_one("#status-bar", StatusBar)
            status_bar.status_text = f"Connected to {self_app.provider.name}"
        except Exception:
            pass
        self_app.input_handler = MagicMock()
        self_app.input_handler.history_file = MagicMock()
        self_app.input_handler.history_file.exists.return_value = False

    return patch.object(
        HenchmanTextualApp,
        "_initialize_core_components",
        _fake_init,
    )


# ============================================================================
# 1. App Lifecycle
# ============================================================================

class TestAppLifecycle:
    """Test that the app starts, mounts widgets, and renders correctly."""

    @pytest.mark.asyncio
    async def test_app_mounts_and_renders(self):
        """App should mount and render all expected top-level widgets."""
        app = _make_app()
        with _patch_core_init():
            async with app.run_test() as _pilot:
                # Header
                headers = app.query(Header)
                assert len(headers) == 1

                # Footer
                footers = app.query(Footer)
                assert len(footers) == 1

                # TabbedContent
                tabs = app.query(TabbedContent)
                assert len(tabs) == 1

                # Input TextArea (HenchmanTextArea)
                input_widget = app.query_one("#input", TextArea)
                assert input_widget is not None

                # StatusBar
                status_bar = app.query_one("#status-bar", StatusBar)
                assert status_bar is not None

    @pytest.mark.asyncio
    async def test_initial_focus_on_input(self):
        """The input TextArea should be focused on mount."""
        app = _make_app()
        with _patch_core_init():
            async with app.run_test() as _pilot:
                await _pilot.pause()
                focused = app.focused
                assert focused is not None
                assert focused.id == "input"

    @pytest.mark.asyncio
    async def test_status_bar_shows_provider(self):
        """Status bar should display the provider name after mount."""
        app = _make_app(provider_name="my-test-provider")
        with _patch_core_init():
            async with app.run_test() as _pilot:
                await _pilot.pause()
                status_bar = app.query_one("#status-bar", StatusBar)
                assert "my-test-provider" in status_bar.status_text

    @pytest.mark.asyncio
    async def test_subtitle_shows_provider(self):
        """App sub_title should mention the provider name."""
        app = _make_app(provider_name="deepseek-v3")
        with _patch_core_init():
            async with app.run_test() as _pilot:
                await _pilot.pause()
                assert "deepseek-v3" in app.sub_title


# ============================================================================
# 2. Widget Composition
# ============================================================================

class TestWidgetComposition:
    """Verify all expected widgets exist inside the correct containers."""

    @pytest.mark.asyncio
    async def test_chat_pane_exists_in_tab(self):
        app = _make_app()
        with _patch_core_init():
            async with app.run_test() as _pilot:
                chat = app.query_one("#chat-pane", ChatPane)
                assert chat is not None
                assert isinstance(chat, ChatPane)
                assert chat.border_title == "Chat"

    @pytest.mark.asyncio
    async def test_thinking_pane_exists_in_tab(self):
        app = _make_app()
        with _patch_core_init():
            async with app.run_test() as _pilot:
                thinking = app.query_one("#thinking-pane", ThinkingPane)
                assert thinking is not None
                assert isinstance(thinking, RichLog)
                assert thinking.border_title == "Thinking"

    @pytest.mark.asyncio
    async def test_tool_pane_exists_in_tab(self):
        app = _make_app()
        with _patch_core_init():
            async with app.run_test() as _pilot:
                tool = app.query_one("#tool-pane", ToolPane)
                assert tool is not None
                assert isinstance(tool, RichLog)
                assert tool.border_title == "Tools"

    @pytest.mark.asyncio
    async def test_context_tree_exists_in_tab(self):
        app = _make_app()
        with _patch_core_init():
            async with app.run_test() as _pilot:
                tree = app.query_one("#context-tree", Tree)
                assert tree is not None

    @pytest.mark.asyncio
    async def test_command_palette_hidden_by_default(self):
        app = _make_app()
        with _patch_core_init():
            async with app.run_test() as _pilot:
                palette = app.query_one("#command-palette", OptionList)
                assert palette is not None
                # CSS sets display: none by default
                assert palette.display is False


# ============================================================================
# 3. Text Input
# ============================================================================

class TestTextInput:
    """Test the HenchmanTextArea input widget behaviour."""

    @pytest.mark.asyncio
    async def test_type_text_into_input(self):
        """Typing text should populate the input widget."""
        app = _make_app()
        with _patch_core_init():
            async with app.run_test() as _pilot:
                await _pilot.pause()
                input_widget = app.query_one("#input", TextArea)
                # Focus and type
                input_widget.focus()
                await _pilot.pause()
                # Use the Textual type method to simulate keypresses
                await _pilot.press("h", "e", "l", "l", "o")
                await _pilot.pause()
                assert input_widget.text == "hello"

    @pytest.mark.asyncio
    async def test_enter_submits_message(self):
        """Pressing Enter should trigger action_submit_message."""
        app = _make_app()
        with _patch_core_init():
            async with app.run_test() as _pilot:
                await _pilot.pause()
                input_widget = app.query_one("#input", TextArea)
                input_widget.focus()

                # Pre-populate input
                input_widget.text = "Hello agent"
                await _pilot.pause()

                # Patch process_user_input to capture the call
                with patch.object(app, "process_user_input") as mock_process:
                    await _pilot.press("enter")
                    await _pilot.pause()
                    mock_process.assert_called_once_with("Hello agent")

                # Input should be cleared after submit
                assert input_widget.text == ""

    @pytest.mark.asyncio
    async def test_shift_enter_inserts_newline(self):
        """Shift+Enter should insert a newline, not submit."""
        app = _make_app()
        with _patch_core_init():
            async with app.run_test() as _pilot:
                await _pilot.pause()
                input_widget = app.query_one("#input", TextArea)
                input_widget.focus()
                await _pilot.pause()

                # Type something, then shift+enter
                await _pilot.press("h", "i")
                await _pilot.pause()
                await _pilot.press("shift+enter")
                await _pilot.pause()

                # Should have a newline in the text, not have submitted
                assert "\n" in input_widget.text

    @pytest.mark.asyncio
    async def test_empty_submit_does_nothing(self):
        """Pressing Enter on empty input should not trigger processing."""
        app = _make_app()
        with _patch_core_init():
            async with app.run_test() as _pilot:
                await _pilot.pause()
                input_widget = app.query_one("#input", TextArea)
                input_widget.focus()
                assert input_widget.text == ""

                with patch.object(app, "process_user_input") as mock_process:
                    await _pilot.press("enter")
                    await _pilot.pause()
                    mock_process.assert_not_called()


# ============================================================================
# 4. Message Display
# ============================================================================

class TestMessageDisplay:
    """Test that posting messages updates the correct panes."""

    @pytest.mark.asyncio
    async def test_agent_content_shows_in_chat(self):
        """AgentContentMessage should write to the chat pane."""
        app = _make_app()
        with _patch_core_init():
            async with app.run_test() as _pilot:
                await _pilot.pause()
                app.post_message(AgentContentMessage("Hello from agent", source_agent="TestBot"))
                await _pilot.pause()

                chat = app.query_one("#chat-pane", ChatPane)
                assert _chatpane_has_content(chat)

    @pytest.mark.asyncio
    async def test_agent_thought_shows_in_thinking(self):
        """AgentThoughtMessage should write to the thinking pane."""
        app = _make_app()
        with _patch_core_init():
            async with app.run_test() as _pilot:
                await _pilot.pause()
                app.post_message(AgentThoughtMessage("Thinking hard...", source_agent="Bot"))
                await _pilot.pause()

                thinking = app.query_one("#thinking-pane", ThinkingPane)
                assert _richlog_has_content(thinking)

    @pytest.mark.asyncio
    async def test_tool_call_request_shows_in_tool_pane(self):
        """ToolCallRequestMessage should write to the tool pane."""
        app = _make_app()
        with _patch_core_init():
            async with app.run_test() as _pilot:
                await _pilot.pause()
                mock_tool = MagicMock()
                mock_tool.name = "read_file"
                mock_tool.arguments = '{"path": "/tmp/test.txt"}'
                app.post_message(ToolCallRequestMessage(mock_tool, source_agent="Bot"))
                await _pilot.pause()

                tool_pane = app.query_one("#tool-pane", ToolPane)
                assert _richlog_has_content(tool_pane)

    @pytest.mark.asyncio
    async def test_tool_call_result_shows_in_tool_pane(self):
        """ToolCallResultMessage should write to the tool pane."""
        app = _make_app()
        with _patch_core_init():
            async with app.run_test() as _pilot:
                await _pilot.pause()
                result = {"result": "file contents here", "success": True}
                app.post_message(ToolCallResultMessage(result, source_agent="Bot"))
                await _pilot.pause()

                tool_pane = app.query_one("#tool-pane", ToolPane)
                assert _richlog_has_content(tool_pane)

    @pytest.mark.asyncio
    async def test_agent_status_updates_status_bar(self):
        """AgentStatusMessage should update the status bar text."""
        app = _make_app()
        with _patch_core_init():
            async with app.run_test() as _pilot:
                await _pilot.pause()
                app.post_message(AgentStatusMessage("Working on it...", source_agent="Bot"))
                await _pilot.pause()

                status_bar = app.query_one("#status-bar", StatusBar)
                assert "Working on it..." in status_bar.status_text

    @pytest.mark.asyncio
    async def test_agent_finished_clears_streaming(self):
        """AgentFinishedMessage should clear the streaming buffer for the agent."""
        app = _make_app()
        with _patch_core_init():
            async with app.run_test() as _pilot:
                await _pilot.pause()
                # First send content to populate the chat pane's active stream
                app.post_message(AgentContentMessage("chunk1", source_agent="Bot"))
                await _pilot.pause()
                chat_pane = app.query_one("#chat-pane", ChatPane)
                assert "Bot" in chat_pane._active

                # Then finish
                app.post_message(AgentFinishedMessage(source_agent="Bot"))
                await _pilot.pause()
                assert "Bot" not in chat_pane._active

    @pytest.mark.asyncio
    async def test_add_message_user_role(self):
        """add_message with 'user' role should write to chat pane."""
        app = _make_app()
        with _patch_core_init():
            async with app.run_test() as _pilot:
                await _pilot.pause()
                app.add_message("user", "Hello!")
                await _pilot.pause()

                chat = app.query_one("#chat-pane", ChatPane)
                assert _chatpane_has_content(chat)

    @pytest.mark.asyncio
    async def test_add_message_assistant_role(self):
        """add_message with 'assistant' role should write to chat pane."""
        app = _make_app()
        with _patch_core_init():
            async with app.run_test() as _pilot:
                await _pilot.pause()
                app.add_message("assistant", "I can help!")
                await _pilot.pause()

                chat = app.query_one("#chat-pane", ChatPane)
                assert _chatpane_has_content(chat)


# ============================================================================
# 5. Command Palette
# ============================================================================

class TestCommandPalette:
    """Test slash-command autocomplete palette."""

    @pytest.mark.asyncio
    async def test_typing_slash_shows_palette(self):
        """Typing '/' should show the command palette."""
        app = _make_app()
        with _patch_core_init():
            async with app.run_test() as _pilot:
                await _pilot.pause()
                # Set up commands so palette has options to display
                mock_cmd = MagicMock()
                mock_cmd.name = "help"
                mock_cmd.description = "Show help"
                mock_registry = MagicMock()
                mock_registry.get_commands.return_value = [mock_cmd]
                app.command_processor = MagicMock()
                app.command_processor.command_registry = mock_registry

                # Fire the Changed event manually since direct assignment
                # may not trigger the on_textarea_changed handler
                app._show_command_palette("/")
                await _pilot.pause()

                palette = app.query_one("#command-palette", OptionList)
                assert palette.display is True

    @pytest.mark.asyncio
    async def test_typing_slash_help_filters(self):
        """Typing '/help' should filter the palette to matching commands."""
        app = _make_app()
        with _patch_core_init():
            async with app.run_test() as _pilot:
                await _pilot.pause()
                # Set up a mock command_processor with a 'help' command
                mock_cmd = MagicMock()
                mock_cmd.name = "help"
                mock_cmd.description = "Show help"
                mock_registry = MagicMock()
                mock_registry.get_commands.return_value = [mock_cmd]
                app.command_processor = MagicMock()
                app.command_processor.command_registry = mock_registry
                app._show_command_palette("/help")
                await _pilot.pause()

                palette = app.query_one("#command-palette", OptionList)
                assert palette.option_count > 0

    @pytest.mark.asyncio
    async def test_hide_palette_on_non_slash(self):
        """Command palette should hide when input doesn't start with '/'."""
        app = _make_app()
        with _patch_core_init():
            async with app.run_test() as _pilot:
                await _pilot.pause()
                # Set up commands so palette has options to display
                mock_cmd = MagicMock()
                mock_cmd.name = "help"
                mock_cmd.description = "Show help"
                mock_registry = MagicMock()
                mock_registry.get_commands.return_value = [mock_cmd]
                app.command_processor = MagicMock()
                app.command_processor.command_registry = mock_registry
                # Show first
                app._show_command_palette("/")
                await _pilot.pause()
                palette = app.query_one("#command-palette", OptionList)
                assert palette.display is True

                # Hide
                app._hide_command_palette()
                await _pilot.pause()
                assert palette.display is False


# ============================================================================
# 6. Search Functionality
# ============================================================================

class TestSearchFunctionality:
    """Test search mode activation and state management."""

    @pytest.mark.asyncio
    async def test_ctrl_f_enters_search_mode(self):
        """Pressing Ctrl+F should activate search mode."""
        app = _make_app()
        with _patch_core_init():
            async with app.run_test() as _pilot:
                await _pilot.pause()
                assert app._search_mode is False

                await _pilot.press("ctrl+f")
                await _pilot.pause()
                assert app._search_mode is True

    @pytest.mark.asyncio
    async def test_escape_exits_search_mode(self):
        """Pressing Escape should exit search mode."""
        app = _make_app()
        with _patch_core_init():
            async with app.run_test() as _pilot:
                await _pilot.pause()
                # Enter search
                app.action_search()
                await _pilot.pause()
                assert app._search_mode is True

                # Exit search
                app.action_clear_search()
                await _pilot.pause()
                assert app._search_mode is False

    @pytest.mark.asyncio
    async def test_search_status_bar_updates(self):
        """Status bar should show search-related messages."""
        app = _make_app()
        with _patch_core_init():
            async with app.run_test() as _pilot:
                await _pilot.pause()
                app.action_search()
                await _pilot.pause()

                status_bar = app.query_one("#status-bar", StatusBar)
                assert "Search" in status_bar.status_text or "search" in status_bar.status_text.lower()

    @pytest.mark.asyncio
    async def test_search_next_previous_wrap(self):
        """search_next/search_previous should handle empty matches gracefully."""
        app = _make_app()
        with _patch_core_init():
            async with app.run_test() as _pilot:
                await _pilot.pause()
                app.action_search()
                # Try navigating with no matches — should not crash
                app.action_search_next()
                app.action_search_previous()
                await _pilot.pause()
                # Still in search mode, no crash
                assert app._search_mode is True


# ============================================================================
# 7. Tab Navigation
# ============================================================================

class TestTabNavigation:
    """Test tab switching and pane clearing via the action methods."""

    @pytest.mark.asyncio
    async def test_toggle_thinking_pane(self):
        """Toggling thinking pane should switch tabs."""
        app = _make_app()
        with _patch_core_init():
            async with app.run_test() as _pilot:
                await _pilot.pause()
                tabs = app.query_one(TabbedContent)

                app.action_toggle_thinking_pane()
                await _pilot.pause()
                assert tabs.active == "tab-thinking"

                # Toggle back
                app.action_toggle_thinking_pane()
                await _pilot.pause()
                assert tabs.active == "tab-chat"

    @pytest.mark.asyncio
    async def test_toggle_tool_pane(self):
        """Toggling tool pane should switch tabs."""
        app = _make_app()
        with _patch_core_init():
            async with app.run_test() as _pilot:
                await _pilot.pause()
                tabs = app.query_one(TabbedContent)

                app.action_toggle_tool_pane()
                await _pilot.pause()
                assert tabs.active == "tab-tools"

                app.action_toggle_tool_pane()
                await _pilot.pause()
                assert tabs.active == "tab-chat"

    @pytest.mark.asyncio
    async def test_clear_thinking_pane(self):
        """Clearing thinking pane should clear its content and update status."""
        app = _make_app()
        with _patch_core_init():
            async with app.run_test() as _pilot:
                await _pilot.pause()
                # Write something first
                thinking = app.query_one("#thinking-pane", ThinkingPane)
                thinking.write("some thought")
                await _pilot.pause()
                assert _richlog_has_content(thinking)

                app.action_clear_thinking_pane()
                await _pilot.pause()
                assert not _richlog_has_content(thinking)

                status_bar = app.query_one("#status-bar", StatusBar)
                assert "cleared" in status_bar.status_text.lower()

    @pytest.mark.asyncio
    async def test_clear_tool_pane(self):
        """Clearing tool pane should clear its content and update status."""
        app = _make_app()
        with _patch_core_init():
            async with app.run_test() as _pilot:
                await _pilot.pause()
                tool_pane = app.query_one("#tool-pane", ToolPane)
                tool_pane.write("some tool output")
                await _pilot.pause()
                assert _richlog_has_content(tool_pane)

                app.action_clear_tool_pane()
                await _pilot.pause()
                assert not _richlog_has_content(tool_pane)

                status_bar = app.query_one("#status-bar", StatusBar)
                assert "cleared" in status_bar.status_text.lower()


# ============================================================================
# 8. History Navigation
# ============================================================================

class TestHistoryNavigation:
    """Test command history navigation."""

    @pytest.mark.asyncio
    async def test_history_navigation_up_down(self):
        """Navigating history should populate the input widget."""
        app = _make_app()
        with _patch_core_init():
            async with app.run_test() as _pilot:
                await _pilot.pause()
                # Seed history directly
                app.command_history = ["first command", "second command"]
                app.history_index = len(app.command_history)

                input_widget = app.query_one("#input", TextArea)
                input_widget.focus()
                await _pilot.pause()

                # Navigate up (older)
                app._navigate_history(-1)
                await _pilot.pause()
                assert input_widget.text == "second command"

                app._navigate_history(-1)
                await _pilot.pause()
                assert input_widget.text == "first command"

                # Navigate down (newer), past end clears
                app._navigate_history(1)
                await _pilot.pause()
                assert input_widget.text == "second command"

                app._navigate_history(1)
                await _pilot.pause()
                assert input_widget.text == ""

    @pytest.mark.asyncio
    async def test_submit_adds_to_history(self):
        """Submitting a message should add it to command_history."""
        app = _make_app()
        with _patch_core_init():
            async with app.run_test() as _pilot:
                await _pilot.pause()
                input_widget = app.query_one("#input", TextArea)
                input_widget.focus()
                await _pilot.pause()

                # Pre-populate and submit
                input_widget.text = "test command"
                with patch.object(app, "process_user_input"):
                    app.action_submit_message()
                    await _pilot.pause()

                assert "test command" in app.command_history

    @pytest.mark.asyncio
    async def test_empty_history_navigation_does_nothing(self):
        """Navigating with no history should not crash."""
        app = _make_app()
        with _patch_core_init():
            async with app.run_test() as _pilot:
                await _pilot.pause()
                assert app.command_history == []
                # Should not raise
                app._navigate_history(-1)
                app._navigate_history(1)
                await _pilot.pause()


# ============================================================================
# 9. Modal Screens
# ============================================================================

class TestModalScreens:
    """Test HelpScreen and ProviderScreen modal interactions."""

    @pytest.mark.asyncio
    async def test_help_screen_shows_and_dismisses(self):
        """Pushing HelpScreen should show it; clicking Close should dismiss."""
        app = _make_app()
        with _patch_core_init():
            async with app.run_test() as _pilot:
                await _pilot.pause()
                # Push help screen
                app.action_show_help()
                await _pilot.pause()

                # HelpScreen should be the current screen
                assert len(app.screen_stack) > 1

                # Dismiss via escape
                await _pilot.press("escape")
                await _pilot.pause()
                assert len(app.screen_stack) == 1

    @pytest.mark.asyncio
    async def test_provider_screen_shows_and_dismisses(self):
        """Pushing ProviderScreen should show it; escape should dismiss."""
        app = _make_app()
        with _patch_core_init():
            async with app.run_test() as _pilot:
                await _pilot.pause()
                app.action_switch_provider()
                await _pilot.pause()

                assert len(app.screen_stack) > 1

                await _pilot.press("escape")
                await _pilot.pause()
                assert len(app.screen_stack) == 1


# ============================================================================
# 10. Error Handling
# ============================================================================

class TestErrorHandling:
    """Test that the app handles errors gracefully."""

    @pytest.mark.asyncio
    async def test_add_message_handles_errors(self):
        """add_message should not crash even if internal query fails."""
        app = _make_app()
        with _patch_core_init():
            async with app.run_test() as _pilot:
                await _pilot.pause()
                # Calling add_message with weird roles shouldn't crash
                app.add_message("user", "normal message")
                app.add_message("unknown_role", "something")
                app.add_message("system", "sys info")
                await _pilot.pause()
                # If we got here without exception, the test passes

    @pytest.mark.asyncio
    async def test_update_status_with_tokens_and_cost(self):
        """update_status should format tokens and cost correctly."""
        app = _make_app()
        with _patch_core_init():
            async with app.run_test() as _pilot:
                await _pilot.pause()
                app.update_status("Done", tokens=1500, cost=0.0023)
                await _pilot.pause()

                status_bar = app.query_one("#status-bar", StatusBar)
                assert "Done" in status_bar.status_text
                assert "1500" in status_bar.status_text
                assert "0.0023" in status_bar.status_text

    @pytest.mark.asyncio
    async def test_is_processing_blocks_submit(self):
        """When is_processing is True, action_submit_message should be a no-op."""
        app = _make_app()
        with _patch_core_init():
            async with app.run_test() as _pilot:
                await _pilot.pause()
                input_widget = app.query_one("#input", TextArea)
                input_widget.text = "something"
                app.is_processing = True

                with patch.object(app, "process_user_input") as mock_process:
                    app.action_submit_message()
                    await _pilot.pause()
                    mock_process.assert_not_called()

                # Text should still be there (not cleared)
                assert input_widget.text == "something"


# ============================================================================
# 11. EventBridge (async unit tests)
# ============================================================================

class TestEventBridge:
    """Test EventBridge forwards agent events to the correct messages."""

    @pytest.mark.asyncio
    async def test_forward_content_event(self):
        """CONTENT events should post AgentContentMessage."""
        app = _make_app()
        with _patch_core_init():
            async with app.run_test() as _pilot:
                await _pilot.pause()
                bridge = EventBridge(app)

                # Create async generator of events
                async def event_stream():
                    yield AgentEvent(type=EventType.CONTENT, data="hello from agent")

                await bridge.forward_events(event_stream())
                await _pilot.pause()

                # Content should appear in chat pane
                chat = app.query_one("#chat-pane", ChatPane)
                assert _chatpane_has_content(chat)

    @pytest.mark.asyncio
    async def test_forward_thought_event(self):
        """THOUGHT events should post AgentThoughtMessage."""
        app = _make_app()
        with _patch_core_init():
            async with app.run_test() as _pilot:
                await _pilot.pause()
                bridge = EventBridge(app)

                async def event_stream():
                    yield AgentEvent(type=EventType.THOUGHT, data="reasoning...")

                await bridge.forward_events(event_stream())
                await _pilot.pause()

                thinking = app.query_one("#thinking-pane", ThinkingPane)
                assert _richlog_has_content(thinking)

    @pytest.mark.asyncio
    async def test_forward_finished_event(self):
        """FINISHED events should post AgentFinishedMessage."""
        app = _make_app()
        with _patch_core_init():
            async with app.run_test() as _pilot:
                await _pilot.pause()
                bridge = EventBridge(app)

                async def event_stream():
                    yield AgentEvent(type=EventType.CONTENT, data="hello", source_agent="Bot")
                    yield AgentEvent(type=EventType.FINISHED, data=None, source_agent="Bot")

                await bridge.forward_events(event_stream())
                await _pilot.pause()

                # Bot should have been cleared from chat pane's active stream
                chat_pane = app.query_one("#chat-pane", ChatPane)
                assert "Bot" not in chat_pane._active

    @pytest.mark.asyncio
    async def test_forward_error_event(self):
        """ERROR events should post status and content messages."""
        app = _make_app()
        with _patch_core_init():
            async with app.run_test() as _pilot:
                await _pilot.pause()
                bridge = EventBridge(app)

                async def event_stream():
                    yield AgentEvent(type=EventType.ERROR, data="something went wrong")

                await bridge.forward_events(event_stream())
                await _pilot.pause()

                # Error should show in chat
                chat = app.query_one("#chat-pane", ChatPane)
                assert _chatpane_has_content(chat)

    @pytest.mark.asyncio
    async def test_forward_handles_stream_exception(self):
        """EventBridge should handle exceptions in the event stream gracefully."""
        app = _make_app()
        with _patch_core_init():
            async with app.run_test() as _pilot:
                await _pilot.pause()
                bridge = EventBridge(app)

                async def bad_stream():
                    yield AgentEvent(type=EventType.CONTENT, data="start")
                    raise RuntimeError("stream broke")

                # Should not propagate exception
                await bridge.forward_events(bad_stream())
                await _pilot.pause()

                # Error message should be posted
                chat = app.query_one("#chat-pane", ChatPane)
                assert _chatpane_has_content(chat)


# ---------------------------------------------------------------------------
# End-to-End: Full message flow through real pipeline (only Provider mocked)
# ---------------------------------------------------------------------------

import asyncio  # noqa: E402
from collections.abc import AsyncIterator  # noqa: E402

from henchman.config.schema import Settings  # noqa: E402
from henchman.providers.base import (  # noqa: E402
    FinishReason,
    ModelProvider,
    StreamChunk,
    ToolDeclaration,
)
from henchman.providers.base import (  # noqa: E402
    Message as ProviderMessage,
)


def _get_richlog_text(widget: RichLog) -> str:
    """Extract all plain text from a RichLog widget.

    RichLog stores rendered content as Strip objects (lists of Segments)
    in .lines, and pending renderables in ._deferred_renders.
    Each Segment is (text, style, ...) — we extract just the text parts
    and join them to get a contiguous plain-text representation.
    """
    parts = []
    # Rendered lines: each is a Strip containing Segments
    for strip in widget.lines:
        line_text = ""
        for segment in strip._segments:
            line_text += segment.text
        parts.append(line_text)
    # Deferred renders: convert renderables to string
    for item in widget._deferred_renders:
        parts.append(str(item))
    return "\n".join(parts)


def _get_chatpane_text(pane: ChatPane) -> str:
    """Extract all plain text from a ChatPane widget.

    ChatPane mounts ChatMessage children, each with _prefix and _content.
    """
    from henchman.cli.textual_app import ChatMessage  # avoid circular import at top level

    parts = []
    for child in pane.children:
        if isinstance(child, ChatMessage):
            parts.append(f"{child._prefix} {child._content}")
    return "\n".join(parts)


class _MockStreamingProvider(ModelProvider):
    """A real ModelProvider subclass that streams a canned response.

    Records every call to chat_completion_stream so tests can assert
    that the user's message was actually sent to the provider.
    """

    def __init__(self, response_text: str = "THINKING: Processed.\n\nHello from the mock provider!"):
        self._response_text = response_text
        self.calls: list[list[ProviderMessage]] = []

    @property
    def name(self) -> str:
        return "mock-e2e-provider"

    async def chat_completion_stream(
        self,
        messages: list[ProviderMessage],
        tools: list[ToolDeclaration] | None = None,
        **kwargs,
    ) -> AsyncIterator[StreamChunk]:
        self.calls.append(list(messages))
        # Yield the full content in one chunk with finish_reason=STOP,
        # which is the simplest path through Agent._process_streaming_response.
        yield StreamChunk(
            content=self._response_text,
            finish_reason=FinishReason.STOP,
        )


class TestEndToEndMessageFlow:
    """True end-to-end tests where only the LLM provider is mocked.

    Everything else — InputHandler, Orchestrator, Agent, EventBridge,
    ChatPane — runs for real.
    """

    @pytest.mark.asyncio
    async def test_user_message_flows_to_provider_and_response_appears_in_chat(self):
        """Verify the complete round-trip:

        1. User types a message in the input box
        2. The message appears in the chat pane (as "You: ...")
        3. The message is submitted to the provider (via orchestrator → agent)
        4. The provider's response is streamed back and appears in the chat pane
        """
        provider = _MockStreamingProvider(
            response_text="THINKING: The user said hello.\n\nHello human, I am the mock agent!"
        )
        settings = Settings()  # Defaults — no MCP servers, no plugins
        app = HenchmanTextualApp(
            provider=provider,
            config=TextualConfig(),
            settings=settings,
        )

        async with app.run_test(size=(120, 40)) as _pilot:
            # Wait for on_mount → _initialize_core_components to finish
            await _pilot.pause()
            await _pilot.pause()

            # --- Verify the app initialized properly ---
            status_bar = app.query_one("#status-bar", StatusBar)
            assert "mock-e2e-provider" in status_bar.status_text

            # --- Type a message into the real HenchmanTextArea ---
            input_widget = app.query_one("#input", HenchmanTextArea)
            input_widget.focus()
            await _pilot.pause()

            # Use the input widget's API to insert text (more reliable
            # than _pilot.press for multi-char input in TextArea)
            input_widget.insert("Hello provider!")
            await _pilot.pause()
            assert input_widget.text == "Hello provider!"

            # --- Press Enter to submit ---
            await _pilot.press("enter")

            # The submit handler fires process_user_input in a @work
            # worker thread. We need to wait for it to complete.
            # Poll is_processing with a reasonable timeout.
            for _ in range(100):  # up to ~10 seconds
                await asyncio.sleep(0.1)
                if not app.is_processing:
                    break
            # Give one more pause for UI message delivery
            await _pilot.pause()
            await _pilot.pause()

            # --- Assert: input was cleared after submission ---
            assert input_widget.text == ""

            # --- Assert: the user's message appeared in the chat pane ---
            chat = app.query_one("#chat-pane", ChatPane)
            # Chat pane is a RichLog — check deferred renders + lines
            assert _chatpane_has_content(chat), "Chat pane should have content after submission"

            # Extract plain text from chat pane for content assertions
            all_chat_text = _get_chatpane_text(chat)

            # The user's message should be visible (process_user_input writes "You: <msg>")
            assert "Hello provider!" in all_chat_text, (
                f"User message not found in chat pane. Chat content:\n{all_chat_text}"
            )

            # --- Assert: the provider received the user's message ---
            assert len(provider.calls) >= 1, "Provider should have been called at least once"
            # Find the user message in the last provider call
            last_call_messages = provider.calls[-1]
            user_messages = [m.content for m in last_call_messages if m.role == "user" and m.content]
            assert any("Hello provider!" in msg for msg in user_messages), (
                f"User message not found in provider call. Messages sent:\n{user_messages}"
            )

            # --- Assert: the provider's response appeared in the chat pane ---
            assert "Hello human, I am the mock agent!" in all_chat_text, (
                f"Provider response not found in chat pane. Chat content:\n{all_chat_text}"
            )

    @pytest.mark.asyncio
    async def test_multiple_messages_accumulate_in_chat(self):
        """Send two messages and verify both user messages and both responses appear."""
        call_count = 0

        class _CountingProvider(ModelProvider):
            @property
            def name(self) -> str:
                return "counting-provider"

            async def chat_completion_stream(self, messages, tools=None, **kwargs):
                nonlocal call_count
                call_count += 1
                yield StreamChunk(
                    content=f"THINKING: ok\n\nResponse number {call_count}",
                    finish_reason=FinishReason.STOP,
                )

        provider = _CountingProvider()
        app = HenchmanTextualApp(
            provider=provider,
            config=TextualConfig(),
            settings=Settings(),
        )

        async with app.run_test(size=(120, 40)) as _pilot:
            await _pilot.pause()
            await _pilot.pause()

            input_widget = app.query_one("#input", HenchmanTextArea)
            input_widget.focus()
            await _pilot.pause()

            # --- First message ---
            input_widget.insert("First message")
            await _pilot.press("enter")
            for _ in range(100):
                await asyncio.sleep(0.1)
                if not app.is_processing:
                    break
            await _pilot.pause()
            await _pilot.pause()

            # --- Second message ---
            input_widget.insert("Second message")
            await _pilot.press("enter")
            for _ in range(100):
                await asyncio.sleep(0.1)
                if not app.is_processing:
                    break
            await _pilot.pause()
            await _pilot.pause()

            # Gather all chat pane text
            chat = app.query_one("#chat-pane", ChatPane)
            all_chat_text = _get_chatpane_text(chat)

            # Both user messages should appear
            assert "First message" in all_chat_text, f"Missing first message. Content:\n{all_chat_text}"
            assert "Second message" in all_chat_text, f"Missing second message. Content:\n{all_chat_text}"

            # Both responses should appear
            assert "Response number 1" in all_chat_text, (
                f"Missing response 1. Content:\n{all_chat_text}"
            )
            assert "Response number 2" in all_chat_text, (
                f"Missing response 2. Content:\n{all_chat_text}"
            )
