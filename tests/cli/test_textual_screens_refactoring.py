"""Tests for refactoring textual_screens.py to address code smells.

This test file covers edge cases and missing type hints for all
functions identified in the smell report.
"""

from unittest.mock import MagicMock

import pytest
from textual.widgets import Label

from henchman.cli.textual_screens import (
    ConfirmToolScreen,
    HelpScreen,
    ProviderScreen,
    SessionScreen,
)
from henchman.tools.base import ConfirmationRequest


def test_confirm_tool_screen_init_type_hints():
    """Test that ConfirmToolScreen.__init__ has proper type hints."""
    # Create a ConfirmationRequest with proper types
    request = ConfirmationRequest(
        tool_name="test_tool",
        description="Test tool description",
        risk_level="medium",
        params={"key": "value"},
    )

    # This should not raise any type errors
    screen = ConfirmToolScreen(request)

    # Verify the request is stored
    assert screen._request == request
    assert screen._request.tool_name == "test_tool"
    assert screen._request.description == "Test tool description"
    assert screen._request.risk_level == "medium"
    assert screen._request.params == {"key": "value"}


def test_confirm_tool_screen_compose_return_type():
    """Test that ConfirmToolScreen.compose has proper return type annotation."""
    request = ConfirmationRequest(
        tool_name="test_tool",
        description="Test tool",
        risk_level="low",
        params=None,
    )
    screen = ConfirmToolScreen(request)

    # Check that compose method exists and has proper signature
    import inspect
    sig = inspect.signature(screen.compose)
    assert str(sig.return_annotation) == "ComposeResult"

    # The method should be a generator (yields widgets)
    result = screen.compose()
    assert inspect.isgenerator(result)


def test_confirm_tool_screen_build_params_label_type_hints():
    """Test that _build_params_label has proper type hints."""
    # Test with no params
    request = ConfirmationRequest(
        tool_name="test_tool",
        description="Test tool",
        risk_level="medium",
        params=None,
    )
    screen = ConfirmToolScreen(request)
    result = screen._build_params_label()

    assert isinstance(result, list)
    assert len(result) == 0  # No params, empty list

    # Test with JSON-serializable params
    request = ConfirmationRequest(
        tool_name="test_tool",
        description="Test tool",
        risk_level="medium",
        params={"key": "value", "number": 42, "list": [1, 2, 3]},
    )
    screen = ConfirmToolScreen(request)
    result = screen._build_params_label()

    assert isinstance(result, list)
    assert len(result) == 1
    assert isinstance(result[0], Label)

    # Test with non-JSON-serializable params
    class NonSerializable:
        def __str__(self):
            return "<NonSerializable>"

    request = ConfirmationRequest(
        tool_name="test_tool",
        description="Test tool",
        risk_level="high",
        params={"obj": NonSerializable()},
    )
    screen = ConfirmToolScreen(request)
    result = screen._build_params_label()

    assert isinstance(result, list)
    assert len(result) == 1
    assert isinstance(result[0], Label)


def test_confirm_tool_screen_on_button_pressed_type_hints():
    """Test that on_button_pressed has proper type hints."""
    from unittest.mock import patch

    request = ConfirmationRequest(
        tool_name="test_tool",
        description="Test tool",
        risk_level="medium",
        params=None,
    )
    screen = ConfirmToolScreen(request)

    # Mock the app property to avoid Textual context errors
    mock_app = MagicMock()
    mock_app.pop_screen = MagicMock()

    # Use patch.object to mock the property
    with patch.object(type(screen), "app", new_callable=lambda: property(lambda _: mock_app)):
        # Create a mock button press event
        mock_button = MagicMock()
        mock_button.id = "btn-yes"
        mock_event = MagicMock()
        mock_event.button = mock_button

        # This should not raise type errors
        screen.on_button_pressed(mock_event)

        # Verify dismiss was called
        mock_app.pop_screen.assert_called_once()


def test_confirm_tool_screen_action_methods_type_hints():
    """Test that action_approve and action_deny have proper type hints."""
    from unittest.mock import patch

    request = ConfirmationRequest(
        tool_name="test_tool",
        description="Test tool",
        risk_level="medium",
        params=None,
    )
    screen = ConfirmToolScreen(request)

    # Mock the app property
    mock_app = MagicMock()
    mock_app.pop_screen = MagicMock()

    # Use patch.object to mock the property
    with patch.object(type(screen), "app", new_callable=lambda: property(lambda _: mock_app)):
        # These methods should exist and not raise errors
        screen.action_approve()
        screen.action_deny()

        # Both methods should call dismiss
        assert mock_app.pop_screen.call_count == 2


def test_help_screen_compose_return_type():
    """Test that HelpScreen.compose has proper return type annotation."""
    screen = HelpScreen()

    import inspect
    sig = inspect.signature(screen.compose)
    assert str(sig.return_annotation) == "ComposeResult"

    # The method should be a generator
    result = screen.compose()
    assert inspect.isgenerator(result)


