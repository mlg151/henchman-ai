"""Event types for the agent loop."""

from dataclasses import dataclass
from enum import Enum
from typing import Any

__all__ = ["AgentEvent", "EventType"]


class EventType(Enum):
    """Types of events emitted by the agent during execution."""

    CONTENT = "content"  # Text content from model
    THOUGHT = "thought"  # Reasoning/thinking content (for reasoning models)
    TOOL_CALL_REQUEST = "tool_call_request"  # Model is requesting a tool call
    TOOL_CALL_RESULT = "tool_call_result"  # Result from a tool execution
    TOOL_CONFIRMATION = "tool_confirmation"  # Awaiting user approval for a tool
    CONTEXT_COMPACTED = "context_compacted"  # Context was compacted to fit model limits
    TURN_SUMMARIZED = "turn_summarized"  # Previous turn was summarized
    TURN_STATUS = "turn_status"  # Status update for current turn
    ERROR = "error"  # An error occurred
    FINISHED = "finished"  # Agent has finished processing

    # Multi-agent orchestration events
    AGENT_DELEGATED = "agent_delegated"  # Tech Lead delegating a task to a specialist
    AGENT_STARTED = "agent_started"  # Specialist agent beginning work
    AGENT_COMPLETED = "agent_completed"  # Specialist agent finished
    AGENT_MESSAGE = "agent_message"  # Inter-agent message via EventBus

    # Thinking and reasoning events
    THINKING_STARTED = "thinking_started"  # Agent has started thinking process
    THINKING_COMPLETED = "thinking_completed"  # Agent has completed thinking
    THINKING_REQUIRED = "thinking_required"  # Thinking pattern missing in response
    DELEGATION_DECISION = "delegation_decision"  # Decision about whether to delegate
    REFLECTION = "reflection"  # Reflection on completed work


@dataclass
class AgentEvent:
    """An event emitted by the agent during execution.

    Attributes:
        type: The type of event.
        data: Optional data associated with the event.
        source_agent: ID of the agent that produced this event.
    """

    type: EventType
    data: Any = None
    source_agent: str | None = None
