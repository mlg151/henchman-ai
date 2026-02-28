"""Event factory helpers for the delegation controller.

Pure functions that create AgentEvent instances and update the task ledger
during delegation flows.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from henchman.core.events import AgentEvent, EventType

from .orchestrator_types import RESULT_PREVIEW_LENGTH

if TYPE_CHECKING:
    from henchman.core.agent import Agent
    from henchman.providers.base import ToolCall


_BRIEF_FIELDS = (
    "done_when", "context", "files",
    "background", "requirements", "depends_on",
)


def extract_brief_fields(arguments: dict[str, Any]) -> dict[str, Any]:
    """Extract delegation brief fields from tool arguments."""
    return {f: arguments.get(f) for f in _BRIEF_FIELDS}


def create_delegation_event(
    agent: Agent,
    target: str,
    task: str,
) -> AgentEvent:
    """Create a delegation event."""
    return AgentEvent(
        type=EventType.AGENT_DELEGATED,
        data={
            "from": agent.identity.id if agent.identity else "unknown",
            "to": target,
            "task": task,
        },
        source_agent="orchestrator",
    )


def create_tool_result_event(
    agent: Agent,
    tool_call: ToolCall,
    result_content: str,
) -> AgentEvent:
    """Create a tool result event."""
    return AgentEvent(
        type=EventType.TOOL_CALL_RESULT,
        data={
            "tool_call_id": tool_call.id,
            "tool_name": tool_call.name,
            "result": (result_content or "")[:RESULT_PREVIEW_LENGTH],
            "success": True,
        },
        source_agent=agent.identity.id if agent.identity else None,
    )


def update_ledger(
    ledger: Any,
    record: Any,
    result: str,
    *,
    had_error: bool,
) -> None:
    """Update ledger with delegation outcome."""
    if not ledger or not record:
        return
    if had_error:
        ledger.fail_delegation(record, result)
    else:
        ledger.complete_delegation(record, result)
