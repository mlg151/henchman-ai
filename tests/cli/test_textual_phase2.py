"""Tests for Phase 2 Textual TUI improvements."""

from unittest.mock import MagicMock, patch

import pytest

from henchman.cli.textual_app import (
    HenchmanTextualApp,
    TextualConfig,
)


class TestTextualPhase2:
    """Test suite for Phase 2 improvements."""

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

    def test_search_logic(self, textual_app):
        """Test search logic finding matches."""
        # Mock query_one to prevent ScreenStackError
        textual_app.query_one = MagicMock()
        textual_app.query_one.return_value.display = True  # for thinking/tool pane

        # Test basic search activation
        textual_app.action_search()
        assert textual_app._search_mode is True

        # Test performing search
        # We need to mock _search_richlog or the panes themselves
        with patch.object(textual_app, "_search_richlog") as mock_search_in_pane:
            textual_app._perform_search("test")

            # Should search in all valid panes
            # Note: logic might skip if panes are hidden/not found, but with mocks it should try
            assert mock_search_in_pane.call_count >= 1

    def test_slash_command_trigger(self, textual_app):
        """Test that slash commands trigger a popup or autocomplete state."""
        # Mock query_one
        textual_app.query_one = MagicMock()

        event = MagicMock()
        event.control.text = "/"

        with patch.object(textual_app, "_show_command_palette") as mock_show:
            textual_app.on_textarea_changed(event)
            mock_show.assert_called_once()

    def test_slash_command_filter(self, textual_app):
        """Test that typing filters the command list."""
        # Mock query_one
        textual_app.query_one = MagicMock()

        event = MagicMock()
        event.control.text = "/hel"

        with patch.object(textual_app, "_show_command_palette") as mock_show:
            textual_app.on_textarea_changed(event)
            mock_show.assert_called_with("/hel")

        # Also test _show_command_palette internals if desired, or assume trusted
        # Testing logic inside _show_command_palette:
        textual_app._show_command_palette("/hel")
        # Should clear options
        palette = textual_app.query_one.return_value
        palette.clear_options.assert_called()
        # add_option requires a command_processor with commands - skip if not set up
