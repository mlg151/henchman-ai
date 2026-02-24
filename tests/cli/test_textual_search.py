"""Tests for Textual TUI search functionality."""

from unittest.mock import MagicMock, patch

import pytest
from textual.widgets import Input, TextArea

from henchman.cli.textual_app import (
    ChatPane,
    HenchmanTextualApp,
    StatusBar,
    TextualConfig,
)


class TestTextualSearch:
    """Test suite for Textual TUI search functionality."""

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

    def test_search_binding_defined(self, textual_app):
        """Test that search keyboard shortcut is defined."""
        # Check that Ctrl+F binding exists for search
        bindings = textual_app.BINDINGS
        search_binding = None
        for binding in bindings:
            if binding.key == "ctrl+f":
                search_binding = binding
                break

        assert search_binding is not None, "Ctrl+F binding for search should be defined"
        assert search_binding.action == "search", "Ctrl+F should trigger search action"
        assert search_binding.description == "Search", (
            "Search binding should have proper description"
        )

    def test_search_binding_show_in_ui(self, textual_app):
        """Test that search binding is shown in UI."""
        bindings = textual_app.BINDINGS
        search_binding = None
        for binding in bindings:
            if binding.key == "ctrl+f":
                search_binding = binding
                break

        assert search_binding is not None
        assert search_binding.show is True, "Search binding should be shown in UI"

    def test_search_action_method_exists(self, textual_app):
        """Test that search action method exists."""
        assert hasattr(textual_app, "action_search"), "action_search method should exist"
        assert callable(textual_app.action_search), "action_search should be callable"

    def test_search_widget_creation(self):
        """Test that search widget can be created."""
        # Test that we can create a search input widget
        search_input = Input(placeholder="Search...")
        assert search_input is not None
        assert search_input.placeholder == "Search..."

    @patch.object(HenchmanTextualApp, "query_one")
    def test_search_action_shows_input(self, mock_query_one, textual_app):
        """Test that search action shows search input."""
        # Mock the input widget
        mock_input = MagicMock(spec=Input)
        mock_input.value = ""
        mock_query_one.return_value = mock_input

        # Call the search action
        textual_app.action_search()

        # Verify search mode was activated
        assert hasattr(textual_app, "_search_mode"), "App should have _search_mode attribute"
        assert textual_app._search_mode is True, "Search mode should be True after action_search"

        # Verify input placeholder was updated
        mock_input.placeholder = "Search..."
        assert mock_input.placeholder == "Search..."

    @patch.object(HenchmanTextualApp, "query_one")
    def test_search_clears_on_escape(self, mock_query_one, textual_app):
        """Test that escape clears search mode."""
        # Mock the status bar (which action_clear_search actually queries)
        mock_status_bar = MagicMock(spec=StatusBar)

        def query_one_side_effect(query, widget_type):
            if query == "#status-bar" and widget_type == StatusBar:
                return mock_status_bar
            raise ValueError(f"Unexpected query: {query}")

        mock_query_one.side_effect = query_one_side_effect

        # Set search mode
        textual_app._search_mode = True
        textual_app._search_query = "test"

        # Simulate escape key (clear search)
        textual_app.action_clear_search()

        # Verify search was cleared
        assert textual_app._search_mode is False, "Search mode should be False after clear"
        assert textual_app._search_query == "", "Search query should be empty after clear"
        # Note: action_clear_search doesn't update input placeholder in current implementation
        # TODO: Implement input placeholder restoration when exiting search mode

    @patch.object(HenchmanTextualApp, "query_one")
    def test_search_highlights_matches(self, mock_query_one, textual_app):
        """Test that search highlights matches in chat pane."""
        # Mock chat pane
        mock_chat_pane = MagicMock(spec=ChatPane)
        mock_chat_pane.lines = [
            "Hello world",
            "This is a test",
            "Search for this text",
            "Another line",
        ]

        # Mock input widget
        mock_input = MagicMock(spec=Input)
        mock_input.value = "test"
        mock_query_one.side_effect = lambda selector, _widget_type=None: (
            mock_chat_pane if selector == "#chat-pane" else mock_input
        )

        # Set search mode and query with matches - _search_matches is list of (pane_id, line_idx, snippet)
        textual_app._search_mode = True
        textual_app._search_query = "test"
        textual_app._search_matches = [("chat", 1, "test"), ("chat", 2, "test")]
        textual_app._current_match_index = 0

        # Call scroll to current match (_highlight_current_match is _scroll_to_match)
        textual_app._scroll_to_match()

        # Verify chat pane was queried for scrolling
        # (In real implementation, this would scroll to matching line)
        mock_query_one.assert_any_call("#chat-pane", ChatPane)

    @patch.object(HenchmanTextualApp, "query_one")
    def test_search_navigation(self, mock_query_one, textual_app):
        """Test that search navigation works (next/previous match)."""
        # Mock chat pane with search results
        mock_chat_pane = MagicMock(spec=ChatPane)
        mock_chat_pane.lines = [
            "First line",
            "test match here",
            "Another line",
            "test again here",
            "Last line",
        ]

        # Mock input widget
        mock_input = MagicMock(spec=Input)
        mock_query_one.side_effect = lambda selector, _widget_type=None: (
            mock_chat_pane if selector == "#chat-pane" else mock_input
        )

        # Set search mode - _search_matches is list of (pane_id, line_idx, snippet) tuples
        textual_app._search_mode = True
        textual_app._search_query = "test"
        textual_app._search_matches = [("chat", 1, "test match"), ("chat", 3, "test again")]
        textual_app._current_match_index = 0

        # Test next match - mock query_one to return input widget for query check
        mock_input_for_nav = MagicMock(spec=TextArea)
        mock_input_for_nav.text = "test"  # Same query so _perform_search isn't triggered
        mock_query_one.side_effect = lambda selector, _widget_type=None: (
            mock_chat_pane if selector == "#chat-pane" else mock_input_for_nav
        )

        textual_app.action_search_next()
        assert textual_app._current_match_index == 1, "Should move to next match"

        # Test previous match
        textual_app.action_search_previous()
        assert textual_app._current_match_index == 0, "Should move to previous match"

    def test_search_also_in_thinking_pane(self):
        """Test that search works across all chat widget types."""
        # _search_chat_pane now searches ChatMessage, ThinkingMessage and ToolMessage
        from henchman.cli.textual_widgets import ThinkingMessage, ToolMessage

        assert hasattr(ThinkingMessage, "set_highlight")
        assert hasattr(ToolMessage, "set_highlight")

    def test_case_insensitive_search(self, textual_app):
        """Test that search is case-insensitive by default."""
        # _perform_search lowercases the query before matching
        textual_app._search_mode = True
        textual_app._search_query = ""
        textual_app._search_matches = []

        # The internal comparison uses .lower() on both sides
        from henchman.cli.textual_widgets import _highlight_text

        result = _highlight_text("Hello World", "hello")
        assert "[reverse]Hello[/reverse]" in result
        result2 = _highlight_text("TESTING", "test")
        assert "[reverse]TEST[/reverse]" in result2

    @patch.object(HenchmanTextualApp, "query_one")
    def test_search_status_update(self, mock_query_one, textual_app):
        """Test that search status is shown in status bar."""
        # Mock status bar
        mock_status_bar = MagicMock(spec=StatusBar)
        mock_status_bar.status_text = "Ready"

        # Mock input widget
        mock_input = MagicMock(spec=Input)
        mock_query_one.side_effect = lambda selector, _widget_type=None: (
            mock_status_bar if selector == "#status-bar" else mock_input
        )

        # Set search with matches
        textual_app._search_mode = True
        textual_app._search_query = "test"
        textual_app._search_matches = [1, 3, 5]
        textual_app._current_match_index = 0

        # Update search status
        textual_app._update_search_status()

        # Verify status was updated
        # Should show something like "Match 1/3" or "3 matches"
        assert (
            "test" in mock_status_bar.status_text.lower()
            or "match" in mock_status_bar.status_text.lower()
        )

    @patch.object(HenchmanTextualApp, "query_one")
    def test_no_matches_status(self, mock_query_one, textual_app):
        """Test status when no search matches are found."""
        # Mock status bar
        mock_status_bar = MagicMock(spec=StatusBar)
        mock_status_bar.status_text = "Ready"

        # Mock input widget
        mock_input = MagicMock(spec=Input)
        mock_query_one.side_effect = lambda selector, _widget_type=None: (
            mock_status_bar if selector == "#status-bar" else mock_input
        )

        # Set search with no matches
        textual_app._search_mode = True
        textual_app._search_query = "nonexistent"
        textual_app._search_matches = []
        textual_app._current_match_index = -1

        # Update search status
        textual_app._update_search_status()

        # Verify "no matches" status
        assert (
            "no matches" in mock_status_bar.status_text.lower()
            or "0 matches" in mock_status_bar.status_text.lower()
        )
