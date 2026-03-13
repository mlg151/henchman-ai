"""Test file for textual_widgets.py refactoring."""
import pytest
from unittest.mock import Mock, AsyncMock
from textual.widgets import Static
from henchman.cli.textual_widgets import (
    ChatPane,
    ChatMessage,
    ThinkingMessage,
    ToolMessage,
    _BaseRichLogPane,
    StatusBar,
    _AGENT_PREFIX_TEMPLATE,
    _USER_PREFIX,
    _SYSTEM_PREFIX,
    _ERROR_PREFIX,
)


class TestChatPane:
    """Test ChatPane widget functionality."""
    
    def test_init(self):
        """Test ChatPane initialization."""
        pane = ChatPane()
        assert pane._active == {}
        assert pane._active_thinking == {}
        
    def test_add_user_message(self):
        """Test adding user messages."""
        pane = ChatPane()
        # Mock the _add_message_widget method
        pane._add_message_widget = Mock(return_value=Mock(spec=ChatMessage))
        result = pane.add_user_message("Hello")
        pane._add_message_widget.assert_called_once_with(ChatMessage, _USER_PREFIX, "Hello")
        assert result == pane._add_message_widget.return_value
        
    def test_add_system_message(self):
        """Test adding system messages."""
        pane = ChatPane()
        pane._add_message_widget = Mock(return_value=Mock(spec=ChatMessage))
        result = pane.add_system_message("System message")
        pane._add_message_widget.assert_called_once_with(ChatMessage, _SYSTEM_PREFIX, "System message")
        assert result == pane._add_message_widget.return_value
        
    def test_add_error_message(self):
        """Test adding error messages."""
        pane = ChatPane()
        pane._add_message_widget = Mock(return_value=Mock(spec=ChatMessage))
        result = pane.add_error_message("Error occurred")
        pane._add_message_widget.assert_called_once_with(ChatMessage, _ERROR_PREFIX, "Error occurred")
        assert result == pane._add_message_widget.return_value
        
    def test_begin_agent_stream(self):
        """Test beginning an agent stream."""
        pane = ChatPane()
        pane._add_message_widget = Mock(return_value=Mock(spec=ChatMessage))
        result = pane.begin_agent_stream("test_agent")
        expected_prefix = _AGENT_PREFIX_TEMPLATE.format(name="test_agent")
        pane._add_message_widget.assert_called_once_with(
            ChatMessage,
            expected_prefix,
            "",
            tracking_dict=pane._active,
            tracking_key="test_agent"
        )
        assert result == pane._add_message_widget.return_value
        
    def test_add_thinking_message(self):
        """Test adding thinking messages."""
        pane = ChatPane()
        pane._add_message_widget = Mock(return_value=Mock(spec=ThinkingMessage))
        result = pane.add_thinking_message("I'm thinking", "test_agent")
        pane._add_message_widget.assert_called_once_with(ThinkingMessage, "I'm thinking", "test_agent")
        assert result == pane._add_message_widget.return_value
        
    def test_add_tool_message(self):
        """Test adding tool messages."""
        pane = ChatPane()
        pane._add_message_widget = Mock(return_value=Mock(spec=ToolMessage))
        tool_call = Mock()
        tool_call.name = "test_tool"
        tool_call.arguments = {"arg1": "value1"}
        result = pane.add_tool_message("Tool thought", tool_call)
        pane._add_message_widget.assert_called_once_with(ToolMessage, "Tool thought", tool_call)
        assert result == pane._add_message_widget.return_value


class TestMessageWidgets:
    """Test message widget classes."""
    
    def test_chat_message_init(self):
        """Test ChatMessage initialization."""
        message = ChatMessage("Test prefix", "Test content")
        # Check private attributes (they should be private)
        assert hasattr(message, '_prefix')
        assert hasattr(message, '_content_text')
        
    def test_thinking_message_init(self):
        """Test ThinkingMessage initialization."""
        message = ThinkingMessage("Test thought", "test_agent")
        # Check private attributes
        assert hasattr(message, '_thought')
        assert hasattr(message, '_agent_name')
        
    def test_tool_message_init(self):
        """Test ToolMessage initialization."""
        tool_call = Mock()
        tool_call.name = "test_tool"
        tool_call.arguments = {"arg1": "value1"}
        message = ToolMessage("Tool thought", tool_call)
        # Check private attributes
        assert hasattr(message, '_thought')
        assert hasattr(message, '_tool_call')


if __name__ == "__main__":
    pytest.main([__file__, "-v"])