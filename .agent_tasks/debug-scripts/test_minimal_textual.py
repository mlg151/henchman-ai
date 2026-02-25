#!/usr/bin/env python3
"""Minimal test to isolate Textual TUI output issue."""

import asyncio

from textual import work
from textual.app import App, ComposeResult
from textual.message import Message
from textual.widgets import Footer, Header, RichLog


class TestMessage(Message):
    """Test message."""
    def __init__(self, content: str) -> None:
        super().__init__()
        self.content = content


class MinimalApp(App):
    """Minimal app to test RichLog output."""

    CSS = """
    RichLog {
        height: 1fr;
        border: solid green;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        yield RichLog(id="log")
        yield Footer()

    def on_mount(self) -> None:
        """Test posting messages."""
        self.title = "RichLog Test"

        # Direct write
        log = self.query_one(RichLog)
        log.write("Direct write works!")

        # Post message from same thread
        self.post_message(TestMessage("Posted message works!"))

        # Start worker to test async
        self.test_async()

    def on_test_message(self, message: TestMessage) -> None:
        """Handle test message."""
        log = self.query_one(RichLog)
        log.write(f"[cyan]Message handler: {message.content}[/]")

    @work
    async def test_async(self) -> None:
        """Test async message posting."""
        await asyncio.sleep(1)

        log = self.query_one(RichLog)
        log.write("[yellow]Direct write from worker works![/]")

        # Post message from worker
        self.post_message(TestMessage("Posted from worker works!"))

        # Test multiple rapid writes
        for i in range(5):
            await asyncio.sleep(0.2)
            log.write(f"[green]Stream chunk {i+1}[/]")


if __name__ == "__main__":
    app = MinimalApp()
    app.run()