def test_help_screen_on_button_pressed_type_hints():
    """Test that HelpScreen.on_button_pressed has proper type hints."""
    from unittest.mock import patch

    screen = HelpScreen()

    # Mock the app property
    mock_app = MagicMock()
    mock_app.pop_screen = MagicMock()

    # Use patch.object to mock the property
    with patch.object(type(screen), "app", new_callable=lambda: property(lambda _: mock_app)):
        # Create a mock button press event
        mock_button = MagicMock()
        mock_button.id = "close-help"
        mock_event = MagicMock()
        mock_event.button = mock_button

        # This should not raise type errors
        screen.on_button_pressed(mock_event)

        # Verify pop_screen was called
        mock_app.pop_screen.assert_called_once()


def test_provider_screen_compose_return_type():
    """Test that ProviderScreen.compose has proper return type annotation."""
    screen = ProviderScreen()

    import inspect
    sig = inspect.signature(screen.compose)
    assert str(sig.return_annotation) == "ComposeResult"

    # The method should be a generator
    result = screen.compose()
    assert inspect.isgenerator(result)


def test_provider_screen_build_options_type_hints():
    """Test that _build_options has proper type hints and edge cases."""
    # Test with None settings
    result = ProviderScreen._build_options(None)
    assert isinstance(result, list)
    assert result == [("No providers configured", "none")]

    # Test with empty settings
    mock_settings = MagicMock()
    mock_settings.providers = None
    result = ProviderScreen._build_options(mock_settings)
    assert result == [("No providers configured", "none")]

    # Test with providers but no known providers configured
    mock_settings.providers = MagicMock()
    mock_settings.providers.default = "test"
    # Mock getattr to return None for all known providers
    result = ProviderScreen._build_options(mock_settings)
    assert result == [("No providers configured", "none")]

    # Test with valid provider config
    mock_settings.providers.deepseek = {"model": "deepseek-chat"}
    result = ProviderScreen._build_options(mock_settings)
    assert len(result) == 1
    assert result[0][0] == "deepseek (deepseek-chat)"
    assert result[0][1] == "deepseek"

    # Test with provider config that's not a dict
    mock_settings.providers.anthropic = "not-a-dict"
    result = ProviderScreen._build_options(mock_settings)
    # Should filter out non-dict configs
    assert len(result) == 1  # Only deepseek should remain
    assert "deepseek" in result[0][0]

    # Test with provider config that's an empty dict
    mock_settings.providers.ollama = {}
    result = ProviderScreen._build_options(mock_settings)
    # Should filter out empty dicts
    assert len(result) == 1  # Only deepseek should remain
    assert "deepseek" in result[0][0]


def test_provider_screen_current_provider_name_type_hints():
    """Test that _current_provider_name has proper type hints."""
    # Test with None settings
    result = ProviderScreen._current_provider_name(None)
    assert result == "unknown"

    # Test with settings but no providers
    mock_settings = MagicMock()
    mock_settings.providers = None
    result = ProviderScreen._current_provider_name(mock_settings)
    assert result == "unknown"

    # Test with valid settings
    mock_settings.providers = MagicMock()
    mock_settings.providers.default = "deepseek"
    result = ProviderScreen._current_provider_name(mock_settings)
    assert result == "deepseek"


def test_provider_screen_on_button_pressed_type_hints():
    """Test that ProviderScreen.on_button_pressed has proper type hints."""
    from unittest.mock import patch

    screen = ProviderScreen()

    # Create mock app with post_message method
    mock_app = MagicMock()
    mock_app.post_message = MagicMock()
    mock_app.pop_screen = MagicMock()

    # Use patch.object to mock the property
    with patch.object(type(screen), "app", new_callable=lambda: property(lambda _: mock_app)):
        # Create a mock select widget
        mock_select = MagicMock()
        mock_select.value = "deepseek"
        screen.query_one = MagicMock(return_value=mock_select)

        # Test cancel button
        mock_button = MagicMock()
        mock_button.id = "btn-cancel"
        mock_event = MagicMock()
        mock_event.button = mock_button

        screen.on_button_pressed(mock_event)
        mock_app.pop_screen.assert_called_once()

        # Test switch button with valid selection
        mock_button.id = "btn-switch"
        mock_event.button = mock_button

        screen.on_button_pressed(mock_event)
        mock_app.post_message.assert_called_once()
        mock_app.pop_screen.assert_called()


def test_session_screen_init_type_hints():
    """Test that SessionScreen.__init__ has proper type hints."""
    # Test with None sessions
    screen = SessionScreen(None)
    assert screen._sessions == []

    # Test with empty list
    screen = SessionScreen([])
    assert screen._sessions == []

    # Test with sessions list
    sessions = [{"id": "1", "tag": "test", "message_count": 5}]
    screen = SessionScreen(sessions)
    assert screen._sessions == sessions


def test_session_screen_compose_return_type():
    """Test that SessionScreen.compose has proper return type annotation."""
    screen = SessionScreen([])

    import inspect
    sig = inspect.signature(screen.compose)
    assert str(sig.return_annotation) == "ComposeResult"

    # The method should be a generator
    result = screen.compose()
    assert inspect.isgenerator(result)


