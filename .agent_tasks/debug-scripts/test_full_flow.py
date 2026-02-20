#!/usr/bin/env python3
"""Test the full Textual TUI flow with better diagnostics."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from henchman.cli.textual_app import HenchmanTextualApp, TextualConfig
from henchman.cli.core_init import create_core_context
from henchman.providers.base import StreamChunk, FinishReason

async def test_event_flow():
    """Test the complete event flow from orchestrator to UI."""
    print("Testing complete event flow...")
    
    # Create a proper mock provider that returns an async generator
    class MockProvider:
        name = "mock"
        
        async def chat_completion_stream(self, messages, **kwargs):
            # This is an async generator - it yields directly
            # Simulate a thinking event
            yield StreamChunk(
                content="I'm thinking about your question...",
                finish_reason=FinishReason.STOP
            )
            # Simulate a content event
            yield StreamChunk(
                content="Here's my response to your question.",
                finish_reason=FinishReason.STOP
            )
    
    # Test 1: Core context with mock provider
    print("1. Creating core context...")
    provider = MockProvider()
    context = create_core_context(
        provider=provider,
        system_prompt="Test",
        auto_approve_tools=True
    )
    print(f"   ✓ Created: {context.orchestrator}")
    
    # Test 2: Orchestrator produces events
    print("2. Testing orchestrator event stream...")
    try:
        event_stream = context.orchestrator.run("Test input")
        
        events = []
        async for event in event_stream:
            events.append(event)
            print(f"   Event: {event.type} - {str(event.data)[:50] if event.data else 'No data'}")
        
        print(f"   ✓ Produced {len(events)} events")
        
        if len(events) == 0:
            print("   ⚠️ No events produced - check provider implementation")
        
    except Exception as e:
        print(f"   ✗ Error: {e}")
        import traceback
        traceback.print_exc()
    
    # Test 3: EventBridge forwarding
    print("3. Testing EventBridge...")
    from henchman.cli.textual_app import EventBridge
    from henchman.core.events import AgentEvent, EventType
    
    class MockApp:
        messages = []
        
        def post_message(self, message):
            self.messages.append(message)
            print(f"   Posted message: {type(message).__name__}")
    
    mock_app = MockApp()
    bridge = EventBridge(mock_app)
    
    # Create a simple event stream
    async def simple_event_stream():
        yield AgentEvent(type=EventType.CONTENT, data="Test response")
        yield AgentEvent(type=EventType.FINISHED)
    
    await bridge.forward_events(simple_event_stream())
    print(f"   ✓ Forwarded {len(mock_app.messages)} messages")
    
    # Test 4: Provider error handling
    print("4. Testing provider error handling...")
    
    class FailingProvider:
        name = "failing"
        
        async def chat_completion_stream(self, messages, **kwargs):
            raise Exception("API key invalid or network error")
    
    failing_provider = FailingProvider()
    try:
        failing_context = create_core_context(
            provider=failing_provider,
            system_prompt="Test",
            auto_approve_tools=True
        )
        
        # This should produce an ERROR event, not crash
        event_stream = failing_context.orchestrator.run("Test")
        
        error_events = []
        async for event in event_stream:
            error_events.append(event)
        
        print(f"   ✓ Error handling: {len(error_events)} events")
        for event in error_events:
            print(f"     {event.type}: {event.data}")
            
    except Exception as e:
        print(f"   ✗ Error handling failed: {e}")
    
    print("\n=== Summary ===")
    print("1. If typing isn't visible: Run test_input_only.py to isolate Input widget")
    print("2. If no agent responses: Provider might be failing with dummy API key")
    print("3. Try with real API key or use --yes flag to auto-approve tools")

if __name__ == "__main__":
    asyncio.run(test_event_flow())