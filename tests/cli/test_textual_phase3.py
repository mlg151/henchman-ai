"""Tests for Phase 3 Textual TUI improvements."""

from unittest.mock import MagicMock

import pytest
from textual.widgets import Tree

from henchman.cli.textual_app import (
    HenchmanTextualApp,
    TextualConfig,
)
from henchman.config.schema import Settings


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

    async def test_context_viewer_structure(self, textual_app):
        """The mounted Context tab contains the actual context tree."""
        async with textual_app.run_test() as pilot:
            await pilot.pause()
            tree = textual_app.query_one("#context-tree", Tree)
            assert tree.parent.id == "tab-context"
            assert str(tree.root.label) == "Context Files"

    def test_status_bar_update(self, textual_app):
        """Test status bar updates with token info."""
        textual_app.query_one = MagicMock()
        status_bar_mock = textual_app.query_one.return_value

        textual_app.update_status("Ready", tokens=100, cost=0.002)

        # status_text holds the message, tokens/cost are separate reactives
        assert status_bar_mock.status_text == "Ready"
        assert status_bar_mock.tokens == 100
        assert status_bar_mock.cost == 0.002
