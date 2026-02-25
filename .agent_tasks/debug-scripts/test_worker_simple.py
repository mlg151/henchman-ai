#!/usr/bin/env python3
"""Run Textual app in test mode - simpler version."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from textual import work
from textual.app import App, ComposeResult
from textual.message import Message
from textual.widgets import Footer, Header, RichLog


class DebugMessage(Message):
    def __init__(self, text: str) -> None:
        super().__init__()
        self.text = text


class DebugTextualApp(App):
    CSS = """
    RichLog { height: 1fr; }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        yield RichLog(id="chat-pane")
        yield Footer()

    def on_mount(self) -> None:
        log = self.query_one("#chat-pane", RichLog)
        log.write("[blue]Mounted[/]")
        self.run_test_worker()

    @work
    async def run_test_worker(self) -> None:
        log = self.query_one("#chat-pane", RichLog)
        log.write("[yellow]Worker started[/]")
        await asyncio.sleep(0.5)
        self.post_message(DebugMessage("Hello!"))
        await asyncio.sleep(0.5)
        log.write("[yellow]Worker done[/]")

    def on_debug_message(self, message: DebugMessage) -> None:
        log = self.query_one("#chat-pane", RichLog)
        log.write(f"[green]Handler: {message.text}[/]")


async def run_test():
    app = DebugTextualApp()
    async with app.run_test() as pilot:
        await asyncio.sleep(2)  # Wait for worker
        print("Test complete - check output above")


if __name__ == "__main__":
    print("=== Testing @work + message posting ===")
    print("Expected: Mounted -> Worker started -> Handler: Hello -> Worker done\n")
    asyncio.run(run_test())
    print("\n=== End of test ===")
