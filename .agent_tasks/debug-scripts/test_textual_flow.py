#!/usr/bin/env python3
"""Test the complete Textual TUI flow with all debug enabled."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

async def test_complete_flow():
    """Test from provider → agent → orchestrator → EventBridge → Textual."""
    from henchman.cli.textual_app import EventBridge, AgentContentMessage
    from henchman.core.events import AgentEvent, EventType
    from henchman.providers.base import Message, StreamChunk, FinishReason
    
    print("=== Testing Complete Event Flow ===")
    
    # 1. Mock provider that returns error (like with dummy API key)
    class MockProvider:
        name = "mock"
        
        async def chat_completion_stream(self, messages, **kwargs):
            print("MockProvider: Yielding error chunk")
            yield StreamChunk(
                content="❌ Provider Error: API key invalid",
                finish_reason=FinishReason.STOP
            )
    
    # 2. Create minimal components
    from henchman.cli.core_init import create_core_context
    provider = MockProvider()
    
    print("1. Creating core context...")
    context = create_core_context(
        provider=provider,
        system_prompt="Test",
        auto_approve_tools=True
    )
    
    print("2. Testing orchestrator.run()...")
    event_stream = context.orchestrator.run("Hello")
    
    event_count = 0
    async for event in event_stream:
        event_count += 1
        print(f"   Event {event_count}: {event.type}")
        print(f"     Data: {str(event.data)[:100] if event.data else 'None'}")
        print(f"     Source: {event.source_agent}")
    
    print(f"3. Total events: {event_count}")
    
    # 3. Test EventBridge
    print("\n4. Testing EventBridge...")
    class MockApp:
        messages_received = []
        
        def post_message(self, message):
            self.messages_received.append(message)
            print(f"   App received: {type(message).__name__}")
            if hasattr(message, 'content'):
                print(f"     Content: {message.content[:100]}")
    
    mock_app = MockApp()
    bridge = EventBridge(mock_app)
    
    # Create a test event stream
    async def test_event_stream():
        yield AgentEvent(
            type=EventType.CONTENT,
            data="❌ Provider Error: API key invalid",
            source_agent="tech_lead"
        )
        yield AgentEvent(
            type=EventType.FINISHED,
            source_agent="tech_lead"
        )
    
    await bridge.forward_events(test_event_stream())
    print(f"   App received {len(mock_app.messages_received)} messages")
    
    # Check if AgentContentMessage was posted
    has_content = any(isinstance(m, AgentContentMessage) for m in mock_app.messages_received)
    print(f"   Has AgentContentMessage: {has_content}")
    
    if has_content:
        for msg in mock_app.messages_received:
            if isinstance(msg, AgentContentMessage):
                print(f"   Error message: {msg.content}")
    
    print("\n=== Expected in Textual TUI ===")
    print("With dummy API key, user should see in chat pane:")
    print("  'Assistant: ❌ Provider Error: API key invalid'")
    print("Or possibly: '❌ API Error: Invalid or missing API key...'")

if __name__ == "__main__":
    asyncio.run(test_complete_flow())