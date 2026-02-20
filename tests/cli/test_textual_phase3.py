"""Tests for Phase 3 Textual TUI improvements."""

from unittest.mock import MagicMock, patch

import pytest

from henchman.cli.textual_app import (
    HenchmanTextualApp,
    TextualConfig,
)


class TestTextualPhase3:
    """Test suite for Phase 3 improvements."""

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

    def test_context_viewer_structure(self, textual_app):
        """Test that Context Viewer uses a Tree widget."""
        # Verification similar to Phase 1, using mocks or inspecting compose
        # We expect a Tree widget in the Context tab

        # Manually inspect compose output or use patch
        with (
            patch("henchman.cli.textual_app.Tree") as mock_tree,
            patch("henchman.cli.textual_app.TabbedContent"),
            patch("henchman.cli.textual_app.TabPane"),
        ):
            list(textual_app.compose())
            # Should verify Tree is called
            mock_tree.assert_called()

    def test_status_bar_update(self, textual_app):
        """Test status bar updates with token info."""
        # Mock status bar
        textual_app.query_one = MagicMock()
        status_bar_mock = textual_app.query_one.return_value

        # Trigger an update
        textual_app.update_status("Ready", tokens=100, cost=0.002)

        # Verify status text assignment
        assert status_bar_mock.status_text == "Ready | 100 tokens | $0.0020"
