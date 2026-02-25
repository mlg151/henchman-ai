#!/usr/bin/env python3
"""Compare worker vs non-worker."""

import asyncio

from textual import work
from textual.app import App, ComposeResult
from textual.message import Message
from textual.widgets import RichLog


class TestMessage(Message):
    def __init__(self, text):
        super().__init__()
        self.text = text


class TestApp(App):
    def compose(self) -> ComposeResult:
        yield RichLog(id="log")

    def on_mount(self):
        log = self.query_one("#log", RichLog)
        log.write("1. Direct in on_mount")

        # Try worker
        self.worker_test()

        # Also try direct message post
        self.post_message(TestMessage("4. Direct message post"))

    @work
    async def worker_test(self):
        log = self.query_one("#log", RichLog)
        log.write("2. From worker")
        await asyncio.sleep(0.1)
        self.post_message(TestMessage("3. Message from worker"))

    def on_test_message(self, message):
        log = self.query_one("#log", RichLog)
        log.write(f"Handler: {message.text}")


async def test():
    app = TestApp()
    async with app.run_test() as pilot:
        await asyncio.sleep(0.5)
        print("Check above - only '1. Direct in on_mount' should appear if bug exists")

asyncio.run(test())
