#!/usr/bin/env python3
"""Test Textual message handling with a simple app."""

import asyncio

from textual.app import App, ComposeResult
from textual.message import Message
from textual.widgets import Footer, Header, RichLog


class TestContentMessage(Message):
    """Test message."""
    def __init__(self, text: str) -> None:
        super().__init__()
        self.text = text


class TestApp(App):
    """Test app to verify message handling."""

    def compose(self) -> ComposeResult:
        yield Header()
        yield RichLog(id="log")
        yield Footer()

    def on_mount(self) -> None:
        """Post a message after mount."""
        log = self.query_one("#log", RichLog)
        log.write("App mounted - posting message in 1 second...")

        # Post a message after 1 second (like EventBridge does)
        asyncio.get_event_loop().call_later(1, self.post_message, TestContentMessage("Hello from message!"))

    def on_test_content_message(self, message: TestContentMessage) -> None:
        """Handle test content message - this should be called automatically."""
        log = self.query_one("#log", RichLog)
        log.write(f"[green]Handler called with: {message.text}[/]")


if __name__ == "__main__":
    print("Testing Textual message handling...")
    print("You should see:")
    print("  1. 'App mounted - posting message in 1 second...'")
    print("  2. One second later: 'Handler called with: Hello from message!'")
    print("\nIf you only see #1, the handler isn't being triggered.")
    print()

    app = TestApp()
    app.run()
