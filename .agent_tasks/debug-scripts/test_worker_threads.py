#!/usr/bin/env python3
"""Debug worker execution."""

import asyncio
from textual.app import App, ComposeResult
from textual.widgets import RichLog
from textual.message import Message
from textual import work
import threading


class TestMsg(Message):
    def __init__(self, text):
        super().__init__()
        self.text = text


class TestApp(App):
    def compose(self) -> ComposeResult:
        yield RichLog(id="log")
    
    def on_mount(self):
        log = self.query_one("#log", RichLog)
        log.write(f"on_mount thread: {threading.current_thread().name}")
        self.worker_test()
    
    @work
    async def worker_test(self):
        print(f"WORKER RUNNING on thread: {threading.current_thread().name}")
        print(f"Is main thread: {threading.current_thread() == threading.main_thread()}")
        self.post_message(TestMsg("message from worker"))
        print("post_message called")
    
    def on_test_msg(self, msg):
        log = self.query_one("#log", RichLog)
        log.write(f"Handler thread: {threading.current_thread().name}")
        log.write(f"Handler got: {msg.text}")


async def test():
    app = TestApp()
    async with app.run_test() as pilot:
        print("Waiting for worker...")
        await asyncio.sleep(2)
        print("Done waiting")


asyncio.run(test())
