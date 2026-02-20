#!/usr/bin/env python3
"""Test query_one from worker - fixed."""

import asyncio
from textual.app import App, ComposeResult
from textual.widgets import RichLog
from textual import work


class TestApp(App):
    def compose(self) -> ComposeResult:
        yield RichLog(id="mylog")
    
    def on_mount(self):
        # Direct write
        log = self.query_one("#mylog", RichLog)
        log.write("1. Direct from on_mount")
        
        # Start worker
        self.worker_test()
    
    @work
    async def worker_test(self):
        # Try query_one in worker
        try:
            log = self.query_one("#mylog", RichLog)
            log.write("2. From worker via query_one")
        except Exception as e:
            print(f"Worker query_one error: {e}")


async def test():
    app = TestApp()
    async with app.run_test() as pilot:
        await asyncio.sleep(0.5)
        print("If bug exists, only '1. Direct from on_mount' appears")

asyncio.run(test())
