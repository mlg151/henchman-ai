#!/usr/bin/env python3
"""Check if RichLog actually renders the content."""

import asyncio

from textual import work
from textual.app import App, ComposeResult
from textual.message import Message
from textual.widgets import RichLog


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

        # Check what's in the log
        log = app.query_one("#log", RichLog)

        # Try to get rendered content
        print("=== Checking RichLog content ===")
        print(f"log object: {log}")
        print(f"log.unicode_text: {log.unicode_text[:200] if hasattr(log, 'unicode_text') else 'N/A'}")

        # Try alternate approach
        await asyncio.sleep(0.5)


asyncio.run(test())
