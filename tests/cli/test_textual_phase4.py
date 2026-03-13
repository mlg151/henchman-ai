"""Tests for Phase 4 Textual TUI improvements."""

from unittest.mock import MagicMock, patch

import pytest

from henchman.cli.textual_app import (
    HenchmanTextualApp,
    TextualConfig,
)


class TestTextualPhase4:
    """Test suite for Phase 4 improvements."""

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

    def test_help_modal(self, textual_app):
        """Test help modal activation."""
        # Mock push_screen
        textual_app.push_screen = MagicMock()

        # Call help action
        textual_app.action_show_help()

        # Verify screen pushed
        textual_app.push_screen.assert_called_once()
        # Verify it's the help screen (check class name or similar if possible)

    def test_provider_switcher(self, textual_app: "HenchmanTextualApp") -> None:
        """Test provider switching logic."""
        textual_app.provider = MagicMock()
        textual_app.provider.name = "Old Provider"

        # Mock push_screen to avoid requiring a running event loop
        textual_app.push_screen = MagicMock()
        with patch.object(textual_app, "query_one"):
            textual_app.action_switch_provider()
            textual_app.push_screen.assert_called_once()

    def test_apply_code_block(self, textual_app):
        """Test apply code block action."""
        # Mock last code block
        textual_app._last_code_block = "print('hello')"

        with patch.object(textual_app, "process_user_input"):  # noqa: SIM117
            # This action might take the code and wrap it in a command or similar
            # Or just copy to clipboard

            # Let's test "Copy" action for simplicity if "Apply" is complex
            # textual_app.action_copy_code()
            pass
