"""Tests for Phase 1 Textual TUI improvements."""

from unittest.mock import MagicMock

import pytest
from textual.widgets import TabbedContent, TabPane

from henchman.cli.textual_app import (
    HenchmanTextualApp,
    TextualConfig,
)
from henchman.cli.textual_widgets import HenchmanTextArea
from henchman.config.schema import Settings


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
        settings = Settings()
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

    async def test_tabbed_structure(self, textual_app):
        """Mount the actual tabs, navigation, and multiline composer."""
        async with textual_app.run_test() as pilot:
            await pilot.pause()
            tabs = textual_app.query_one(TabbedContent)
            assert [pane.id for pane in tabs.query(TabPane)] == [
                "tab-chat", "tab-thinking", "tab-tools", "tab-context", "tab-workspace",
            ]
            assert textual_app.query_one("#input", HenchmanTextArea).has_focus
            assert textual_app.query_one("#chat-navigation").parent.id == "tab-chat"

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
