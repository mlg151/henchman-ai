#!/usr/bin/env python3
"""Verify message posting from worker."""

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
        log.write("1. Direct")
        self.worker_test()

    @work
    async def worker_test(self):
        self.post_message(TestMsg("2. From worker"))

    def on_test_msg(self, msg):
        log = self.query_one("#log", RichLog)
        log.write(f"Handler: {msg.text}")


async def test():
    app = TestApp()
    async with app.run_test() as pilot:
        await asyncio.sleep(0.5)
        print("If bug: only '1. Direct', handler not triggered")

asyncio.run(test())
