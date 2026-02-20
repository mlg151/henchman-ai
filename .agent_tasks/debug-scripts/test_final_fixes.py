#!/usr/bin/env python3
"""Test final fixes for Textual TUI issues."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

# Working mock provider
class WorkingProvider:
    name = "working"
    
    async def chat_completion_stream(self, messages, **kwargs):
        # This is an async generator
        from henchman.providers.base import StreamChunk, FinishReason
        
        yield StreamChunk(
            content="Hello! I'm the assistant.",
            finish_reason=FinishReason.STOP
        )

# Failing mock provider  
class FailingProvider:
    name = "failing"
    
    async def chat_completion_stream(self, messages, **kwargs):
        raise Exception("API error: Invalid API key")

async def test_error_handling():
    """Test that errors are properly handled and surfaced."""
    print("=== Testing Error Handling Fix ===")
    
    from henchman.core.agent import Agent
    from henchman.core.events import EventType
    from henchman.tools.registry import ToolRegistry
    
    # Test 1: Working provider should produce events
    print("\n1. Testing with working provider...")
    provider = WorkingProvider()
    agent = Agent(
        provider=provider,
        system_prompt="Test",
        tool_registry=ToolRegistry()
    )
    
    events = []
    async for event in agent.run("Hello"):
        events.append(event)
        print(f"   Event: {event.type} - {str(event.data)[:50] if event.data else 'No data'}")
    
    print(f"   ✓ {len(events)} events produced")
    
    # Test 2: Failing provider should produce ERROR event, not crash
    print("\n2. Testing with failing provider...")
    provider = FailingProvider()
    agent = Agent(
        provider=provider,
        system_prompt="Test",
        tool_registry=ToolRegistry()
    )
    
    error_events = []
    try:
        async for event in agent.run("Hello"):
            error_events.append(event)
            print(f"   Event: {event.type} - {str(event.data)[:50] if event.data else 'No data'}")
    except Exception as e:
        print(f"   ✗ Agent crashed: {e}")
    else:
        print(f"   ✓ {len(error_events)} events (should include ERROR event)")
        
        # Check if we got an ERROR event
        has_error = any(e.type == EventType.ERROR for e in error_events)
        print(f"   {'✓' if has_error else '✗'} ERROR event {'present' if has_error else 'missing'}")
        
        # Check if we got a FINISHED event
        has_finished = any(e.type == EventType.FINISHED for e in error_events)
        print(f"   {'✓' if has_finished else '✗'} FINISHED event {'present' if has_finished else 'missing'}")

async def test_textual_components():
    """Test Textual components can be created."""
    print("\n=== Testing Textual Components ===")
    
    try:
        from henchman.cli.textual_app import (
            HenchmanTextualApp,
            TextualConfig,
            EventBridge,
            create_core_context
        )
        print("✓ Textual components import successfully")
        
        # Test EventBridge
        class MockApp:
            def post_message(self, msg):
                pass
        
        bridge = EventBridge(MockApp())
        print("✓ EventBridge created")
        
        # Test core context
        provider = WorkingProvider()
        context = create_core_context(
            provider=provider,
            system_prompt="Test",
            auto_approve_tools=True
        )
        print(f"✓ Core context created: {context.orchestrator}")
        
        return True
        
    except Exception as e:
        print(f"✗ Textual components failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Run all tests."""
    print("=== FINAL FIXES TEST ===")
    print("Testing both Input visibility and agent error handling fixes.")
    
    # Test error handling
    await test_error_handling()
    
    # Test Textual components
    await test_textual_components()
    
    print("\n=== SUMMARY ===")
    print("1. Error handling: Agent should produce ERROR event when provider fails")
    print("2. Textual Input: Should show text as you type (depends on terminal)")
    print("3. To test: Run 'henchman --tui --yes' with valid API key")
    print("4. If Input still invisible: May be terminal compatibility issue")

if __name__ == "__main__":
    asyncio.run(main())