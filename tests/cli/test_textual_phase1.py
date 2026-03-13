"""Tests for Phase 1 Textual TUI improvements."""

from unittest.mock import MagicMock, patch

import pytest

from henchman.cli.textual_app import (
    HenchmanTextualApp,
    TextualConfig,
)


class TestTextualPhase1:
    """Test suite for Phase 1 improvements."""

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
        )
        return app

    @patch("henchman.cli.textual_app.TabbedContent")
    @patch("henchman.cli.textual_app.TabPane")
    @patch("henchman.cli.textual_app.ChatPane")
    @patch("henchman.cli.textual_app.ThinkingPane")
    @patch("henchman.cli.textual_app.ToolPane")
    @patch("henchman.cli.textual_app.Static")
    @patch("henchman.cli.textual_app.HenchmanTextArea")
    @patch("henchman.cli.textual_app.StatusBar")
    @patch("henchman.cli.textual_app.Footer")
    @patch("henchman.cli.textual_app.Header")
    def test_tabbed_structure(
        self,
        mock_header,
        mock_footer,
        mock_status_bar,
        mock_textarea,
        mock_static,
        mock_tool_pane,
        mock_thinking_pane,
        mock_chat_pane,
        mock_tab_pane,
        mock_tabbed_content,
        textual_app,
    ):
        """Test that the app uses TabbedContent structure."""
        # Mock the context manager behavior of TabbedContent and TabPane
        mock_tabbed_content.return_value.__enter__.return_value = MagicMock()
        mock_tab_pane.return_value.__enter__.return_value = MagicMock()

        # Execute compose
        list(textual_app.compose())

        # Verify TabbedContent was used
        mock_tabbed_content.assert_called_once()

        # Verify HenchmanTextArea was used for input
        mock_textarea.assert_called()
        # Verify the ID was set to 'input' in one of the calls
        input_call = [
            call
            for call in mock_textarea.call_args_list
            if "id='input'" in str(call) or "id" in call.kwargs and call.kwargs["id"] == "input"
        ]
        assert input_call, "HenchmanTextArea with id='input' not found"

    def test_textarea_input(self, textual_app):
        """Test that Input is replaced by TextArea."""
        # This is covered by test_tabbed_structure now via mocking
        pass

    def test_history_navigation_init(self, textual_app):
        """Test history navigation initialization."""
        # Should have history attributes
        assert hasattr(textual_app, "command_history")
        assert hasattr(textual_app, "history_index")
        assert textual_app.history_index == -1

    @pytest.mark.asyncio
    async def test_submit_textarea(self, textual_app):
        """Test submitting input from TextArea."""
        # Mock the process_user_input method
        textual_app.process_user_input = MagicMock()

        # Mock query_one to return a mock TextArea
        mock_textarea = MagicMock()
        mock_textarea.text = "Test message"
        mock_textarea.load_text = MagicMock()

        textual_app.query_one = MagicMock()
        textual_app.query_one.return_value = mock_textarea

        # Call action
        textual_app.action_submit_message()

        # Verify processing
        textual_app.process_user_input.assert_called_with("Test message")

        # Verify input was cleared via load_text
        mock_textarea.load_text.assert_called_with("")

        # Verify history update
        assert "Test message" in textual_app.command_history
