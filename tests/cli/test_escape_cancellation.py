"""Tests for escape key cancellation of agent tasks in TUI."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from henchman.cli.textual_app import (
    HenchmanTextualApp,
    TextualConfig,
)


class TestEscapeCancellation:
    """Tests for escape key cancelling agent tasks."""

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

    def test_escape_key_binding_exists(self, textual_app):
        """Test that escape key binding is defined."""
        # Check that escape binding exists
        escape_binding = None
        for binding in textual_app.BINDINGS:
            if binding.key == "escape":
                escape_binding = binding
                break

        assert escape_binding is not None
        assert escape_binding.key == "escape"
        assert escape_binding.action == "cancel_or_clear"
        assert escape_binding.description == "Cancel/Clear"

    def test_action_cancel_or_clear_method_exists(self, textual_app):
        """Test that cancel_or_clear action method exists."""
        assert hasattr(textual_app, "action_cancel_or_clear")
        assert callable(textual_app.action_cancel_or_clear)

    def test_is_processing_property_exists(self, textual_app):
        """Test that is_processing property exists."""
        assert hasattr(textual_app, "is_processing")
        # It should be a property or attribute
        # Just check it exists, don't worry about type

    def test_current_agent_task_attribute_exists(self, textual_app):
        """Test that current_agent_task attribute can exist."""
        # This attribute is set dynamically, but we should be able to set it
        textual_app.current_agent_task = MagicMock()
        assert hasattr(textual_app, "current_agent_task")

    def test_cancel_or_clear_cancels_agent_task_when_processing(self):
        """Test that cancel_or_clear cancels agent task when is_processing is True."""
        # Create app with mocks
        mock_provider = MagicMock()
        mock_settings = MagicMock()
        mock_settings.ui.theme = "dark"
        mock_settings.ui.keybindings = {}

        app = HenchmanTextualApp(
            provider=mock_provider,
            config=TextualConfig(),
            settings=mock_settings,
            environment_context="Test",
        )

        # Create a mock task
        mock_task = AsyncMock()
        mock_task.cancel = MagicMock()
        mock_task.done = MagicMock(return_value=False)

        # Set up app state
        app.is_processing = True
        app.current_agent_task = mock_task

        # Mock the status bar query
        mock_status_bar = MagicMock()
        mock_status_bar.status_text = ""
        with patch.object(app, "query_one", return_value=mock_status_bar):
            # Call the action
            app.action_cancel_or_clear()

            # Verify task was cancelled
            mock_task.cancel.assert_called_once()

            # Verify status was updated
            assert mock_status_bar.status_text == "Cancelling..."

    def test_cancel_or_clear_clears_search_when_not_processing(self):
        """Test that cancel_or_clear clears search when not processing."""
        # Create app with mocks
        mock_provider = MagicMock()
        mock_settings = MagicMock()
        mock_settings.ui.theme = "dark"
        mock_settings.ui.keybindings = {}

        app = HenchmanTextualApp(
            provider=mock_provider,
            config=TextualConfig(),
            settings=mock_settings,
            environment_context="Test",
        )

        # Set up app state
        app.is_processing = False
        app._search_mode = True
        app._search_query = "test query"
        app._search_matches = ["match1", "match2"]
        app._current_match_index = 1

        # Mock the clear_search action
        app.action_clear_search = MagicMock()

        # Call the action
        app.action_cancel_or_clear()

        # Verify clear_search was called
        app.action_clear_search.assert_called_once()

    def test_cancel_or_clear_does_nothing_when_no_task(self):
        """Test that cancel_or_clear handles missing task gracefully."""
        # Create app with mocks
        mock_provider = MagicMock()
        mock_settings = MagicMock()
        mock_settings.ui.theme = "dark"
        mock_settings.ui.keybindings = {}

        app = HenchmanTextualApp(
            provider=mock_provider,
            config=TextualConfig(),
            settings=mock_settings,
            environment_context="Test",
        )

        # Set up app state but no task
        app.is_processing = True
        # Don't set current_agent_task

        # Mock the status bar query
        mock_status_bar = MagicMock()
        mock_status_bar.status_text = ""
        with patch.object(app, "query_one", return_value=mock_status_bar):
            # Should not raise exception
            app.action_cancel_or_clear()

            # Should fall back to clear_search
            # Since we didn't mock it, it will try to call the real method
            # which is fine for this test

    async def test_escape_during_agent_operation(self):
        """Integration test: escape during agent operation should cancel task."""

        # Create a real async task that we can cancel
        async def long_running_task():
            try:
                await asyncio.sleep(10)  # Simulate long operation
                return "completed"
            except asyncio.CancelledError:
                return "cancelled"

        # Create app
        mock_provider = MagicMock()
        mock_settings = MagicMock()
        mock_settings.ui.theme = "dark"
        mock_settings.ui.keybindings = {}

        app = HenchmanTextualApp(
            provider=mock_provider,
            config=TextualConfig(),
            settings=mock_settings,
            environment_context="Test",
        )

        # Create and start task
        task = asyncio.create_task(long_running_task())
        app.is_processing = True
        app.current_agent_task = task

        # Mock status bar
        mock_status_bar = MagicMock()
        mock_status_bar.status_text = ""
        with patch.object(app, "query_one", return_value=mock_status_bar):
            # Cancel the task
            app.action_cancel_or_clear()

            # Wait a bit for cancellation to propagate
            await asyncio.sleep(0.01)

            # Verify task was cancelled
            assert task.cancelled()

            # Check result - handle cancelled task properly
            try:
                result = await task
            except asyncio.CancelledError:
                result = "cancelled"
            assert result == "cancelled"
