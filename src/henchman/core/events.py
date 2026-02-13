"""Event types for the agent loop."""

from dataclasses import dataclass
from enum import Enum, auto
from typing import Any

__all__ = ["AgentEvent", "EventType"]


class EventType(Enum):
    """Types of events emitted by the agent during execution."""

    CONTENT = auto()  # Text content from model
    THOUGHT = auto()  # Reasoning/thinking content (for reasoning models)
    TOOL_CALL_REQUEST = auto()  # Model is requesting a tool call
    TOOL_CALL_RESULT = auto()  # Result from a tool execution
    TOOL_CONFIRMATION = auto()  # Awaiting user approval for a tool
    CONTEXT_COMPACTED = auto()  # Context was compacted to fit model limits
    TURN_SUMMARIZED = auto()  # Previous turn was summarized
    TURN_STATUS = auto()  # Status update for current turn
    ERROR = auto()  # An error occurred
    FINISHED = auto()  # Agent has finished processing

    # Multi-agent orchestration events
    AGENT_DELEGATED = auto()  # Tech Lead delegating a task to a specialist
    AGENT_STARTED = auto()  # Specialist agent beginning work
    AGENT_COMPLETED = auto()  # Specialist agent finished
    AGENT_MESSAGE = auto()  # Inter-agent message via EventBus


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
