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
    "done_when",
    "context",
    "files",
    "background",
    "requirements",
    "depends_on",
)


def extract_brief_fields(arguments: dict[str, Any]) -> dict[str, Any]:
    """Extract delegation brief fields from tool arguments.

    Args:
        arguments: Dictionary of tool arguments containing delegation fields.

    Returns:
        Dictionary containing only the brief fields from the input arguments.
    """
    return {f: arguments.get(f) for f in _BRIEF_FIELDS}


def create_delegation_event(
    agent: Agent,
    target: str,
    task: str,
) -> AgentEvent:
    """Create a delegation event.

    Args:
        agent: The agent that is delegating the task.
        target: The target agent role to delegate to.
        task: The task description to delegate.

    Returns:
        AgentEvent of type AGENT_DELEGATED with delegation data.
    """
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
    """Create a tool result event.

    Args:
        agent: The agent that executed the tool.
        tool_call: The tool call that was executed.
        result_content: The result content from the tool execution.

    Returns:
        AgentEvent of type TOOL_CALL_RESULT with tool result data.
    """
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
    """Update ledger with delegation outcome.

    Args:
        ledger: The delegation ledger to update.
        record: The delegation record to update.
        result: The result of the delegation.
        had_error: Whether the delegation had an error.

    Returns:
        None
    """
    if not ledger or not record:
        return
    if had_error:
        ledger.fail_delegation(record, result)
    else:
        ledger.complete_delegation(record, result)
