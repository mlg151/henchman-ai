"""Tests for refactoring textual_widgets.py to address duplicate code smells."""

from unittest.mock import MagicMock

from henchman.cli.textual_widgets import ChatMessage, ChatPane, ThinkingMessage, ToolMessage


class TestChatPaneRefactoring:
    """Test refactoring of ChatPane to address duplicate code smells."""

    def test_add_message_with_prefix_creates_chatmessage(self):
        """Test that _add_message_with_prefix creates a ChatMessage widget."""
        pane = ChatPane()
        pane.mount = MagicMock()
        pane._scroll_to_bottom = MagicMock()

        # Mock _add_message_widget to track calls
        calls = []
        original_method = pane._add_message_widget

        def mock_add_message_widget(widget_class, *args, **kwargs):
            calls.append((widget_class, args, kwargs))
            # Create a mock widget
            widget = MagicMock(spec=widget_class)
            return widget

        pane._add_message_widget = mock_add_message_widget

        result = pane._add_message_with_prefix("[bold]Test:[/]", "Hello world")

        # Should call _add_message_widget with ChatMessage class
        assert len(calls) == 1
        widget_class, args, kwargs = calls[0]
        assert widget_class == ChatMessage
        assert args == ("[bold]Test:[/]", "Hello world")
        assert isinstance(result, MagicMock)

        # Restore original method
        pane._add_message_widget = original_method

    def test_add_thinking_message_creates_thinkingmessage(self):
        """Test that add_thinking_message creates a ThinkingMessage widget."""
        pane = ChatPane()
        pane.mount = MagicMock()
        pane._scroll_to_bottom = MagicMock()

        # Mock _add_message_widget to track calls
        calls = []
        original_method = pane._add_message_widget

        def mock_add_message_widget(widget_class, *args, **kwargs):
            calls.append((widget_class, args, kwargs))
            # Create a mock widget
            widget = MagicMock(spec=widget_class)
            return widget

        pane._add_message_widget = mock_add_message_widget

        result = pane.add_thinking_message("I'm thinking", "agent1")

        # Should call _add_message_widget with ThinkingMessage class
        assert len(calls) == 1
        widget_class, args, kwargs = calls[0]
        assert widget_class == ThinkingMessage
        assert args == ("I'm thinking", "agent1")
        assert isinstance(result, MagicMock)

        # Restore original method
        pane._add_message_widget = original_method

    def test_add_tool_message_creates_toolmessage(self):
        """Test that add_tool_message creates a ToolMessage widget."""
        pane = ChatPane()
        pane.mount = MagicMock()
        pane._scroll_to_bottom = MagicMock()

        # Mock _add_message_widget to track calls
        calls = []
        original_method = pane._add_message_widget

        def mock_add_message_widget(widget_class, *args, **kwargs):
            calls.append((widget_class, args, kwargs))
            # Create a mock widget
            widget = MagicMock(spec=widget_class)
            return widget

        pane._add_message_widget = mock_add_message_widget

        # Create a mock tool call
        mock_tool_call = MagicMock()
        mock_tool_call.name = "test_tool"
        mock_tool_call.arguments = '{"param": "value"}'

        result = pane.add_tool_message("Tool thought", mock_tool_call)

        # Should call _add_message_widget with ToolMessage class
        assert len(calls) == 1
        widget_class, args, kwargs = calls[0]
        assert widget_class == ToolMessage
        assert args == ("Tool thought", mock_tool_call)
        assert isinstance(result, MagicMock)

        # Restore original method
        pane._add_message_widget = original_method

    def test_partial_methods_work_correctly(self):
        """Test that the partial method wrappers (add_user_message, etc.) work correctly."""
        pane = ChatPane()

        # Mock _add_message_widget to track calls (since partial methods call it indirectly)
        calls = []
        original_method = pane._add_message_widget

        def mock_add_message_widget(widget_class, *args, **kwargs):
            calls.append((widget_class, args, kwargs))
            return MagicMock(spec=widget_class)

        pane._add_message_widget = mock_add_message_widget

        # Test add_user_message
        result1 = pane.add_user_message("User says hello")
        assert len(calls) == 1
        widget_class, args, kwargs = calls[0]
        assert widget_class == ChatMessage
        assert args == ("[bold green]You:[/]", "User says hello")
        assert isinstance(result1, MagicMock)

        # Test add_system_message
        calls.clear()
        result2 = pane.add_system_message("System message")
        assert len(calls) == 1
        widget_class, args, kwargs = calls[0]
        assert widget_class == ChatMessage
        assert args == ("[dim]»[/]", "System message")
        assert isinstance(result2, MagicMock)

        # Test add_error_message
        calls.clear()
        result3 = pane.add_error_message("Error occurred")
        assert len(calls) == 1
        widget_class, args, kwargs = calls[0]
        assert widget_class == ChatMessage
        assert args == ("[bold red]Error:[/]", "Error occurred")
        assert isinstance(result3, MagicMock)

        # Restore original method
        pane._add_message_widget = original_method

    def test_message_methods_have_correct_signatures(self):
        """Test that all message-adding methods have the correct signatures."""
        import inspect

        # Check _add_message_with_prefix on the class (unbound)
        sig = inspect.signature(ChatPane._add_message_with_prefix)
        params = list(sig.parameters.keys())
        assert params == ["self", "prefix", "text", "trusted"]
        # trusted has default value
        assert sig.parameters["trusted"].default is False
        # Return annotation might be a string due to forward references
        assert sig.return_annotation in ["ChatMessage", ChatMessage]

        # Check add_thinking_message
        sig = inspect.signature(ChatPane.add_thinking_message)
        params = list(sig.parameters.keys())
        assert params == ["self", "thought", "agent_name"]
        # agent_name has default value
        assert sig.parameters["agent_name"].default == ""
        # Return annotation might be a string due to forward references
        assert sig.return_annotation in ["ThinkingMessage", ThinkingMessage]

        # Check add_tool_message
        sig = inspect.signature(ChatPane.add_tool_message)
        params = list(sig.parameters.keys())
        assert params == ["self", "thought", "tool_call"]
        # Both parameters have default values
        assert sig.parameters["thought"].default == ""
        assert sig.parameters["tool_call"].default is None
        # Return annotation might be a string due to forward references
        assert sig.return_annotation in ["ToolMessage", ToolMessage]
