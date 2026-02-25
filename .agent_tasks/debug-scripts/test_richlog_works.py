#!/usr/bin/env python3
"""Check if RichLog works at all."""

import asyncio

from textual.app import App, ComposeResult
from textual.widgets import RichLog


class TestApp(App):
    def compose(self) -> ComposeResult:
        yield RichLog(id="log")

    def on_mount(self):
        print("on_mount called")
        log = self.query_one("#log", RichLog)
        print(f"Got log widget: {log}")

        result = log.write("Hello from on_mount")
        print(f"write() returned: {result}")


async def test():
    print("Creating app...")
    app = TestApp()
    print("Running test...")
    async with app.run_test() as pilot:
        print("Waiting...")
        await pilot.pause()
        print("Done")


asyncio.run(test())
print("Script completed")
