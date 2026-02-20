#!/usr/bin/env python3
"""Check live RichLog content."""

import asyncio
from textual.app import App, ComposeResult
from textual.widgets import RichLog
from textual.message import Message
from textual import work


class TestMsg(Message):
    def __init__(self, text):
        super().__init__()
        self.text = text


class TestApp(App):
    def compose(self) -> ComposeResult:
        yield RichLog(id="log")
    
    def on_mount(self):
        log = self.query_one("#log", RichLog)
        log.write("1. Direct from on_mount")
        self.worker_test()
    
    @work
    async def worker_test(self):
        self.post_message(TestMsg("2. Message from worker"))
    
    def on_test_msg(self, msg):
        log = self.query_one("#log", RichLog)
        log.write(f"Handler: {msg.text}")


async def test():
    app = TestApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        
        # Get live widget
        log = app.query_one("#log", RichLog)
        
        # Try to access internal content
        print("=== RichLog Content ===")
        
        # Try different properties
        if hasattr(log, 'lines'):
            print(f"lines: {log.lines}")
        if hasattr(log, '_lines'):
            print(f"_lines: {log._lines}")
        if hasattr(log, 'render_lines'):
            print("has render_lines")
            
        # Check if widget is displayed
        print(f"\nlog.displayed: {log.displayed}")
        print(f"log.visible: {log.visible}")
        print(f"log.size: {log.size}")
        print(f"log.region: {log.region}")


asyncio.run(test())
