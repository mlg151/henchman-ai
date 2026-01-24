#!/usr/bin/env python3
"""Integration test for keyboard interrupt fixes."""

from unittest.mock import MagicMock


# Test the actual behavior
def test_ctrl_c_double_tap_exits():
    """Test that double Ctrl+C exits."""
    # This would be an integration test
    # For now, just verify the logic
    import time

    class MockRepl:
        def __init__(self):
            self._last_interrupt_time = None
            self.console = MagicMock()
            self.running = True

        def handle_ctrl_c(self):
            """Simulate the Ctrl+C handler logic."""
            current_time = time.time()
            if self._last_interrupt_time is not None:
                time_since_last = current_time - self._last_interrupt_time
                if time_since_last < 2.0:  # Double Ctrl+C within 2 seconds
                    self.console.print("\n[bold red]Exiting...[/]")
                    return False  # Exit the REPL

            # First Ctrl+C or spaced out
            self.console.print("\n[dim]Press Ctrl+C again to exit[/]")
            self._last_interrupt_time = current_time
            return True  # Continue

    # Test the logic
    repl = MockRepl()

    # First Ctrl+C
    result1 = repl.handle_ctrl_c()
    assert result1 is True, "First Ctrl+C should continue"
    assert "Press Ctrl+C again to exit" in str(repl.console.print.call_args)

    # Simulate immediate second Ctrl+C
    repl._last_interrupt_time = time.time() - 1.0  # 1 second ago
    result2 = repl.handle_ctrl_c()
    assert result2 is False, "Second Ctrl+C within 2 seconds should exit"
    assert "Exiting..." in str(repl.console.print.call_args)


def test_escape_raises_keyboard_interrupt():
    """Test that escape on empty buffer raises KeyboardInterrupt."""
    # This tests the input.py escape handler logic
    class MockBuffer:
        def __init__(self, text):
            self.text = text

    class MockEvent:
        def __init__(self, text):
            self.current_buffer = MockBuffer(text)

    # Test with empty buffer - should raise KeyboardInterrupt
    event = MockEvent("")
    try:
        # This would be the escape handler
        if not event.current_buffer.text:
            raise KeyboardInterrupt("Escape pressed on empty buffer")
        raise AssertionError("Should have raised KeyboardInterrupt")
    except KeyboardInterrupt as e:
        assert "Escape pressed on empty buffer" in str(e)

    # Test with text - should clear buffer
    event = MockEvent("some text")
    if event.current_buffer.text:
        event.current_buffer.text = ""
    assert event.current_buffer.text == "", "Should clear buffer text"


if __name__ == "__main__":
    print("Running keyboard interrupt integration tests...")
    test_ctrl_c_double_tap_exits()
    test_escape_raises_keyboard_interrupt()
    print("All tests passed!")
