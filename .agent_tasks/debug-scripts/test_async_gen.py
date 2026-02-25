#!/usr/bin/env python3
"""Test with proper async generator mock."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from henchman.cli.textual_app import EventBridge
from henchman.core.events import AgentEvent, EventType


async def test_async_generator():
    """Test with proper async generator."""
    print("=== Testing with Async Generator ===\n")

    # Create mock widgets
    class MockChatPane:
        def __init__(self):
            self.writes = []
        def write(self, content):
            self.writes.append(content)
            print(f"  ChatPane.write: {content[:50]}...")
        def scroll_end(self, animate=False):
            pass

    class MockApp:
        def __init__(self):
            self.chat = MockChatPane()
            self._streaming_buffer = {}

        def query_one(self, query, widget_type=None):
            if query == "#chat-pane":
                return self.chat
            return None

        def post_message(self, msg):
            print(f"  App.post_message: {type(msg).__name__}")

    app = MockApp()
    bridge = EventBridge(app)

    # Proper async generator like orchestrator.run()
    async def mock_orchestrator_stream():
        print("  Stream: yielding AGENT_STARTED")
        yield AgentEvent(type=EventType.AGENT_STARTED, data={"agent": "tech_lead"}, source_agent="orchestrator")

        print("  Stream: yielding CONTENT 'Hello '")
        yield AgentEvent(type=EventType.CONTENT, data="Hello ", source_agent="tech_lead")

        print("  Stream: yielding CONTENT 'world!'")
        yield AgentEvent(type=EventType.CONTENT, data="world!", source_agent="tech_lead")

        print("  Stream: yielding FINISHED")
        yield AgentEvent(type=EventType.FINISHED, source_agent="tech_lead")

        print("  Stream: done")

    # Call the stream
    stream = mock_orchestrator_stream()
    print("Created stream (nothing printed yet)")

    print("\n--- Now iterating with forward_events ---\n")
    await bridge.forward_events(stream)

    print("\n=== Results ===")
    print(f"ChatPane writes: {len(app.chat.writes)}")


if __name__ == "__main__":
    asyncio.run(test_async_generator())
