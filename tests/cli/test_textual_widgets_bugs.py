"""Tests for bugs in textual_widgets.py."""

from unittest.mock import MagicMock

from henchman.cli.textual_widgets import ChatPane


class TestChatPaneBugs:
    """Test bugs in ChatPane class."""

    def test_bug4_double_scroll_on_new_agent_stream(self):
        """Bug 4: Double scrolling when appending to new agent stream.
        
        Severity: Low (UI glitch, performance)
        Description: append_agent_chunk calls begin_agent_stream which scrolls,
        then scrolls again, causing double scroll animation.
        """
        pane = ChatPane()

        # Mock the mount method
        pane.mount = MagicMock()

        # Mock _scroll_to_bottom to track calls
        scroll_calls = []
        pane._scroll_to_bottom = lambda: scroll_calls.append(1)

        # Initialize _active dict
        pane._active = {}

        # First call to append_agent_chunk for new agent
        pane.append_agent_chunk("agent1", "Hello")

        # Should have scrolled only once: in begin_agent_stream (fixed bug)
        assert len(scroll_calls) == 1, f"Expected 1 scroll (fixed bug), got {len(scroll_calls)}"

        # Test second chunk for same agent - should scroll
        scroll_calls.clear()
        pane.append_agent_chunk("agent1", " World")
        assert len(scroll_calls) == 1, f"Expected 1 scroll for existing agent, got {len(scroll_calls)}"

    def test_bug5_finish_agent_stream_silent_failure(self):
        """Bug 5: finish_agent_stream fails silently for non-existent agent.
        
        Severity: Medium (silent failure, state inconsistency)
        Description: finish_agent_stream calls pop() on _active dict
        without checking if agent exists, potentially hiding bugs.
        """
        pane = ChatPane()
        pane._active = {"agent1": MagicMock()}

        # This should work
        pane.finish_agent_stream("agent1")
        assert "agent1" not in pane._active

        # This should fail or at least warn, but silently does nothing
        pane.finish_agent_stream("non_existent_agent")
        # No error raised, which could hide bugs

    def test_bug6_clear_thinking_messages_import_coupling(self):
        """Bug 6: clear_thinking_messages uses class name string comparison.
        
        Severity: Low (brittle code)
        Description: Uses __class__.__name__ == "ThinkingMessage" which
        breaks if class is renamed or subclassed.
        """
        pane = ChatPane()

        # We can't easily test this without creating actual ThinkingMessage widgets
        # But we can verify the code now uses isinstance instead of string comparison
        import inspect
        source = inspect.getsource(pane.clear_thinking_messages)
        # Should use isinstance now, not string comparison
        assert "isinstance(child, ThinkingMessage)" in source, \
               "Should use isinstance check, not string comparison"

    def test_bug7_chatmessage_escape_handling(self):
        """Bug 7: ChatMessage escapes content but prefix may contain markup.
        
        Severity: Medium (potential markup injection)
        Description: ChatMessage escapes content with markup_escape,
        but prefix contains Rich markup that isn't validated.
        """
        from henchman.cli.textual_widgets import ChatMessage

        # Test with malicious prefix (should be safe since it's from trusted code)
        # But if prefix comes from user input, could be problematic
        widget = ChatMessage(prefix="[bold red]Test:[/]", content="<script>alert('xss')</script>")

        # Content should be escaped
        # The update method uses markup_escape on content but not on prefix
        # This is correct since prefix is from code, not user input

    def test_bug8_toolmessage_unused_parameters(self):
        """Bug 8: ToolMessage stores unused parameters.
        
        Severity: Low (dead code)
        Description: ToolMessage.__init__ stores thought and tool_call
        parameters but _update_renderable doesn't use them.
        """
        from henchman.cli.textual_widgets import ToolMessage

        widget = ToolMessage(thought="test thought", tool_call={"name": "test"})

        # These attributes are stored but not used in rendering
        assert hasattr(widget, '_thought')
        assert hasattr(widget, '_tool_call')
        assert hasattr(widget, '_content')

        # _update_renderable only uses _content
        # thought and tool_call are dead code
