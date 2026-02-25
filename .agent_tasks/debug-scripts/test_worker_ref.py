#!/usr/bin/env python3
"""Test if query_one works from worker."""

import asyncio

from textual import work
from textual.app import App, ComposeResult
from textual.widgets import RichLog


class TestApp(App):
    def compose(self) -> ComposeResult:
        yield RichLog(id="log")

    def on_mount(self):
        # Store reference during mount
        self.log = self.query_one("#log", RichLog)
        print(f"Stored log reference: {self.log}")

        # Direct write works
        self.log.write("1. Direct from on_mount")

        # Start worker
        self.worker_test()

    @work
    async def worker_test(self):
        print(f"Worker: self.log = {self.log}")

        # Try using stored reference
        try:
            self.log.write("2. From worker using stored ref")
        except Exception as e:
            print(f"Worker: Error writing: {e}")

        # Try query_one again
        try:
            log2 = self.query_one("#log", RichLog)
            log2.write("3. From worker using query_one")
        except Exception as e:
            print(f"Worker: query_one error: {e}")


async def test():
    app = TestApp()
    async with app.run_test() as pilot:
        await asyncio.sleep(0.5)
        print("Check output above")


asyncio.run(test())
