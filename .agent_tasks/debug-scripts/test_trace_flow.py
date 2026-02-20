#!/usr/bin/env python3
"""Trace what happens when user submits input in Textual TUI."""

import asyncio
import sys
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

sys.path.insert(0, str(Path(__file__).parent / "src"))

from henchman.cli.textual_app import (
    HenchmanTextualApp,
    TextualConfig,
    EventBridge,
    AgentContentMessage,
)
from henchman.core.events import AgentEvent, EventType


async def trace_full_flow():
    """Trace the complete flow from user input to output."""
    print("=== Tracing Full Textual TUI Flow ===\n")
    
    # Step 1: Create mock provider that returns content
    class MockProvider:
        name = "mock"
        
        async def chat_completion_stream(self, messages, **kwargs):
            yield None  # Empty message to start
            yield None
    
    provider = MockProvider()
    
    # Step 2: Create app (but don't run it)
    config = TextualConfig(auto_approve_tools=True)
    
    # Create app without running it
    app = HenchmanTextualApp(provider=provider, config=config, settings=None)
    
    # Step 3: Simulate on_mount initialization
    print("1. Simulating on_mount...")
    
    # Mock the query_one to return mock widgets
    mock_chat_pane = MagicMock()
    mock_status_bar = MagicMock()
    mock_thinking_pane = MagicMock()
    mock_tool_pane = MagicMock()
    
    def mock_query_one(query, widget_type=None):
        print(f"   query_one('{query}', {widget_type})")
        if query == "#chat-pane":
            return mock_chat_pane
        elif query == "#status-bar":
            return mock_status_bar
        elif query == "#thinking-pane":
            return mock_thinking_pane
        elif query == "#tool-pane":
            return mock_tool_pane
        elif query == "#input":
            mock_input = MagicMock()
            mock_input.text = "Hello"
            mock_input.cursor_location = (0, 0)
            return mock_input
        return MagicMock()
    
    app.query_one = mock_query_one
    
    # Mock the core components
    mock_orchestrator = MagicMock()
    mock_session_manager = MagicMock()
    
    # Create a real event stream
    async def real_event_stream():
        yield AgentEvent(type=EventType.AGENT_STARTED, data={"agent": "tech_lead"}, source_agent="orchestrator")
        yield AgentEvent(type=EventType.CONTENT, data="Hello ", source_agent="tech_lead")
        yield AgentEvent(type=EventType.CONTENT, data="world!", source_agent="tech_lead")
        yield AgentEvent(type=EventType.FINISHED, data="done", source_agent="tech_lead")
    
    mock_orchestrator.run = MagicMock(return_value=real_event_stream())
    
    app.core_context = MagicMock()
    app.core_context.orchestrator = mock_orchestrator
    app.core_context.session_manager = mock_session_manager
    
    # Mock input_handler
    app.input_handler = MagicMock()
    app.input_handler.process_input = AsyncMock(return_value=("Hello", False, True))
    app.input_handler.history_file = None
    
    # Step 4: Simulate what happens in process_user_input
    print("\n2. Simulating process_user_input...")
    
    # Create event bridge with our app
    event_bridge = EventBridge(app)
    
    # Simulate the worker running
    print("\n3. Running event_bridge.forward_events...")
    
    # This should forward all events
    await event_bridge.forward_events(real_event_stream())
    
    # Check what was written
    print("\n4. Checking what was written to RichLog...")
    print(f"   chat_pane.write calls: {mock_chat_pane.write.call_count}")
    for call in mock_chat_pane.write.call_args_list:
        print(f"   - write({call})")
    
    print("\n5. Checking status_bar updates...")
    print(f"   status_bar.status_text updates: {mock_status_bar.update.call_count}")
    for call in mock_status_bar.update.call_args_list:
        print(f"   - update({call})")
    
    print("\n=== Flow trace complete ===")
    print("If write was called with the content, the issue is elsewhere.")
    print("If write was NOT called, the message handlers aren't working.")


if __name__ == "__main__":
    asyncio.run(trace_full_flow())
