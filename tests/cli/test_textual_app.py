"""Tests for the Textual TUI."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from henchman.cli.textual_app import (
    ChatPane,
    HenchmanTextualApp,
    StatusBar,
    TextualConfig,
    ThinkingPane,
    ToolPane,
)


class TestHenchmanTextualApp:
    """Test suite for HenchmanTextualApp."""

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

    def test_app_initialization(self, textual_app, mock_provider):
        """Test that the app initializes correctly."""
        assert textual_app.provider == mock_provider
        assert textual_app.config is not None
        assert isinstance(textual_app.config, TextualConfig)
        assert textual_app.config.prompt == "❯ "
        assert textual_app.current_input == ""
        assert textual_app.is_processing is False

    def test_app_compose(self, textual_app):
        """Test that the app composes the correct widgets."""
        assert hasattr(textual_app, "compose")

        # CSS is now loaded from external .tcss file
        assert textual_app.CSS_PATH == "henchman.tcss"

    def test_app_css(self, textual_app):
        """Test that the CSS is loaded from external TCSS file."""
        from pathlib import Path

        tcss_path = Path(__file__).resolve().parents[2] / "src" / "henchman" / "cli" / "henchman.tcss"
        assert tcss_path.exists(), "henchman.tcss should exist"
        css_content = tcss_path.read_text()
        assert "#chat-pane" in css_content
        assert "#thinking-pane" in css_content
        assert "#tool-pane" in css_content

    def test_pane_widgets(self):
        """Test that pane widgets are properly configured."""
        # Test ChatPane
        chat_pane = ChatPane()
        assert chat_pane.border_title == "Chat"
        assert chat_pane.wrap is True
        assert chat_pane.highlight is True
        assert chat_pane.markup is True

        # Test ThinkingPane (legacy - thinking now appears in chat)
        thinking_pane = ThinkingPane()
        assert thinking_pane.border_title == "Thinking (legacy)"
        assert thinking_pane.wrap is True
        assert thinking_pane.highlight is True
        assert thinking_pane.markup is True
        # display is True by default; hidden state is managed by the app after mount

        # Test ToolPane
        tool_pane = ToolPane()
        assert tool_pane.border_title == "Tools"
        assert tool_pane.wrap is True
        assert tool_pane.highlight is True
        assert tool_pane.markup is True
        # display is True by default; hidden state is managed by the app after mount

    def test_status_bar(self):
        """Test the status bar widget."""
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

    @patch("henchman.cli.textual_app.create_core_context")
    @patch("rich.console.Console")
    @patch("henchman.cli.console.ThemeManager")
    @patch("henchman.cli.console.OutputRenderer")
    @patch("henchman.cli.textual_app.UIRenderer")
    @patch("henchman.cli.textual_app.OutputHandler")
    @patch("henchman.cli.textual_app.CommandProcessor")
    @patch("henchman.cli.textual_app.ToolExecutor")
    @patch("henchman.cli.textual_app.InputHandler")
    @patch("henchman.cli.textual_app.initialize_mcp")
    @patch.object(HenchmanTextualApp, "query_one")
    def test_initialize_core_components(
        self,
        mock_query_one,
        mock_initialize_mcp,
        mock_input_handler,
        mock_tool_executor,
        mock_command_processor,
        mock_output_handler,
        mock_ui_renderer,
        mock_output_renderer,
        mock_theme_manager,
        mock_console,
        mock_create_core_context,
        textual_app,
        mock_provider,
        mock_settings,
    ):
        """Test core component initialization."""
        # Mock core context
        mock_core_context = MagicMock()
        mock_core_context.orchestrator = MagicMock()
        mock_core_context.tool_manager = MagicMock()
        mock_core_context.session_manager = MagicMock()
        mock_core_context.plugin_manager = MagicMock()
        mock_core_context.mcp_manager = MagicMock()
        mock_core_context.agent = MagicMock()
        mock_create_core_context.return_value = mock_core_context

        # Mock theme manager
        mock_theme = MagicMock()
        mock_theme_manager_instance = MagicMock()
        mock_theme_manager_instance.list_themes.return_value = ["dark", "light"]
        mock_theme_manager_instance.get_theme.return_value = mock_theme
        mock_theme_manager.return_value = mock_theme_manager_instance

        # Mock console
        mock_console_instance = MagicMock()
        mock_console.return_value = mock_console_instance

        # Mock renderers
        mock_output_renderer_instance = MagicMock()
        mock_output_renderer.return_value = mock_output_renderer_instance
        mock_ui_renderer_instance = MagicMock()
        mock_ui_renderer.return_value = mock_ui_renderer_instance

        # Mock handlers
        mock_output_handler_instance = MagicMock()
        mock_output_handler.return_value = mock_output_handler_instance
        mock_command_processor_instance = MagicMock()
        mock_command_processor.return_value = mock_command_processor_instance
        mock_tool_executor_instance = MagicMock()
        mock_tool_executor.return_value = mock_tool_executor_instance
        mock_input_handler_instance = MagicMock()
        mock_input_handler.return_value = mock_input_handler_instance

        # Mock status bar query
        mock_status_bar = MagicMock()
        mock_query_one.return_value = mock_status_bar

        # Call the method
        textual_app._initialize_core_components()

        # Verify core context was created
        mock_create_core_context.assert_called_once_with(
            provider=mock_provider,
            system_prompt=textual_app.config.system_prompt,
            environment_context=textual_app.environment_context,
            settings=mock_settings,
            auto_approve_tools=textual_app.config.auto_approve_tools,
        )

        # Verify plugin manager UI instance was set
        assert mock_core_context.plugin_manager.ui_instance == textual_app

        # Verify MCP was initialized
        mock_initialize_mcp.assert_called_once_with(mock_core_context)

        # Verify core context is set
        assert textual_app.core_context == mock_core_context
        assert textual_app.renderer == mock_ui_renderer_instance
        assert textual_app.output_handler == mock_output_handler_instance
        assert textual_app.command_processor == mock_command_processor_instance
        assert textual_app.tool_executor == mock_tool_executor_instance
        assert textual_app.input_handler == mock_input_handler_instance

        # Verify status bar was updated
        mock_query_one.assert_called_once_with("#status-bar", StatusBar)
        mock_status_bar.status_text = f"Connected to {mock_provider.name}"

    def test_add_message(self, textual_app):
        """Test adding messages to chat pane."""
        # Mock the chat pane
        mock_chat_pane = MagicMock()
        with patch.object(textual_app, "query_one", return_value=mock_chat_pane):
            # Test user message
            textual_app.add_message("user", "Hello")
            mock_chat_pane.add_user_message.assert_called_with("Hello")

            # Test assistant message
            textual_app.add_message("assistant", "Hi there!")
            mock_chat_pane.add_system_message.assert_called_with("Hi there!")

            # Test unknown role (should use role in brackets)
            textual_app.add_message("unknown", "Test")
            mock_chat_pane.add_system_message.assert_called_with("[unknown] Test")

    def test_keyboard_shortcuts_defined(self, textual_app):
        """Test that keyboard shortcuts are defined in the app."""
        # Check that BINDINGS are defined
        assert hasattr(textual_app, "BINDINGS")
        assert isinstance(textual_app.BINDINGS, list)

        # Check for expected shortcuts
        # Textual BINDINGS are Binding objects with .key attribute
        binding_keys = [binding.key for binding in textual_app.BINDINGS]
        # We should have at least some bindings defined
        assert len(binding_keys) > 0
        # Check for common shortcuts
        assert any("ctrl+q" in key.lower() for key in binding_keys) or any(
            "ctrl+c" in key.lower() for key in binding_keys
        )

    @patch.object(HenchmanTextualApp, "query_one")
    def test_toggle_thinking_pane(self, mock_query_one, textual_app):
        """Test toggling the thinking pane."""
        # Mock TabbedContent
        mock_tabs = MagicMock()
        mock_tabs.active = "tab-chat"
        # query_one returns tabs
        mock_query_one.return_value = mock_tabs

        # Toggle
        textual_app.action_toggle_thinking_pane()

        # Verify it switched to thinking tab
        assert mock_tabs.active == "tab-thinking"

        # Toggle back
        textual_app.action_toggle_thinking_pane()
        assert mock_tabs.active == "tab-chat"

    @patch.object(HenchmanTextualApp, "query_one")
    def test_toggle_tool_pane(self, mock_query_one, textual_app):
        """Test toggling the tool pane."""
        # Mock TabbedContent
        mock_tabs = MagicMock()
        mock_tabs.active = "tab-chat"
        mock_query_one.return_value = mock_tabs

        # Toggle
        textual_app.action_toggle_tool_pane()

        # Verify it switched to tool tab
        assert mock_tabs.active == "tab-tools"

        # Toggle back
        textual_app.action_toggle_tool_pane()
        assert mock_tabs.active == "tab-chat"

    @patch.object(HenchmanTextualApp, "query_one")
    def test_clear_thinking_pane(self, mock_query_one, textual_app):
        """Test clearing the thinking pane."""
        # Mock the thinking pane, chat pane, and status bar
        mock_thinking_pane = MagicMock()
        mock_chat_pane = MagicMock()
        mock_status_bar = MagicMock()

        # Set up mock to return different values based on query
        def query_one_side_effect(query, widget_type):
            if query == "#thinking-pane" and widget_type == ThinkingPane:
                return mock_thinking_pane
            elif query == "#chat-pane" and widget_type == ChatPane:
                return mock_chat_pane
            elif query == "#status-bar" and widget_type == StatusBar:
                return mock_status_bar
            else:
                raise ValueError(f"Unexpected query: {query}, {widget_type}")

        mock_query_one.side_effect = query_one_side_effect

        # Call the action method
        textual_app.action_clear_thinking_pane()

        # Verify pane was cleared, chat thinking messages cleared, and status bar updated
        mock_thinking_pane.clear.assert_called_once()
        mock_chat_pane.clear_thinking_messages.assert_called_once()
        assert mock_status_bar.status_text == "Thinking cleared (legacy pane and chat messages)"

    @patch.object(HenchmanTextualApp, "query_one")
    def test_clear_tool_pane(self, mock_query_one, textual_app):
        """Test clearing the tool pane."""
        # Mock the tool pane and status bar
        mock_tool_pane = MagicMock()
        mock_status_bar = MagicMock()

        # Set up mock to return different values based on query
        def query_one_side_effect(query, widget_type):
            if query == "#tool-pane" and widget_type == ToolPane:
                return mock_tool_pane
            elif query == "#status-bar" and widget_type == StatusBar:
                return mock_status_bar
            else:
                raise ValueError(f"Unexpected query: {query}, {widget_type}")

        mock_query_one.side_effect = query_one_side_effect

        # Call the action method
        textual_app.action_clear_tool_pane()

        # Verify pane was cleared and status bar updated
        mock_tool_pane.clear.assert_called_once()
        mock_status_bar.status_text = "Tool pane cleared"

    @patch("henchman.providers.get_default_registry")
    @patch.object(HenchmanTextualApp, "query_one")
    @patch.object(HenchmanTextualApp, "_initialize_core_components")
    def test_switch_provider_failure_leaves_inconsistent_state(
        self,
        mock_initialize_core_components,
        mock_query_one,
        mock_get_default_registry,
        textual_app,
        mock_provider,
    ):
        """Test Bug 5: Provider switch failure leaves app in inconsistent state.
        
        When _initialize_core_components() fails AFTER provider assignment,
        the provider is changed but core components aren't reinitialized.
        """
        # Setup mocks
        mock_registry = MagicMock()
        mock_get_default_registry.return_value = mock_registry

        # Create a new mock provider
        new_mock_provider = MagicMock()
        new_mock_provider.name = "new-provider"
        mock_registry.create.return_value = new_mock_provider

        # Simulate failure: _initialize_core_components() raises exception
        mock_initialize_core_components.side_effect = RuntimeError("Component init failed")

        # Mock chat pane for error message
        mock_chat_pane = MagicMock()
        mock_query_one.return_value = mock_chat_pane

        # Store original provider
        original_provider = textual_app.provider

        # Attempt to switch provider - should partially fail
        textual_app._switch_provider("new-provider")

        # BUG: Provider IS changed even though initialization fails
        # This test will FAIL because the bug exists
        assert textual_app.provider == original_provider, \
            "Provider should be rolled back when component initialization fails"

        # _initialize_core_components WAS called (and failed)
        mock_initialize_core_components.assert_called_once()

        # Error message should be shown
        mock_chat_pane.add_error_message.assert_called_once_with(
            "Failed to switch provider: Component init failed"
        )

    def test_on_tree_node_selected_implementation_fixed(
        self,
        textual_app,
    ):
        """Test Bug 4 fix: Verify implementation uses async file reading.
        
        Check that the method is now async and uses asyncio.to_thread.
        """
        # Check that the method is decorated with @work (has __wrapped__)
        method = textual_app.on_tree_node_selected
        assert hasattr(method, '__wrapped__'), "Method should be decorated with @work"

        # Get the wrapped function
        wrapped = method.__wrapped__

        # Check the source code contains asyncio.to_thread
        import inspect
        source = inspect.getsource(wrapped)
        assert 'asyncio.to_thread' in source, "Method should use asyncio.to_thread for async file reading"
        assert 'await' in source, "Method should be async"

        # Check exception handler handles query_one failure
        assert 'except Exception:' in source, "Method should have exception handler"
        # Check for nested try-except in exception handler
        assert 'chat.add_error_message' in source, "Should show error message"
        assert 'logging.error' in source, "Should log error if UI fails"

    @patch.object(HenchmanTextualApp, "query_one")
    @patch("asyncio.to_thread")
    @pytest.mark.asyncio
    async def test_on_tree_node_selected_async_behavior(
        self,
        mock_to_thread,
        mock_query_one,
        textual_app,
    ):
        """Test Bug 4 fix: Async file reading behavior.
        
        Simulate the async behavior by calling the method directly
        in an async context.
        """
        # Create a mock event with a file path
        mock_event = MagicMock()
        mock_node = MagicMock()

        # Create a mock path
        mock_path = MagicMock(spec=Path)
        mock_path.is_file.return_value = True
        mock_path.name = "test_file.txt"
        mock_path.read_text = MagicMock()
        mock_stat = MagicMock()
        mock_stat.st_size = 20000
        mock_path.stat = MagicMock()

        mock_node.data = mock_path
        mock_event.node = mock_node

        # Mock chat pane
        mock_chat_pane = MagicMock()
        mock_query_one.return_value = mock_chat_pane

        # Test async file reading: first call is stat, second is read_text
        test_content = "Test file content" * 1000  # Larger than 5000 char limit
        mock_to_thread.side_effect = [mock_stat, test_content]

        # Call the async method directly (bypassing @work decorator)
        method = textual_app.on_tree_node_selected.__wrapped__
        await method(textual_app, mock_event)

        # Verify both stat and read are done asynchronously
        assert mock_to_thread.call_count == 2

        # Check that content was truncated (5000 char limit)
        call_args = mock_chat_pane.add_system_message.call_args[0][0]
        assert "… (truncated)" in call_args, "Large file should be truncated"

    @patch("henchman.cli.app._get_provider")
    @patch("henchman.config.load_settings")
    @patch("henchman.cli.textual_config.TextualConfig")
    @patch("henchman.config.environment.format_environment_block")
    @patch("henchman.config.environment.gather_environment")
    def test_resolve_provider_from_env_handles_all_exceptions(
        self,
        mock_gather_environment,
        mock_format_environment_block,
        mock_textual_config,
        mock_load_settings,
        mock_get_provider,
        textual_app,
    ):
        """Test Bug 1 fix: All initialization steps should handle exceptions.
        
        Previously only _get_provider() was wrapped in try-except. Now
        load_settings(), TextualConfig(), format_environment_block(), and
        gather_environment() should all handle exceptions gracefully.
        """
        # Setup mocks
        mock_provider = MagicMock()
        mock_provider.name = "test-provider"
        mock_get_provider.return_value = mock_provider

        # Test 1: load_settings() raises exception - should be handled
        mock_load_settings.side_effect = ValueError("Corrupted settings file")

        # This should NOT crash - should handle exception gracefully
        textual_app._resolve_provider_from_env()

        # Verify settings were set to defaults
        assert textual_app.settings is not None
        assert hasattr(textual_app.settings, 'ui')  # Default Settings object

        # Test 2: TextualConfig() raises exception - should be handled
        mock_load_settings.reset_mock(side_effect=True)
        mock_load_settings.return_value = MagicMock()
        mock_textual_config.side_effect = TypeError("Invalid config")

        # This should NOT crash
        textual_app._resolve_provider_from_env()

        # Verify config was set to defaults
        assert textual_app.config is not None
        assert hasattr(textual_app.config, 'prompt')  # Default TextualConfig object

        # Test 3: format_environment_block() raises exception - should be handled
        mock_textual_config.reset_mock(side_effect=True)
        mock_textual_config.return_value = MagicMock()
        mock_format_environment_block.side_effect = RuntimeError("Format error")
        mock_gather_environment.return_value = {}

        # This should NOT crash
        textual_app._resolve_provider_from_env()

        # Verify environment context was set to fallback
        assert textual_app.environment_context == "Environment context unavailable"

        # Test 4: gather_environment() raises exception - should be handled
        mock_format_environment_block.reset_mock(side_effect=True)
        mock_format_environment_block.return_value = "Test environment"
        mock_gather_environment.side_effect = OSError("Cannot gather env")

        # This should NOT crash
        textual_app._resolve_provider_from_env()

        # Verify environment context was set to fallback
        assert textual_app.environment_context == "Environment context unavailable"

    @patch("henchman.config.context.ContextLoader")
    @patch("logging.error")
    def test_fill_context_tree_proper_error_logging(
        self,
        mock_logging_error,
        mock_context_loader_class,
        textual_app,
    ):
        """Test Bug 2 fix: Proper error logging instead of silent suppression.
        
        When context loading fails, errors should be logged properly instead of
        being silently suppressed with contextlib.suppress(Exception).
        """
        # Create a mock tree
        mock_tree = MagicMock()
        mock_root = MagicMock()
        mock_tree.root = mock_root

        # Setup mock to raise exception
        mock_loader = MagicMock()
        mock_context_loader_class.return_value = mock_loader
        mock_loader.discover_files.side_effect = ValueError("Context discovery failed")

        # Also make tree.root.add_leaf() fail
        mock_root.add_leaf.side_effect = AttributeError("Tree has no root")

        # Call the method - should log errors instead of silently suppressing
        textual_app._fill_context_tree(mock_tree)

        # Verify context loading was attempted
        mock_loader.discover_files.assert_called_once()

        # Verify error was logged for context loading failure
        mock_logging_error.assert_any_call("Failed to load context files: Context discovery failed")

        # Verify error was logged for UI failure
        mock_logging_error.assert_any_call("Failed to show error in UI: Tree has no root")

        # Verify tree.root.add_leaf() was attempted (and failed)
        mock_root.add_leaf.assert_called_once_with("Error loading context: Context discovery failed")

    @patch("builtins.open")
    @patch.object(HenchmanTextualApp, "query_one")
    @patch("logging.error")
    def test_persist_history_entry_shows_error_notification(
        self,
        mock_logging_error,
        mock_query_one,
        mock_open,
        textual_app,
    ):
        """Test Bug 3 fix: History persistence failures should show error notification.
        
        When history file cannot be written, users should be notified
        instead of silently ignoring the error with except Exception: pass.
        """
        # Setup mock input handler
        mock_input_handler = MagicMock()
        mock_input_handler.history_file = Path("/tmp/test_history")
        textual_app.input_handler = mock_input_handler

        # Mock chat pane for error message
        mock_chat_pane = MagicMock()
        mock_query_one.return_value = mock_chat_pane

        # Test 1: File open fails
        mock_open.side_effect = PermissionError("Cannot write to file")

        # Call the method - should log error and show notification
        textual_app._persist_history_entry("test command")

        # Verify error was logged
        mock_logging_error.assert_any_call("Failed to persist history entry: Cannot write to file")

        # Verify error notification was shown to user
        mock_chat_pane.add_error_message.assert_called_once_with(
            "Failed to save command history: Cannot write to file"
        )

        # Test 2: UI notification also fails
        mock_open.reset_mock()
        mock_logging_error.reset_mock()
        mock_chat_pane.reset_mock()
        mock_open.side_effect = OSError("Disk full")
        mock_query_one.side_effect = Exception("Widget not found")

        # Call the method - should log both errors
        textual_app._persist_history_entry("another command")

        # Verify both errors were logged
        mock_logging_error.assert_any_call("Failed to persist history entry: Disk full")
        mock_logging_error.assert_any_call("Failed to show history error in UI: Widget not found")
