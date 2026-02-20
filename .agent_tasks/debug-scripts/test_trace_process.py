#!/usr/bin/env python3
"""Add debug output to trace process_user_input."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from henchman.cli.textual_app import (
    HenchmanTextualApp,
    TextualConfig,
    EventBridge,
)
from henchman.core.events import AgentEvent, EventType


class MockProvider:
    name = "mock"
    
    async def chat_completion_stream(self, messages, **kwargs):
        yield None
        yield None


async def test_process_user_input():
    """Simulate process_user_input with debug."""
    print("=== Testing process_user_input ===\n")
    
    # Create app
    provider = MockProvider()
    config = TextualConfig(auto_approve_tools=True)
    app = HenchmanTextualApp(provider=provider, config=config, settings=None)
    
    # Create mock orchestrator that yields events
    async def mock_orchestrator_stream():
        print("Orchestrator stream: yielding events...")
        yield AgentEvent(type=EventType.CONTENT, data="Hello ", source_agent="tech_lead")
        yield AgentEvent(type=EventType.CONTENT, data="world!", source_agent="tech_lead")
        yield AgentEvent(type=EventType.FINISHED, source_agent="tech_lead")
        print("Orchestrator stream: done")
    
    # Set up mock core_context
    class MockOrchestrator:
        def run(self, input_text):
            print(f"Orchestrator.run called with: {input_text}")
            return mock_orchestrator_stream()
    
    class MockSessionManager:
        def record_user_message(self, msg):
            print(f"Session manager recorded: {msg}")
    
    app.core_context = type('obj', (object,), {
        'orchestrator': MockOrchestrator(),
        'session_manager': MockSessionManager(),
    })()
    
    # Mock input_handler
    class MockInputHandler:
        async def process_input(self, user_input):
            print(f"Input handler processed: {user_input}")
            return user_input, False, True  # processed_input, is_command, should_continue
        
        history_file = None
    
    app.input_handler = MockInputHandler()
    
    # Mock query_one to return mock widgets
    class MockChatPane:
        def __init__(self):
            self.writes = []
        def write(self, content):
            self.writes.append(content)
            print(f"  ChatPane.write: {content}")
        def scroll_end(self, animate=False):
            pass
    
    class MockStatusBar:
        def __init__(self):
            self.status_text = "Ready"
        def update(self, text):
            self.status_text = text
            print(f"  StatusBar.update: {text}")
    
    mock_chat = MockChatPane()
    mock_status = MockStatusBar()
    
    def mock_query_one(query, widget_type=None):
        print(f"  query_one('{query}')")
        if query == "#chat-pane":
            return mock_chat
        elif query == "#status-bar":
            return mock_status
        elif query == "#input":
            mock_input = type('obj', (object,), {'text': 'Hello world', 'cursor_location': (0,0)})()
            return mock_input
        raise Exception(f"Unknown query: {query}")
    
    app.query_one = mock_query_one
    
    # Now simulate running process_user_input
    print("\n--- Running process_user_input('Hello world') ---\n")
    
    event_bridge = EventBridge(app)
    
    print("Calling orchestrator.run()...")
    event_stream = app.core_context.orchestrator.run("Hello world")
    
    print("Calling event_bridge.forward_events()...")
    await event_bridge.forward_events(event_stream)
    
    print("\n=== Results ===")
    print(f"ChatPane writes: {len(mock_chat.writes)}")
    for w in mock_chat.writes:
        print(f"  - {w}")
    
    print(f"\nStatusBar updates: {mock_status.status_text}")


if __name__ == "__main__":
    asyncio.run(test_process_user_input())
