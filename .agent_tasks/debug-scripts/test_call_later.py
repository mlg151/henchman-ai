#!/usr/bin/env python3
"""Test call_later instead of @work."""

import asyncio
from textual.app import App, ComposeResult
from textual.widgets import RichLog


class TestApp(App):
    def compose(self) -> ComposeResult:
        yield RichLog(id="log")
    
    def on_mount(self):
        log = self.query_one("#log", RichLog)
        log.write("1. Direct from on_mount")
        
        # Use call_later instead of @work
        self.call_later(self._delayed_write)
    
    def _delayed_write(self):
        """This runs on main thread."""
        log = self.query_one("#log", RichLog)
        log.write("2. From call_later (main thread)")


async def test():
    app = TestApp()
    async with app.run_test() as pilot:
        await asyncio.sleep(0.5)
        print("call_later works! Check output above")

asyncio.run(test())
