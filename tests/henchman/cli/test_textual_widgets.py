'''tests/henchman/cli/test_textual_widgets.py
TDD tests for ThinkingMessage fix and ToolMessage.''' 

import pytest
from unittest.mock import MagicMock
from rich.text import Text

from henchman.cli.textual_app import ThinkingMessage, ChatPane

class TestThinkingMessageFixed:
    def test_collapsed_by_default(self):
        msg = ThinkingMessage('Test thought', 'Agent')
        assert msg._is_expanded is False
        render_str = str(msg.header.render())
        assert 'thinking:' in render_str
        assert 'Test thought' not in render_str  # Content hidden by CSS
        assert 'click to expand' in render_str.lower()

    def test_expanded_shows_content_via_css(self):
        msg = ThinkingMessage('Hidden content')
        msg.toggle_expansion()
        assert msg._is_expanded is True
        assert 'expanded' in msg.classes
        assert 'Hidden content' in str(msg.content.render())

    def test_append_updates(self):
        msg = ThinkingMessage('')
        msg.append('streaming...')
        assert 'streaming' in str(msg.content.render())

    def test_header_click_toggle(self):
        msg = ThinkingMessage('test')
        msg.on_click(MagicMock())
        assert msg._is_expanded is True

class TestChatPaneThinking:
    def test_begin_thinking(self):
        pane = ChatPane()
        msg = pane.begin_thinking_stream('Agent')
        assert isinstance(msg, ThinkingMessage)
        assert msg._agent_name == 'Agent'
        assert len(pane._active_thinking) == 1

    def test_append_thinking(self):
        pane = ChatPane()
        pane.append_thinking_chunk('Agent', 'chunk')
        assert len(pane.children) > 0
        thinking_msgs = [c for c in pane.children if isinstance(c, ThinkingMessage)]
        assert len(thinking_msgs) == 1

@pytest.mark.skip("ToolMessage not implemented")
class TestToolMessage:
    pass

@pytest.mark.skip("Tool integration not implemented")
class TestChatPaneTools:
    pass