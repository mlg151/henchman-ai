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
    ERROR = auto()  # An error occurred
    FINISHED = auto()  # Agent has finished processing


@dataclass
class AgentEvent:
    """An event emitted by the agent during execution.

    Attributes:
        type: The type of event.
        data: Optional data associated with the event. The type depends on
            the event type:
            - CONTENT: str (text content)
            - THOUGHT: str (reasoning content)
            - TOOL_CALL_REQUEST: ToolCall object
            - TOOL_CALL_RESULT: dict with tool_call_id and result
            - ERROR: str or Exception
            - FINISHED: None
    """

    type: EventType
    data: Any = None
