"""Typed payloads for AgentEvent data."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AgentStartedPayload:
    """Payload for AGENT_STARTED event."""
    agent: str


@dataclass(frozen=True)
class AgentCompletedPayload:
    """Payload for AGENT_COMPLETED event."""
    agent: str
    status: str
    summary: str


@dataclass(frozen=True)
class ToolCallRequestPayload:
    """Payload for TOOL_CALL_REQUEST event."""
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ToolCallResultPayload:
    """Payload for TOOL_CALL_RESULT event."""
    tool_call_id: str
    tool_name: str
    result: str
    success: bool
    display: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class AgentDelegatedPayload:
    """Payload for AGENT_DELEGATED event."""
    sender: str  # 'from' is a keyword in Python
    receiver: str # 'to' is commonly used
    task: str


@dataclass(frozen=True)
class AgentMessagePayload:
    """Payload for AGENT_MESSAGE event."""
    receiver: str
    message: str


@dataclass(frozen=True)
class FinishedPayload:
    """Payload for FINISHED event."""
    finish_reason: str | None = None
    usage: dict[str, int] | None = None
