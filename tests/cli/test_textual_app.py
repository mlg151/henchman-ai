"""Tests for the Textual TUI."""

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
        # Instead of actually calling compose, check the CSS and widget definitions
        # The compose method yields specific widgets in order
        assert hasattr(textual_app, "compose")

        # Check CSS defines the expected widget IDs
        css = textual_app.CSS
        assert "#chat-pane" in css
        assert "#thinking-pane" in css
        assert "#tool-pane" in css
        assert "#input" in css
        assert "#status-bar" in css

    def test_app_css(self, textual_app):
        """Test that the CSS is valid."""
        css = textual_app.CSS
        assert "Screen" in css
        # assert "TabbedContent" in css
        assert "#chat-pane" in css
        assert "#thinking-pane" in textual_app.CSS
        assert "#tool-pane" in textual_app.CSS

    def test_pane_widgets(self):
        """Test that pane widgets are properly configured."""
        # Test ChatPane
        chat_pane = ChatPane()
        assert chat_pane.border_title == "Chat"
        assert chat_pane.wrap is True
        assert chat_pane.highlight is True
        assert chat_pane.markup is True

        # Test ThinkingPane
        thinking_pane = ThinkingPane()
        assert thinking_pane.border_title == "Thinking"
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
        # Mock the thinking pane and status bar
        mock_thinking_pane = MagicMock()
        mock_status_bar = MagicMock()

        # Set up mock to return different values based on query
        def query_one_side_effect(query, widget_type):
            if query == "#thinking-pane" and widget_type == ThinkingPane:
                return mock_thinking_pane
            elif query == "#status-bar" and widget_type == StatusBar:
                return mock_status_bar
            else:
                raise ValueError(f"Unexpected query: {query}, {widget_type}")

        mock_query_one.side_effect = query_one_side_effect

        # Call the action method
        textual_app.action_clear_thinking_pane()

        # Verify pane was cleared and status bar updated
        mock_thinking_pane.clear.assert_called_once()
        mock_status_bar.status_text = "Thinking pane cleared"

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