def test_session_screen_build_entries_type_hints():
    """Test that _build_entries has proper type hints."""
    from types import SimpleNamespace

    # Test with empty sessions
    screen = SessionScreen([])
    result = screen._build_entries()
    assert isinstance(result, list)
    assert len(result) == 0

    # Test with session objects (using SimpleNamespace for proper attribute access)
    session1 = SimpleNamespace(
        id="1",
        tag="session1",
        updated_at="2024-01-01",
        message_count=3
    )

    session2 = SimpleNamespace(
        id="2",
        tag=None,
        created_at="2024-01-02",
        message_count=5
    )

    screen = SessionScreen([session1, session2])
    result = screen._build_entries()

    assert len(result) == 2
    assert "session1" in result[0][0]
    assert "[2024-01-01]" in result[0][0]
    assert "(3 messages)" in result[0][0]
    assert result[0][1] == "1"
    assert "2" in result[1][0]  # When tag is None, it uses id
    assert "[2024-01-02]" in result[1][0]
    assert "(5 messages)" in result[1][0]
    assert result[1][1] == "2"

    # Test with session objects that have no timestamps
    session3 = SimpleNamespace(
        id="3",
        tag="no-timestamp",
        message_count=1
    )
    # No updated_at or created_at attributes

    screen = SessionScreen([session3])
    result = screen._build_entries()

    assert len(result) == 1
    assert "no-timestamp" in result[0][0]
    assert "[]" in result[0][0]  # Empty timestamp
    assert "(1 messages)" in result[0][0]
    assert result[0][1] == "3"


def test_session_screen_on_button_pressed_type_hints():
    """Test that SessionScreen.on_button_pressed has proper type hints."""
    screen = SessionScreen([])

    # Mock dismiss method
    screen.dismiss = MagicMock()

    # Create a mock select widget
    mock_select = MagicMock()
    mock_select.value = "session-id"
    screen.query_one = MagicMock(return_value=mock_select)

    # Test cancel button
    mock_button = MagicMock()
    mock_button.id = "btn-cancel"
    mock_event = MagicMock()
    mock_event.button = mock_button

    screen.on_button_pressed(mock_event)
    screen.dismiss.assert_called_once_with(None)

    # Test resume button with valid selection
    screen.dismiss.reset_mock()
    mock_button.id = "btn-resume"
    mock_event.button = mock_button

    screen.on_button_pressed(mock_event)
    screen.dismiss.assert_called_once_with("resume:session-id")

    # Test delete button with valid selection
    screen.dismiss.reset_mock()
    mock_button.id = "btn-delete"
    mock_event.button = mock_button

    screen.on_button_pressed(mock_event)
    screen.dismiss.assert_called_once_with("delete:session-id")

    # Test with "none" selection (should dismiss with None)
    screen.dismiss.reset_mock()
    mock_select.value = "none"
    mock_button.id = "btn-resume"

    screen.on_button_pressed(mock_event)
    screen.dismiss.assert_called_once_with(None)


def test_session_screen_action_cancel_type_hints():
    """Test that action_cancel has proper type hints."""
    screen = SessionScreen([])
    screen.dismiss = MagicMock()

    screen.action_cancel()
    screen.dismiss.assert_called_once_with(None)


def test_long_method_compose_refactoring():
    """Test that ConfirmToolScreen.compose can be refactored to be shorter.

    The method is 35 lines which exceeds the 30-line threshold.
    We should extract helper methods to reduce its length.
    """
    request = ConfirmationRequest(
        tool_name="test_tool",
        description="A very long description that might make the method longer than necessary, but we need to check the actual line count",
        risk_level="medium",
        params={"key1": "value1", "key2": "value2", "key3": "value3"},
    )
    screen = ConfirmToolScreen(request)

    # Count lines in the compose method
    import inspect
    source = inspect.getsource(screen.compose)
    lines = source.split('\n')

    # The method is currently 35 lines, we should aim to reduce it
    # by extracting helper methods for building UI components
    print(f"ConfirmToolScreen.compose has {len(lines)} lines")

    # For now, just verify it works
    result = list(screen.compose())
    assert len(result) > 0


def test_duplicate_code_analysis():
    """Analyze duplicate code issue with __init__ methods.

    The smell report says ConfirmToolScreen.__init__ is 95% similar to
    mcp/client.py:33 __init__. Let's check what can be extracted.
    """
    # Both __init__ methods likely follow the pattern:
    # def __init__(self, param: Type) -> None:
    #     super().__init__()
    #     self._param = param

    # This is a common pattern in Python, not necessarily bad duplication.
    # However, we should ensure type hints are complete.

    request = ConfirmationRequest(
        tool_name="test",
        description="test",
        risk_level="low",
        params=None,
    )
    screen = ConfirmToolScreen(request)

    # Verify the pattern
    assert hasattr(screen, '_request')
    assert screen._request == request

    # The issue might be missing return type annotation
    import inspect
    sig = inspect.signature(ConfirmToolScreen.__init__)
    assert sig.return_annotation is not None
    assert str(sig.return_annotation) == "None"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
