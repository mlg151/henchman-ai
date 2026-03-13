"""Refactor plan: Replace Agent | AgentEvent union with exceptions."""

from typing import Protocol, runtime_checkable
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

# Current problematic pattern
class EventType(Enum):
    ERROR = "error"
    AGENT_STARTED = "agent_started"
    AGENT_COMPLETED = "agent_completed"

@dataclass
class AgentEvent:
    type: EventType
    data: str
    source_agent: str

@runtime_checkable
class AgentProtocol(Protocol):
    messages: Sequence[str]  # Simplified for example
    def clear_history(self) -> None: ...

# Current implementation returns union
async def get_agent_with_error_handling_current(target_role: str) -> AgentProtocol | AgentEvent:
    """Current problematic pattern."""
    try:
        # Simulate agent retrieval
        if target_role == "engineer":
            class MockAgent:
                messages = []
                def clear_history(self):
                    pass
            return MockAgent()
        else:
            raise ValueError(f"Agent '{target_role}' not found")
    except Exception as e:
        return AgentEvent(
            type=EventType.ERROR,
            data=f"Failed to get agent '{target_role}': {e}",
            source_agent="orchestrator"
        )

# Refactored implementation with exceptions
class DelegationError(Exception):
    """Base exception for delegation errors."""
    def __init__(self, message: str, agent_role: str):
        super().__init__(message)
        self.agent_role = agent_role
        self.message = message

class AgentNotFoundError(DelegationError):
    """Agent not found in pool."""
    pass

class AgentProtocolError(DelegationError):
    """Agent doesn't conform to required protocol."""
    pass

async def get_agent_with_error_handling_refactored(target_role: str) -> AgentProtocol:
    """Refactored: Raises exceptions instead of returning union."""
    try:
        # Simulate agent retrieval
        if target_role == "engineer":
            class MockAgent:
                messages = []
                def clear_history(self):
                    pass
            agent = MockAgent()
        elif target_role == "broken":
            class BrokenAgent:
                messages = None  # Protocol violation
                def clear_history(self):
                    pass
            agent = BrokenAgent()
        else:
            raise AgentNotFoundError(f"Agent '{target_role}' not found", target_role)
        
        # Validate protocol
        if not isinstance(agent.messages, Sequence):
            raise AgentProtocolError(
                f"Agent '{target_role}' has invalid 'messages' attribute",
                target_role
            )
        
        return agent
    except DelegationError:
        # Re-raise our custom exceptions
        raise
    except Exception as e:
        # Wrap unexpected exceptions
        raise DelegationError(f"Unexpected error: {e}", target_role) from e

# Usage comparison
async def run_delegation_current(target_role: str):
    """Current usage pattern - error-prone type checking."""
    result = await get_agent_with_error_handling_current(target_role)
    
    if isinstance(result, AgentEvent):
        # Must check type - easy to forget
        if result.type == EventType.ERROR:
            yield result
        else:
            yield AgentEvent(
                type=EventType.ERROR,
                data=f"Unexpected event: {result.type}",
                source_agent="orchestrator"
            )
        return
    
    # Now we have an agent
    agent = result
    print(f"Current: Got agent with {len(agent.messages)} messages")

async def run_delegation_refactored(target_role: str):
    """Refactored usage pattern - clean exception handling."""
    try:
        agent = await get_agent_with_error_handling_refactored(target_role)
        print(f"Refactored: Got agent with {len(agent.messages)} messages")
        yield AgentEvent(
            type=EventType.AGENT_STARTED,
            data={"agent": target_role},
            source_agent="orchestrator"
        )
    except AgentNotFoundError as e:
        yield AgentEvent(
            type=EventType.ERROR,
            data=f"Agent not found: {e.message}",
            source_agent="orchestrator"
        )
    except AgentProtocolError as e:
        yield AgentEvent(
            type=EventType.ERROR,
            data=f"Agent protocol error: {e.message}",
            source_agent="orchestrator"
        )
    except DelegationError as e:
        yield AgentEvent(
            type=EventType.ERROR,
            data=f"Delegation error: {e.message}",
            source_agent="orchestrator"
        )

# Test the patterns
import asyncio

async def test_patterns():
    print("Testing current pattern:")
    print("=" * 60)
    
    # Test current pattern
    async for event in run_delegation_current("engineer"):
        print(f"  Success: {event.type} - {event.data}")
    
    async for event in run_delegation_current("unknown"):
        print(f"  Error: {event.type} - {event.data}")
    
    print("\nTesting refactored pattern:")
    print("=" * 60)
    
    # Test refactored pattern
    try:
        async for event in run_delegation_refactored("engineer"):
            print(f"  Success: {event.type} - {event.data}")
    except Exception as e:
        print(f"  Exception: {e}")
    
    try:
        async for event in run_delegation_refactored("unknown"):
            print(f"  Error: {event.type} - {event.data}")
    except Exception as e:
        print(f"  Exception: {e}")
    
    try:
        async for event in run_delegation_refactored("broken"):
            print(f"  Error: {event.type} - {event.data}")
    except Exception as e:
        print(f"  Exception: {e}")
    
    print("\nBenefits of refactored pattern:")
    print("1. Type safety: Function returns AgentProtocol, not union")
    print("2. Clear error hierarchy: Specific exception types")
    print("3. No isinstance checks: Clean try/except blocks")
    print("4. Better stack traces: Exceptions preserve call chain")
    print("5. Easier testing: Can assert on exception types")

if __name__ == "__main__":
    asyncio.run(test_patterns())