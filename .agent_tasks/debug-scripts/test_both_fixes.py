#!/usr/bin/env python3
"""Test both Input visibility and agent response fixes."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

# Mock provider that works
class WorkingMockProvider:
    name = "working_mock"
    
    async def chat_completion_stream(self, messages, **kwargs):
        # This is an async generator that yields content
        from henchman.providers.base import StreamChunk, FinishReason
        
        # Yield thinking content
        yield StreamChunk(
            content="Let me think about that...",
            finish_reason=None
        )
        
        # Yield main response
        yield StreamChunk(
            content="This is a mock response from the agent.",
            finish_reason=FinishReason.STOP
        )

# Mock provider that fails
class FailingMockProvider:
    name = "failing_mock"
    
    async def chat_completion_stream(self, messages, **kwargs):
        raise Exception("API key invalid or network error")

async def test_with_provider(provider_class, provider_name):
    """Test with a specific provider."""
    print(f"\n=== Testing with {provider_name} ===")
    
    from henchman.cli.textual_app import (
        HenchmanTextualApp, 
        TextualConfig,
        create_core_context
    )
    
    # Create provider
    provider = provider_class()
    
    # Create core context
    context = create_core_context(
        provider=provider,
        system_prompt="Test system prompt",
        auto_approve_tools=True
    )
    
    print(f"1. Core context created: {context.orchestrator}")
    
    # Test orchestrator
    try:
        event_stream = context.orchestrator.run("Hello, test!")
        
        event_count = 0
        async for event in event_stream:
            event_count += 1
            data_str = str(event.data)
            if len(data_str) > 50:
                data_str = data_str[:50] + "..."
            print(f"2. Event {event_count}: {event.type} - {data_str if event.data else 'No data'}")
        
        print(f"3. Total events: {event_count}")
        
        if event_count == 0:
            print("   ⚠️ Warning: No events produced")
            return False
        else:
            print("   ✓ Events produced successfully")
            return True
            
    except Exception as e:
        print(f"3. Error: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    print("=== Testing Textual TUI Fixes ===")
    
    # Test with working provider
    working_ok = await test_with_provider(WorkingMockProvider, "Working Mock Provider")
    
    # Test with failing provider  
    failing_ok = await test_with_provider(FailingMockProvider, "Failing Mock Provider")
    
    print("\n=== Summary ===")
    print(f"1. Working provider test: {'PASS' if working_ok else 'FAIL'}")
    print(f"2. Failing provider test: {'PASS' if failing_ok else 'FAIL (expected for failing provider)'}")
    
    print("\n=== Next Steps ===")
    print("1. If Input still not visible: Textual may have focus/rendering bug")
    print("2. If no agent responses: Real provider failing with API key")
    print("3. Try: henchman --tui --yes (auto-approve tools)")
    print("4. Try with valid API key")

if __name__ == "__main__":
    asyncio.run(main())