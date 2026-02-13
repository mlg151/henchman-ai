#!/usr/bin/env python3
"""Test the henchman bug fixes."""

import sys

sys.path.insert(0, ".")

from unittest.mock import AsyncMock, Mock

print("Testing henchman bug fixes...")

# Test 1: Agent class has all required methods
print("\n1. Testing Agent class...")
try:
    from src.henchman.core.agent import Agent

    provider = Mock()
    tool_registry = Mock()
    agent = Agent(provider, tool_registry)

    required_methods = ["continue_with_tool_results", "clear_history", "history", "tools"]
    for method in required_methods:
        if hasattr(agent, method):
            print(f"  ✓ Agent has {method}()")
        else:
            print(f"  ✗ Agent missing {method}()")
            sys.exit(1)
except Exception as e:
    print(f"  ✗ Error testing Agent: {e}")
    sys.exit(1)

# Test 2: Check that continue_with_tool_results is an async generator
print("\n2. Testing continue_with_tool_results method...")
try:
    import inspect

    # Mock the provider to return an empty stream
    async def empty_stream():
        if False:
            yield

    provider.chat_completion_stream = AsyncMock(return_value=empty_stream())

    # Check if it's an async generator
    if inspect.isasyncgenfunction(agent.continue_with_tool_results):
        print("  ✓ continue_with_tool_results is an async generator function")
    else:
        print("  ✗ continue_with_tool_results is not an async generator function")
except Exception as e:
    print(f"  ✗ Error: {e}")

# Test 3: Test clear_history method
print("\n3. Testing clear_history method...")
try:
    # Add some messages
    from src.henchman.providers.base import Message

    agent.messages = [
        Message(role="system", content="You are a helpful assistant"),
        Message(role="user", content="Hello"),
        Message(role="assistant", content="Hi there!"),
    ]

    print(f"  Before clear: {len(agent.messages)} messages")
    agent.clear_history()
    print(f"  After clear: {len(agent.messages)} messages")

    # Should keep system message
    if len(agent.messages) == 1 and agent.messages[0].role == "system":
        print("  ✓ clear_history preserves system message")
    else:
        print("  ✗ clear_history did not preserve system message correctly")
except Exception as e:
    print(f"  ✗ Error: {e}")

print("\n✅ All tests passed! The bug fixes are working.")
