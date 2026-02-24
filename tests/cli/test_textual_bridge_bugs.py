"""Tests for bugs in textual_bridge.py."""

import pytest

from henchman.cli.textual_bridge import _format_error_text, _format_turn_status


def test_bug9_format_error_text_case_sensitivity():
    """Bug 9: _format_error_text has potential case sensitivity issue.
    
    Severity: Low (cosmetic)
    Description: The function calls kw.lower() on keywords that are already
    partially lowercase, and the logic might not handle all cases correctly.
    """
    # Test cases
    test_cases = [
        ("Invalid API key provided", "❌ API Error: Invalid or missing API key."),
        ("Authentication failed", "❌ API Error: Invalid or missing API key."),
        ("API KEY invalid", "❌ API Error: Invalid or missing API key."),  # All caps
        ("api key missing", "❌ API Error: Invalid or missing API key."),  # all lowercase
        ("Error: authentication required", "❌ API Error: Invalid or missing API key."),
        ("Some other error", "Some other error"),  # Not an auth error
    ]
    
    for error_input, expected in test_cases:
        result = _format_error_text(error_input)
        assert result == expected, f"Failed for '{error_input}': got '{result}', expected '{expected}'"
    
    # The bug might be that "authentication" is already lowercase in _AUTH_ERROR_KEYWORDS
    # but we call .lower() on it anyway, which is redundant but not wrong


def test_bug10_format_turn_status_missing_keys():
    """Bug 10: _format_turn_status doesn't handle missing keys gracefully.
    
    Severity: Medium (potential KeyError)
    Description: The function accesses data.get() for some keys but assumes
    data has certain keys, could crash with malformed data.
    """
    # Test with minimal data
    result = _format_turn_status({"iteration": 1})
    assert "Turn 1/?" in result  # max_iterations defaults to "?"
    
    # Test with missing iteration
    result = _format_turn_status({"max_iterations": 5})
    assert "Turn ?/5" in result  # iteration defaults to "?"
    
    # Test with tokens
    result = _format_turn_status({"iteration": 2, "max_iterations": 10, "tokens": 1500})
    assert "Turn 2/10" in result
    assert "1500 tokens" in result
    
    # Test with empty dict
    result = _format_turn_status({})
    assert "Turn ?/?" in result
    
    # Test with None (should this be handled?)
    # The function doesn't check if data is None, could crash


def test_bug11_event_bridge_forward_events_exception_handling():
    """Bug 11: forward_events catches all exceptions but doesn't re-raise.
    
    Severity: Medium (error hiding)
    Description: Exceptions in event stream are caught and converted to
    error messages, but the original exception is lost. This could hide
    bugs and leave the stream in an inconsistent state.
    """
    # This is harder to test without mocking async iterators
    # But we can document the issue
    pass


def test_bug12_event_handlers_missing_null_checks():
    """Bug 12: Some event handlers don't check for None/null data.
    
    Severity: Low (potential crashes)
    Description: Handlers like _on_content check if event.data exists,
    but others like _on_finished don't check event.source_agent.
    """
    from henchman.cli.textual_bridge import EventBridge
    from henchman.core.events import AgentEvent, EventType
    from unittest.mock import MagicMock
    
    bridge = EventBridge(MagicMock())
    bridge._post = MagicMock()
    
    # Test _on_finished with None source_agent
    event = AgentEvent(type=EventType.FINISHED, data=None, source_agent=None)
    bridge._on_finished(event)
    bridge._post.assert_called_once()
    
    # The handler should handle None source_agent gracefully
    call_args = bridge._post.call_args[0][0]
    assert call_args.source_agent is None  # Should be accepted


def test_bug13_tui_console_adapter_buffer_overflow():
    """Bug 13: TuiConsoleAdapter buffer could grow without bound.
    
    Severity: Medium (memory issue)
    Description: StringIO buffer accumulates output until flush_to_chat
    is called. If print() is called many times without flush, memory
    could grow excessively.
    """
    from henchman.cli.textual_bridge import TuiConsoleAdapter
    from unittest.mock import MagicMock
    
    app = MagicMock()
    adapter = TuiConsoleAdapter(app)
    
    # Write a lot of data without flushing
    for i in range(1000):
        adapter.print(f"Line {i}")
    
    # Buffer should have been flushed each time because print() calls flush_to_chat()
    # Actually, looking at the code, print() calls flush_to_chat() immediately
    # So this might not be a bug after all
    
    # Check the implementation
    import inspect
    source = inspect.getsource(adapter.print)
    assert "self.flush_to_chat()" in source, "print() should flush buffer"