#!/usr/bin/env python3
"""Debug script for Textual TUI issues."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from henchman.cli.textual_app import create_core_context


async def test_core_context():
    """Test core context creation."""
    print("Testing core context creation...")

    # Create a mock provider for testing
    class MockProvider:
        name = "mock"

        async def chat_completion_stream(self, *args, **kwargs):
            async def mock_stream():
                yield None
            return mock_stream()

    provider = MockProvider()

    try:
        context = create_core_context(
            provider=provider,
            system_prompt="Test prompt",
            auto_approve_tools=False
        )
        print("✓ Core context created successfully")
        print(f"  - Orchestrator: {context.orchestrator}")
        print(f"  - Agent: {context.agent}")
        print(f"  - Tool registry: {context.tool_registry}")
        return True
    except Exception as e:
        print(f"✗ Failed to create core context: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_orchestrator_run():
    """Test orchestrator.run() method."""
    print("\nTesting orchestrator.run()...")

    class MockProvider:
        name = "mock"

        async def chat_completion_stream(self, messages, **kwargs):
            # Return a mock response
            from henchman.providers.base import FinishReason, StreamChunk

            async def mock_stream():
                yield StreamChunk(
                    content="Test response",
                    finish_reason=FinishReason.STOP
                )

            return mock_stream()

    provider = MockProvider()

    try:
        context = create_core_context(
            provider=provider,
            system_prompt="Test prompt",
            auto_approve_tools=True  # Auto-approve to avoid tool confirmations
        )

        # Run orchestrator
        event_stream = context.orchestrator.run("Hello, world!")

        event_count = 0
        async for event in event_stream:
            event_count += 1
            data_str = str(event.data)
            if len(data_str) > 50:
                data_str = data_str[:50] + "..."
            print(f"  Event {event_count}: {event.type} - {data_str if event.data else 'No data'}")

        print(f"✓ Orchestrator produced {event_count} events")
        return True

    except Exception as e:
        print(f"✗ Orchestrator.run() failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_input_widget():
    """Test Textual Input widget separately."""
    print("\nTesting Textual Input widget...")

    from textual.app import App
    from textual.widgets import Input

    class TestApp(App):
        CSS = """
        #input {
            width: 1fr;
        }
        """

        def compose(self):
            yield Input(id="input", placeholder="Type here...")

        def on_mount(self):
            self.query_one("#input", Input).focus()

    print("✓ Input widget should show typed text in real-time")
    print("  If not, there may be a CSS or focus issue")
    return True

if __name__ == "__main__":
    print("=== Textual TUI Debug Tests ===")

    # Test 1: Core context
    asyncio.run(test_core_context())

    # Test 2: Orchestrator
    asyncio.run(test_orchestrator_run())

    # Test 3: Input widget
    test_input_widget()

    print("\n=== Debug Summary ===")
    print("1. If typing isn't visible: CSS/focus issue with Input widget")
    print("2. If no agent responses: Check orchestrator.run() and EventBridge")
    print("3. Try with real API key to test full flow")
