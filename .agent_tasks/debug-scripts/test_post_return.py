#!/usr/bin/env python3
"""Check post_message return value."""

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
        log.write("Mounted")
        self.worker_test()

    @work
    async def worker_test(self):
        # Check return value of post_message
        result = self.post_message(TestMsg("hello"))
        print(f"post_message returned: {result}")
        print(f"Message queued: {result is True}")

    def on_test_msg(self, msg):
        print(f"Handler called with: {msg.text}")
        log = self.query_one("#log", RichLog)
        log.write(f"Handler: {msg.text}")


async def test():
    app = TestApp()
    async with app.run_test() as pilot:
        await asyncio.sleep(1)
        print("Done")


asyncio.run(test())
