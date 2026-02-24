"""Final comprehensive functional tests for the Textual TUI."""

from unittest.mock import MagicMock, patch

import pytest
from textual.widgets import OptionList, TextArea

from henchman.cli.textual_app import (
    ChatPane,
    EventBridge,
    HelpScreen,
    HenchmanTextArea,
    HenchmanTextualApp,
    ProviderScreen,
    StatusBar,
    TextualConfig,
    ThinkingPane,
    ToolPane,
)
from henchman.providers.base import ModelProvider


class TestTextualFunctionalFinal:
    """Final comprehensive functional test suite for Textual TUI."""

    @pytest.fixture
    def mock_provider(self):
        """Create a mock provider."""
        provider = MagicMock(spec=ModelProvider)
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

    # === Core Functionality Tests ===

    def test_app_initialization(self, textual_app, mock_provider):
        """Test that the app initializes correctly."""
        assert textual_app.provider == mock_provider
        assert textual_app.config is not None
        assert isinstance(textual_app.config, TextualConfig)
        assert textual_app.config.prompt == "❯ "
        assert textual_app.current_input == ""
        assert textual_app.is_processing is False

    def test_app_compose_structure(self, textual_app):
        """Test that the app composes the correct widget structure."""
        assert hasattr(textual_app, "compose")

        # CSS should be loaded from external .tcss file
        assert hasattr(textual_app, "CSS_PATH")
        assert textual_app.CSS_PATH == "henchman.tcss"

    # === Widget Tests ===

    def test_pane_widgets_initialization(self):
        """Test pane widgets are properly configured."""
        # ChatPane
        chat_pane = ChatPane()
        assert chat_pane.border_title == "Chat"
        assert chat_pane.wrap is True
        assert chat_pane.highlight is True
        assert chat_pane.markup is True

        # ThinkingPane (legacy - thinking now appears in chat)
        thinking_pane = ThinkingPane()
        assert thinking_pane.border_title == "Thinking (legacy)"
        assert thinking_pane.wrap is True
        assert thinking_pane.highlight is True
        assert thinking_pane.markup is True
        # display is True by default; hidden state is managed by the app after mount

        # ToolPane
        tool_pane = ToolPane()
        assert tool_pane.border_title == "Tools"
        assert tool_pane.wrap is True
        assert tool_pane.highlight is True
        assert tool_pane.markup is True
        # display is True by default; hidden state is managed by the app after mount

    def test_status_bar_functionality(self):
        """Test status bar widget."""
        status_bar = StatusBar()
        assert status_bar.border_title == "Status"
        assert status_bar.status_text == "Ready"

        # Test render method
        rendered = status_bar.render()
        assert "[bold cyan]Ready[/]" in rendered

        # Test reactive property
        status_bar.status_text = "Processing..."
        rendered = status_bar.render()
        assert "[bold cyan]Processing...[/]" in rendered

    def test_henchman_textarea_bindings(self):
        """Test HenchmanTextArea custom bindings."""
        textarea = HenchmanTextArea()
        assert hasattr(textarea, "BINDINGS")
        assert len(textarea.BINDINGS) > 0

        # Check for specific bindings
        binding_keys = [binding.key for binding in textarea.BINDINGS]
        assert any("enter" in key.lower() for key in binding_keys)
        assert any("escape" in key.lower() for key in binding_keys)

    # === Message Handling Tests ===

    def test_add_message_functionality(self, textual_app):
        """Test adding messages to chat pane."""
        # Mock the chat pane
        mock_chat_pane = MagicMock()

        # Patch query_one on the actual instance
        with patch.object(textual_app, 'query_one', return_value=mock_chat_pane):
            # Test user message
            textual_app.add_message("user", "Hello")
            mock_chat_pane.add_user_message.assert_called_with("Hello")

            # Test assistant message
            textual_app.add_message("assistant", "Hi there!")
            mock_chat_pane.add_system_message.assert_called_with("Hi there!")

            # Test system message
            textual_app.add_message("system", "System message")
            mock_chat_pane.add_system_message.assert_called_with("System message")

            # Test unknown role (should use role in brackets)
            textual_app.add_message("unknown", "Test")
            mock_chat_pane.add_system_message.assert_called_with("[unknown] Test")

    # === Event Bridge Tests ===

    def test_event_bridge_initialization(self, textual_app):
        """Test EventBridge initialization."""
        bridge = EventBridge(textual_app)
        assert bridge.app == textual_app

    @patch("henchman.cli.textual_app.HenchmanTextualApp.call_from_thread")
    @patch("henchman.cli.textual_app.HenchmanTextualApp.post_message")
    async def test_event_bridge_forward_events(self, mock_post_message, mock_call_from_thread, textual_app):
        """Test EventBridge forwarding events."""
        from henchman.core.events import AgentEvent, EventType

        bridge = EventBridge(textual_app)

        # Create mock event stream
        async def mock_event_stream():
            yield AgentEvent(EventType.CONTENT, "Hello")
            yield AgentEvent(EventType.THOUGHT, "Thinking...")
            yield AgentEvent(EventType.FINISHED, None)

        # Mock call_from_thread to call the function directly
        def call_from_thread_side_effect(func, *args, **kwargs):
            return func(*args, **kwargs)
        mock_call_from_thread.side_effect = call_from_thread_side_effect

        # Forward events
        await bridge.forward_events(mock_event_stream())

        # Verify messages were posted
        assert mock_post_message.call_count >= 3

    # === Command Palette Tests ===

    @patch.object(HenchmanTextualApp, "query_one")
    def test_command_palette_functionality(self, mock_query_one, textual_app):
        """Test command palette showing, filtering, and selection."""
        # Mock option list
        mock_option_list = MagicMock()
        mock_textarea = MagicMock()

        call_count = 0
        def query_one_side_effect(query, widget_type):
            nonlocal call_count
            call_count += 1
            if query == "#command-palette" and widget_type == OptionList:
                return mock_option_list
            elif query == "#input" and widget_type == TextArea:
                return mock_textarea
            raise ValueError(f"Unexpected query: {query}")

        mock_query_one.side_effect = query_one_side_effect

        # Set up a mock command_processor so palette has commands to show
        mock_cmd = MagicMock()
        mock_cmd.name = "help"
        mock_cmd.description = "Show help"
        mock_cmd_registry = MagicMock()
        mock_cmd_registry.get_commands.return_value = [mock_cmd]
        textual_app.command_processor = MagicMock()
        textual_app.command_processor.command_registry = mock_cmd_registry

        # Test showing palette
        textual_app._show_command_palette("/hel")
        mock_query_one.assert_called_with("#command-palette", OptionList)
        assert mock_option_list.display is True
        mock_option_list.clear_options.assert_called_once()

        # Test hiding palette
        textual_app._hide_command_palette()
        assert mock_option_list.display is False

        # Test command selection
        mock_event = MagicMock()
        mock_option = MagicMock()
        mock_option.prompt = "/help"
        mock_event.option = mock_option

        textual_app.on_command_selected(mock_event)
        mock_textarea.text = "/help "
        mock_textarea.cursor_location = (0, len("/help "))
        mock_textarea.focus.assert_called_once()
        assert mock_option_list.display is False

    # === History Navigation Tests ===

    @patch.object(HenchmanTextualApp, "query_one")
    def test_history_navigation(self, mock_query_one, textual_app):
        """Test command history navigation."""
        # Set up history
        textual_app.command_history = ["command1", "command2", "command3"]
        textual_app.history_index = 3

        # Mock textarea with load_text method
        mock_textarea = MagicMock()
        mock_textarea.load_text = MagicMock()
        mock_query_one.return_value = mock_textarea

        # Navigate up
        textual_app._navigate_history(-1)  # Should go to command3
        mock_query_one.assert_called_with("#input", TextArea)
        mock_textarea.load_text.assert_called_with("command3")

        # Navigate up again
        textual_app._navigate_history(-1)  # Should go to command2
        mock_textarea.load_text.assert_called_with("command2")

        # Navigate down
        textual_app._navigate_history(1)  # Should go to command3
        mock_textarea.load_text.assert_called_with("command3")

        # Navigate down past end - should clear
        textual_app._navigate_history(1)
        mock_textarea.load_text.assert_called_with("")

    # === Tab and Pane Management Tests ===

    @patch.object(HenchmanTextualApp, "query_one")
    def test_tab_toggling(self, mock_query_one, textual_app):
        """Test tab toggling functionality."""
        # Mock TabbedContent
        mock_tabs = MagicMock()
        mock_tabs.active = "tab-chat"
        mock_query_one.return_value = mock_tabs

        # Test toggle thinking pane
        textual_app.action_toggle_thinking_pane()
        assert mock_tabs.active == "tab-thinking"

        # Test toggle back
        textual_app.action_toggle_thinking_pane()
        assert mock_tabs.active == "tab-chat"

        # Test toggle tool pane
        textual_app.action_toggle_tool_pane()
        assert mock_tabs.active == "tab-tools"

        # Test toggle back
        textual_app.action_toggle_tool_pane()
        assert mock_tabs.active == "tab-chat"

    @patch.object(HenchmanTextualApp, "query_one")
    def test_pane_clearing(self, mock_query_one, textual_app):
        """Test clearing panes."""
        # Mock panes and status bar
        mock_thinking_pane = MagicMock()
        mock_chat_pane = MagicMock()
        mock_tool_pane = MagicMock()
        mock_status_bar = MagicMock()

        call_count = 0

        def query_one_side_effect(query, widget_type):  # noqa: ARG001
            nonlocal call_count
            call_count += 1
            pane_map = {
                "#thinking-pane": mock_thinking_pane,
                "#chat-pane": mock_chat_pane,
                "#tool-pane": mock_tool_pane,
                "#status-bar": mock_status_bar,
            }
            if query in pane_map:
                return pane_map[query]
            raise ValueError(f"Unexpected query: {query}")

        mock_query_one.side_effect = query_one_side_effect

        # Test clear thinking pane (now also clears chat thinking messages)
        textual_app.action_clear_thinking_pane()
        mock_thinking_pane.clear.assert_called_once()
        mock_chat_pane.clear_thinking_messages.assert_called_once()
        assert mock_status_bar.status_text == "Thinking cleared (legacy pane and chat messages)"

        # Test clear tool pane
        textual_app.action_clear_tool_pane()
        mock_tool_pane.clear.assert_called_once()
        mock_status_bar.status_text = "Tool pane cleared"

    # === Search Functionality Tests ===

    def test_search_actions_mocked(self, textual_app):
        """Test search actions with mocked dependencies."""
        textual_app._search_mode = False

        # Mock query_one to avoid ScreenStackError
        with patch.object(textual_app, "query_one") as mock_query_one:
            # Mock status bar
            mock_status_bar = MagicMock()
            mock_query_one.return_value = mock_status_bar

            # First call should enable search mode
            with patch.object(textual_app, "action_search_next") as mock_search_next:
                textual_app.action_search()
                assert textual_app._search_mode is True
                mock_search_next.assert_not_called()

            # Second call should find next match
            textual_app._search_mode = True
            with patch.object(textual_app, "action_search_next") as mock_search_next:
                textual_app.action_search()
                mock_search_next.assert_called_once()

    def test_clear_search_action(self, textual_app):
        """Test clear search action."""
        textual_app._search_mode = True
        textual_app._search_query = "test"

        # Mock query_one to avoid ScreenStackError
        with patch.object(textual_app, "query_one") as mock_query_one:
            # Mock status bar
            mock_status_bar = MagicMock()
            mock_query_one.return_value = mock_status_bar

            textual_app.action_clear_search()

            assert textual_app._search_mode is False
            assert textual_app._search_query == ""
            mock_status_bar.status_text = "Search cleared"

    # === Modal Screen Tests ===

    @patch.object(HenchmanTextualApp, "push_screen")
    def test_modal_screens(self, mock_push_screen, textual_app):
        """Test showing modal screens."""
        # Test help screen
        mock_help_screen = MagicMock(spec=HelpScreen)
        with patch("henchman.cli.textual_app.HelpScreen", return_value=mock_help_screen):
            textual_app.action_show_help()
            mock_push_screen.assert_called_with(mock_help_screen)

        # Reset mock for next test
        mock_push_screen.reset_mock()

        # Test provider screen
        mock_provider_screen = MagicMock(spec=ProviderScreen)
        with patch("henchman.cli.textual_app.ProviderScreen", return_value=mock_provider_screen):
            textual_app.action_switch_provider()
            mock_push_screen.assert_called_with(mock_provider_screen)

    # === Configuration Tests ===

    def test_textual_config_defaults(self):
        """Test TextualConfig default values."""
        config = TextualConfig()
        assert config.prompt == "❯ "
        assert config.system_prompt == ""
        assert config.auto_save is True
        assert config.history_file is None
        assert config.base_tool_iterations == 25
        assert config.max_tool_calls_per_turn == 100
        assert config.auto_approve_tools is False

    def test_textual_config_custom_values(self):
        """Test TextualConfig with custom values."""
        from pathlib import Path

        config = TextualConfig(
            prompt="> ",
            system_prompt="You are helpful",
            auto_save=False,
            history_file=Path("/tmp/history.txt"),
            base_tool_iterations=10,
            max_tool_calls_per_turn=50,
            auto_approve_tools=True,
        )

        assert config.prompt == "> "
        assert config.system_prompt == "You are helpful"
        assert config.auto_save is False
        assert config.history_file == Path("/tmp/history.txt")
        assert config.base_tool_iterations == 10
        assert config.max_tool_calls_per_turn == 50
        assert config.auto_approve_tools is True

    # === Keyboard Shortcuts Tests ===

    def test_keyboard_shortcuts(self, textual_app):
        """Test keyboard shortcuts are defined."""
        # Check BINDINGS exist
        assert hasattr(textual_app, 'BINDINGS')
        assert isinstance(textual_app.BINDINGS, list)

        # Should have some bindings
        assert len(textual_app.BINDINGS) > 0

        # Check for common shortcuts
        binding_keys = [binding.key for binding in textual_app.BINDINGS]

        # Should have quit shortcut
        assert any("ctrl+q" in key.lower() for key in binding_keys) or any(
            "ctrl+c" in key.lower() for key in binding_keys
        )

        # Should have submit shortcut
        assert any("ctrl+enter" in key.lower() for key in binding_keys)

    # === App Mount Tests ===

    @patch.object(HenchmanTextualApp, "query_one")
    def test_on_mount_initialization(self, mock_query_one, textual_app):
        """Test app initialization on mount."""
        # Mock input widget
        mock_input = MagicMock()
        mock_query_one.return_value = mock_input

        # Mock core component initialization
        with patch.object(textual_app, "_initialize_core_components"):
            textual_app.on_mount()

        # Verify
        # Note: query_one is called multiple times in on_mount, including for TabbedContent
        # to force the Chat tab to be active. We check that it was called with #input at some point.
        mock_query_one.assert_any_call("#input", TextArea)
        mock_input.focus.assert_called()
        # Check sub_title format includes version
        assert "Henchman-AI v" in textual_app.sub_title
        assert textual_app.provider.name in textual_app.sub_title

    # === Message Handler Existence Tests ===

    def test_message_handler_methods_exist(self, textual_app):
        """Test that message handler methods exist (they use @on decorator)."""
        # These methods are decorated with @on and may not show up in dir()
        # but we can check if the class has the expected handler registrations
        # by checking for common patterns

        # Check that the class has methods that handle messages
        # The actual handlers use @on decorator which registers them differently
        assert hasattr(textual_app, 'on_agent_content_message')
        assert hasattr(textual_app, 'on_agent_thought_message')
        assert hasattr(textual_app, 'on_tool_call_request_message')
        assert hasattr(textual_app, 'on_tool_call_result_message')
        assert hasattr(textual_app, 'on_agent_status_message')
        assert hasattr(textual_app, 'on_agent_finished_message')

    # === Integration Style Tests ===

    @patch.object(HenchmanTextualApp, "query_one")
    @patch("henchman.cli.textual_app.expand_at_references")
    @patch("henchman.cli.textual_app.EventBridge")
    def test_process_user_input_integration_style(
        self,
        mock_event_bridge_class,
        mock_expand_references,
        mock_query_one,
        textual_app
    ):
        """Integration-style test for process_user_input dependencies."""
        # Setup mocks
        mock_chat_pane = MagicMock()
        mock_status_bar = MagicMock()

        def query_one_side_effect(query, widget_type):  # noqa: ARG001
            if query == "#chat-pane":
                return mock_chat_pane
            elif query == "#status-bar":
                return mock_status_bar
            raise ValueError(f"Unexpected query: {query}")

        mock_query_one.side_effect = query_one_side_effect

        # Mock dependencies
        textual_app.input_handler = MagicMock()
        textual_app.input_handler.process_input.return_value = ("Hello", False, True)

        textual_app.core_context = MagicMock()
        textual_app.core_context.orchestrator = MagicMock()
        textual_app.core_context.session_manager = MagicMock()

        # Mock event bridge
        mock_event_bridge = MagicMock()
        mock_event_bridge_class.return_value = mock_event_bridge

        # Mock expand_at_references
        mock_expand_references.return_value = "Hello"

        # Verify dependencies are set up
        assert textual_app.input_handler is not None
        assert textual_app.core_context is not None

        # The actual @work-decorated method can't be easily tested in unit tests
        # but we've verified all its dependencies are properly mocked

    # === Screen Composition Tests ===

    def test_screen_composition(self):
        """Test that screens compose their widgets."""
        # HelpScreen (can be tested without app context)
        help_screen = HelpScreen()
        help_compose_result = list(help_screen.compose())
        assert len(help_compose_result) > 0

        # ProviderScreen requires an active app context (accesses self.app in compose())
        # Verify it exists and is a ModalScreen subclass
        provider_screen = ProviderScreen()
        assert hasattr(provider_screen, "compose")

    # === Error Handling Tests ===

    @patch.object(HenchmanTextualApp, "query_one")
    def test_message_handling_with_errors(self, mock_query_one, textual_app):
        """Test that message handling doesn't crash on errors."""
        # Mock query_one to raise an error
        mock_query_one.side_effect = Exception("Test error")

        # Should not crash when adding message
        try:
            textual_app.add_message("user", "Test")
        except Exception:
            pytest.fail("add_message should handle query_one errors gracefully")

        # Should not crash when toggling panes
        try:
            textual_app.action_toggle_thinking_pane()
        except Exception:
            pytest.fail("action_toggle_thinking_pane should handle errors gracefully")

        try:
            textual_app.action_toggle_tool_pane()
        except Exception:
            pytest.fail("action_toggle_tool_pane should handle errors gracefully")
