#!/usr/bin/env python3
"""Add more debug to understand."""

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
        print("=== on_mount start ===")
        log = self.query_one("#log", RichLog)
        print(f"Got log: {log}")
        log.write("1. Direct")
        print("Wrote '1. Direct'")
        self.worker_test()
        print("=== on_mount end ===")
    
    @work
    async def worker_test(self):
        print("=== worker start ===")
        result = self.post_message(TestMsg("2. From worker"))
        print(f"post_message result: {result}")
        print("=== worker end ===")
    
    def on_test_msg(self, msg):
        print(f"=== handler start: {msg.text} ===")
        try:
            log = self.query_one("#log", RichLog)
            print(f"Got log in handler: {log}")
            log.write(f"Handler: {msg.text}")
            print("write() called")
        except Exception as e:
            print(f"Error in handler: {e}")
        print("=== handler end ===")


async def test():
    app = TestApp()
    async with app.run_test() as pilot:
        print("=== test start ===")
        await asyncio.sleep(1)
        print("=== test end ===")


asyncio.run(test())
