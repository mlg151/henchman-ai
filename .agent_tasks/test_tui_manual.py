import os
import sys

import anyio

from textual.widgets import TextArea, RichLog
from henchman.cli.textual_app import HenchmanTextualApp
from henchman.providers.base import ModelProvider
import traceback

class MockProvider(ModelProvider):
    @property
    def name(self): return "mock"
    
    async def chat_completion_stream(self, *args, **kwargs):
        from henchman.providers.base import StreamChunk
        yield StreamChunk(content="Hello from mock!")

async def test_app():
    try:
        app = HenchmanTextualApp(provider=MockProvider())
        async with app.run_test() as pilot:
            print("App loaded")
            input_widget = app.query_one("#input", TextArea)
            input_widget.text = "Hello textual"
            
            # Submit the message using the action
            print("Submitting message")
            app.action_submit_message()
            
            # Wait for processing
            await pilot.pause(1.0)
            
            chat_pane = app.query_one("#chat-pane", RichLog)
            text = "\n".join([str(line) for line in chat_pane.lines])
            print("Chat output:")
            print(text)
            
            print("Finished run successfully")
    except Exception as e:
        print("Exception caught in test script:")
        traceback.print_exc()

if __name__ == "__main__":
    anyio.run(test_app)
