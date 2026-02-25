#!/usr/bin/env python3
"""Test provider error handling and see what happens."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

async def test_provider_with_dummy_key():
    """Test what happens with dummy API key."""
    from henchman.providers.base import Message
    from henchman.providers.openai_compat import OpenAICompatibleProvider

    print("=== Testing Provider with Dummy API Key ===")

    # Create provider with dummy key
    provider = OpenAICompatibleProvider(
        api_key="dummy-key-that-will-fail",
        base_url="https://api.deepseek.com",
        default_model="deepseek-chat"
    )

    # Create simple messages
    messages = [
        Message(role="user", content="Hello, test!")
    ]

    print("Calling chat_completion_stream...")
    try:
        event_count = 0
        async for chunk in provider.chat_completion_stream(messages):
            event_count += 1
            print(f"Chunk {event_count}:")
            print(f"  Content: {chunk.content}")
            print(f"  Finish reason: {chunk.finish_reason}")
            print(f"  Thinking: {chunk.thinking}")
            print(f"  Tool calls: {chunk.tool_calls}")

        if event_count == 0:
            print("⚠️ No chunks returned!")
        else:
            print(f"✓ {event_count} chunks returned")

    except Exception as e:
        print(f"✗ Exception raised (should be caught internally): {e}")
        import traceback
        traceback.print_exc()

async def test_agent_with_mock():
    """Test with a mock provider that works."""
    print("\n=== Testing with Mock Provider ===")

    from henchman.providers.base import FinishReason, StreamChunk

    class MockProvider:
        name = "mock"

        async def chat_completion_stream(self, messages, **kwargs):
            print("MockProvider: Yielding response")
            yield StreamChunk(
                content="Hello from mock provider!",
                finish_reason=FinishReason.STOP
            )

    from henchman.core.agent import Agent
    from henchman.tools.registry import ToolRegistry

    provider = MockProvider()
    agent = Agent(
        provider=provider,
        system_prompt="Test",
        tool_registry=ToolRegistry()
    )

    print("Running agent...")
    event_count = 0
    async for event in agent.run("Hello"):
        event_count += 1
        print(f"Event {event_count}: {event.type} - {event.data}")

    print(f"✓ Agent produced {event_count} events")

async def main():
    """Run tests."""
    await test_provider_with_dummy_key()
    await test_agent_with_mock()

    print("\n=== What to Expect ===")
    print("1. With dummy key: Should yield ERROR chunk with message")
    print("2. With mock provider: Should get CONTENT and FINISHED events")
    print("3. In Textual TUI: Error should appear in chat pane")

if __name__ == "__main__":
    asyncio.run(main())
