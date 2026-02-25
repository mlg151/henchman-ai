#!/usr/bin/env python3
"""Run Textual app programmatically to test debug output."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

async def main():
    """Run a minimal Textual test."""
    from henchman.cli.textual_app import HenchmanTextualApp, TextualConfig
    from henchman.providers.base import FinishReason, StreamChunk

    # Mock provider that returns error
    class MockProvider:
        name = "mock"

        async def chat_completion_stream(self, messages, **kwargs):
            print("DEBUG MockProvider: Yielding error chunk")
            yield StreamChunk(
                content="❌ Provider Error: API key invalid for testing",
                finish_reason=FinishReason.STOP
            )

    print("=== Starting Textual Test ===")
    print("All 'DEBUG' prints should appear below...")

    # Create provider and config
    provider = MockProvider()
    config = TextualConfig(
        system_prompt="Test",
        auto_approve_tools=True,
        prompt="TEST> "
    )

    # Create app but don't run it fully
    app = HenchmanTextualApp(
        provider=provider,
        config=config,
        settings=None,
        environment_context=None
    )

    print("App created successfully")
    print("Test complete - if you see DEBUG prints above, handlers are working")

if __name__ == "__main__":
    asyncio.run(main())
