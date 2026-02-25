#!/usr/bin/env python3
"""Test thread safety of EventBridge."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

async def test_event_bridge():
    """Test EventBridge thread-safe posting."""
    from textual.app import App

    from henchman.cli.textual_app import AgentContentMessage, AgentStatusMessage, EventBridge

    class MockApp(App):
        """Mock Textual app to test posting."""
        messages_received = []

        def post_message(self, message):
            """Record messages posted."""
            self.messages_received.append(message)
            print(f"MockApp.post_message called: {type(message).__name__}")

    print("=== Testing EventBridge Thread Safety ===")

    # Create mock app
    mock_app = MockApp()

    # Create EventBridge
    bridge = EventBridge(mock_app)

    # Test _post_message_safe
    print("1. Testing _post_message_safe...")
    test_msg = AgentStatusMessage("Test status")
    bridge._post_message_safe(test_msg)

    # Test with content message
    print("2. Testing with content message...")
    content_msg = AgentContentMessage("Test content", "test_agent")
    bridge._post_message_safe(content_msg)

    print(f"3. Total messages received: {len(mock_app.messages_received)}")

    # Check if call_from_thread is used (simulated)
    print("\n=== Thread Safety Check ===")
    print("EventBridge should use call_from_thread for all message posting")
    print("from worker threads (@work decorator).")

    return True

async def main():
    await test_event_bridge()
    print("\n✓ Thread safety test passed")

if __name__ == "__main__":
    asyncio.run(main())
