#!/usr/bin/env python3
"""Run Textual app in test mode with debug output."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from textual.app import App, ComposeResult
from textual.widgets import RichLog, Header, Footer
from textual.message import Message
from textual import work


class DebugMessage(Message):
    """Debug message."""
    def __init__(self, text: str) -> None:
        super().__init__()
        self.text = text


class DebugTextualApp(App):
    """Debug app to trace message flow."""
    
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
        """On mount, log and schedule a test."""
        log = self.query_one("#chat-pane", RichLog)
        log.write("[blue]Mounted - scheduling worker...[/]")
        
        # Schedule the test worker
        self.run_test_worker()
    
    @work
    async def run_test_worker(self) -> None:
        """Worker that simulates agent running."""
        log = self.query_one("#chat-pane", RichLog)
        
        log.write("[yellow]Worker started[/]")
        
        await asyncio.sleep(0.5)
        
        # Post a message (like EventBridge does)
        log.write("[yellow]About to post message...[/]")
        self.post_message(DebugMessage("Hello from worker!"))
        
        await asyncio.sleep(0.5)
        
        log.write("[yellow]Worker done[/]")
    
    def on_debug_message(self, message: DebugMessage) -> None:
        """Handle debug message."""
        log = self.query_one("#chat-pane", RichLog)
        log.write(f"[green]Handler received: {message.text}[/]")


async def run_test():
    """Run the test."""
    app = DebugTextualApp()
    print("Starting app...")
    
    # Run in test mode
    async with app.run_test() as pilot:
        print("App running, waiting for worker...")
        
        # Wait for worker to complete
        await asyncio.sleep(3)
        
        print("Test complete!")
        
        # Get the log content
        log = app.query_one("#chat-pane", RichLog)
        print(f"\nLog write count: {len(log._lines)}")


if __name__ == "__main__":
    asyncio.run(run_test())
