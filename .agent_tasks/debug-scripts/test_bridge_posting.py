#!/usr/bin/env python3
"""Check if EventBridge posts messages to the app."""

import asyncio
import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent / "src"))

from henchman.cli.textual_app import (
    AgentContentMessage,
    AgentFinishedMessage,
    EventBridge,
)
from henchman.core.events import AgentEvent, EventType


async def check_message_posting():
    """Check if EventBridge actually posts messages."""
    print("=== Checking EventBridge Message Posting ===\n")

    # Create mock app
    mock_app = MagicMock()
    posted_messages = []

    def track_post(message):
        posted_messages.append(message)
        print(f"   post_message called with: {type(message).__name__}")
        if hasattr(message, 'content'):
            print(f"      content: {message.content[:50] if message.content else 'None'}...")

    mock_app.post_message = track_post

    # Create event bridge
    bridge = EventBridge(mock_app)

    # Create event stream
    async def event_stream():
        yield AgentEvent(type=EventType.CONTENT, data="Hello ", source_agent="tech_lead")
        yield AgentEvent(type=EventType.CONTENT, data="world!", source_agent="tech_lead")
        yield AgentEvent(type=EventType.FINISHED, source_agent="tech_lead")

    # Run forward_events
    print("Running bridge.forward_events()...")
    await bridge.forward_events(event_stream())

    print("\n=== Results ===")
    print(f"Total messages posted: {len(posted_messages)}")
    print("Expected: 3 (2 CONTENT + 1 FINISHED)")

    # Check message types
    content_count = sum(1 for m in posted_messages if isinstance(m, AgentContentMessage))
    finished_count = sum(1 for m in posted_messages if isinstance(m, AgentFinishedMessage))

    print(f"\nAgentContentMessage: {content_count}")
    print(f"AgentFinishedMessage: {finished_count}")

    if content_count == 2:
        print("\n✓ EventBridge IS posting messages correctly")
        print("  The issue must be in Textual's message handling")
    else:
        print("\n✗ EventBridge is NOT posting messages!")
        print("  Bug is in EventBridge._post_message_safe()")


if __name__ == "__main__":
    asyncio.run(check_message_posting())
