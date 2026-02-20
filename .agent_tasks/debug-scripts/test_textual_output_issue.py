#!/usr/bin/env python3
"""Minimal test to reproduce Textual TUI output issue."""

import asyncio
from textual.app import App, ComposeResult
from textual.widgets import RichLog, Header, Footer
from textual.message import Message
from textual import work


class ContentMessage(Message):
    """Message for content."""
    def __init__(self, content: str) -> None:
        super().__init__()
        self.content = content


class TestApp(App):
    """Test app to reproduce the issue."""
    
    CSS = """
    RichLog {
        height: 1fr;
    }
    """
    
    def compose(self) -> ComposeResult:
        yield Header()
        yield RichLog(id="chat-pane")
        yield Footer()
    
    def on_mount(self) -> None:
        """Initialize test."""
        self.title = "Output Test"
        log = self.query_one("#chat-pane", RichLog)
        
        # Test 1: Direct write (this should work)
        log.write("[green]1. Direct write works[/]")
        
        # Test 2: Post message from main thread
        self.post_message(ContentMessage("2. Posted from main thread"))
        
        # Test 3: Post from worker (simulates agent)
        self.test_worker()
    
    def on_content_message(self, message: ContentMessage) -> None:
        """Handle content message (simulates on_agent_content_message)."""
        log = self.query_one("#chat-pane", RichLog)
        log.write(f"[cyan]{message.content}[/]")
    
    @work
    async def test_worker(self) -> None:
        """Simulate agent worker thread posting messages."""
        await asyncio.sleep(1)
        
        # This simulates what EventBridge does
        self.post_message(ContentMessage("3. Posted from worker thread"))
        
        # Test rapid streaming
        for i in range(5):
            await asyncio.sleep(0.2)
            self.post_message(ContentMessage(f"4.{i+1} Stream chunk {i+1}"))


if __name__ == "__main__":
    import sys
    print("Starting Textual test app...")
    print("You should see 8 messages in the RichLog:")
    print("  1. Direct write works")
    print("  2. Posted from main thread")
    print("  3. Posted from worker thread")
    print("  4.1-4.5 Stream chunks")
    print("\nIf you only see message 1, the issue is with message handling.")
    print("If you see all messages, the issue is elsewhere.\n")
    
    app = TestApp()
    app.run()
