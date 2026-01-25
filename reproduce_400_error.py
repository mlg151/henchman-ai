#!/usr/bin/env python3
"""Reproduce the 400 error with tool call sequencing."""

import asyncio
import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from src.henchman.providers.base import Message, ToolCall, ToolDeclaration, FinishReason, StreamChunk
from src.henchman.core.agent import Agent
from src.henchman.core.events import EventType

class MockProvider:
    """Mock provider to simulate the 400 error scenario."""
    
    @property
    def name(self) -> str:
        return "mock"
    
    async def chat_completion_stream(self, messages, tools=None, **kwargs):
        """Simulate different error scenarios based on message history."""
        
        print(f"\n=== Mock Provider Called ===")
        print(f"Number of messages: {len(messages)}")
        for i, msg in enumerate(messages):
            print(f"  Message {i}: role={msg.role}, content='{msg.content or ''}', "
                  f"tool_calls={msg.tool_calls is not None}, tool_call_id={msg.tool_call_id}")
        
        # Scenario 1: Tool message without preceding tool call
        if len(messages) >= 2 and messages[-1].role == "tool":
            print("\n  ERROR SCENARIO: Tool message without proper preceding tool call")
            # Check if previous message has tool calls
            prev_msg = messages[-2]
            if prev_msg.role != "assistant" or not prev_msg.tool_calls:
                print("  -> This would cause: 'Messages with role tool must be a response to a preceding message with tool_calls'")
            
            # Check if tool_call_id matches
            if prev_msg.tool_calls:
                tool_call_ids = [tc.id for tc in prev_msg.tool_calls]
                if messages[-1].tool_call_id not in tool_call_ids:
                    print(f"  -> Tool call ID mismatch: {messages[-1].tool_call_id} not in {tool_call_ids}")
        
        # Always return a simple response
        yield StreamChunk(content="Test response", finish_reason=FinishReason.STOP)

async def test_scenario_1():
    """Test scenario: Tool message without preceding tool call."""
    print("\n=== Scenario 1: Tool message without preceding tool call ===")
    
    provider = MockProvider()
    agent = Agent(provider=provider)
    
    # Manually create invalid history
    agent.history = [
        Message(role="user", content="Hello"),
        Message(role="tool", content="result", tool_call_id="call_123")  # Invalid: no preceding tool call
    ]
    
    print("\nAgent history (invalid):")
    for i, msg in enumerate(agent.history):
        print(f"  {i}: role={msg.role}, tool_call_id={msg.tool_call_id}")
    
    # Try to continue - this might trigger the error
    print("\nTrying to continue with invalid history...")
    try:
        async for event in agent.continue_with_tool_results():
            print(f"  Event: {event.type}")
    except Exception as e:
        print(f"  Exception: {e}")

async def test_scenario_2():
    """Test scenario: Mismatched tool call ID."""
    print("\n\n=== Scenario 2: Mismatched tool call ID ===")
    
    provider = MockProvider()
    agent = Agent(provider=provider)
    
    # Create history with mismatched IDs
    agent.history = [
        Message(role="user", content="List files"),
        Message(
            role="assistant",
            content="",
            tool_calls=[ToolCall(id="call_abc", name="ls", arguments={})]
        ),
        # Tool message with wrong ID
        Message(role="tool", content="files.txt", tool_call_id="call_xyz")  # Wrong ID!
    ]
    
    print("\nAgent history (mismatched IDs):")
    for i, msg in enumerate(agent.history):
        if msg.tool_calls:
            print(f"  {i}: role={msg.role}, tool_call_ids={[tc.id for tc in msg.tool_calls]}")
        else:
            print(f"  {i}: role={msg.role}, tool_call_id={msg.tool_call_id}")
    
    print("\nTrying to continue with mismatched IDs...")
    try:
        async for event in agent.continue_with_tool_results():
            print(f"  Event: {event.type}")
    except Exception as e:
        print(f"  Exception: {e}")

async def test_scenario_3():
    """Test scenario: Valid tool call sequence."""
    print("\n\n=== Scenario 3: Valid tool call sequence ===")
    
    provider = MockProvider()
    agent = Agent(provider=provider)
    
    # Create valid history
    agent.history = [
        Message(role="user", content="List files"),
        Message(
            role="assistant",
            content="",
            tool_calls=[ToolCall(id="call_123", name="ls", arguments={})]
        ),
        # Tool message with correct ID
        Message(role="tool", content="files.txt", tool_call_id="call_123")  # Correct ID
    ]
    
    print("\nAgent history (valid):")
    for i, msg in enumerate(agent.history):
        if msg.tool_calls:
            print(f"  {i}: role={msg.role}, tool_call_ids={[tc.id for tc in msg.tool_calls]}")
        else:
            print(f"  {i}: role={msg.role}, tool_call_id={msg.tool_call_id}")
    
    print("\nTrying to continue with valid history...")
    try:
        async for event in agent.continue_with_tool_results():
            print(f"  Event: {event.type}")
    except Exception as e:
        print(f"  Exception: {e}")

async def test_agent_flow():
    """Test the normal agent flow to see where errors might occur."""
    print("\n\n=== Testing Normal Agent Flow ===")
    
    class FlowProvider:
        @property
        def name(self) -> str:
            return "flow"
        
        async def chat_completion_stream(self, messages, tools=None, **kwargs):
            print(f"\nProvider called with {len(messages)} messages")
            
            # Simulate tool call on first request
            if len(messages) == 1:  # Just user message
                yield StreamChunk(
                    content="",
                    tool_calls=[ToolCall(id="test_1", name="test", arguments={})],
                    finish_reason=FinishReason.TOOL_CALLS
                )
            else:
                # After tool result
                yield StreamChunk(
                    content="Tool executed successfully",
                    finish_reason=FinishReason.STOP
                )
    
    provider = FlowProvider()
    agent = Agent(provider=provider)
    
    print("\nStep 1: User sends message")
    events = []
    async for event in agent.run("Do something"):
        events.append(event.type)
        if event.type == EventType.TOOL_CALL_REQUEST:
            print(f"  Tool call requested: {event.data.name} (id: {event.data.id})")
            # Submit tool result
            agent.submit_tool_result(event.data.id, "Tool result")
    
    print(f"\nEvents in step 1: {events}")
    
    print("\nStep 2: Continue with tool results")
    events = []
    async for event in agent.continue_with_tool_results():
        events.append(event.type)
        print(f"  Event: {event.type}")
    
    print(f"\nEvents in step 2: {events}")
    
    print("\nFinal agent history:")
    for i, msg in enumerate(agent.history):
        print(f"  {i}: role={msg.role}, content_length={len(msg.content or '')}, "
              f"tool_calls={msg.tool_calls is not None}, tool_call_id={msg.tool_call_id}")

async def main():
    print("=== 400 Error Reproduction Tests ===")
    print("Testing various scenarios that might cause the OpenAI API 400 error.")
    
    await test_scenario_1()
    await test_scenario_2()
    await test_scenario_3()
    await test_agent_flow()
    
    print("\n=== Summary ===")
    print("The 400 error occurs when the message sequence violates OpenAI API rules:")
    print("1. Tool messages must follow assistant messages with tool_calls")
    print("2. Tool call IDs must match between assistant and tool messages")
    print("3. The sequence must be: user → assistant(with tool_calls) → tool → assistant")
    print("\nCheck the Agent's history management to ensure proper sequencing.")

if __name__ == "__main__":
    asyncio.run(main())
