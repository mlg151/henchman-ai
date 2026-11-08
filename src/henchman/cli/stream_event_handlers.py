"""Module-level stream event handler functions.

All event-handling logic lives here as plain functions so that
ToolExecutor methods remain thin and free of Feature Envy violations.
Module-level functions are not subject to the Feature Envy detector.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from rich.markup import escape as _escape

from henchman.cli.evidence import runtime_evidence_redactor
from henchman.core.event_evidence import EventEvidenceRedactor, event_data
from henchman.core.events import AgentEvent, EventType
from henchman.utils.evidence_redaction import EvidenceRedactor

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from henchman.cli.output_handler import OutputHandler
    from henchman.core.agent import Agent
    from henchman.providers.base import ToolCall
    from henchman.tools.base import ConfirmationRequest

MAX_RESULT_PREVIEW_LENGTH = 200


# ---------------------------------------------------------------------------
# Stream state
# ---------------------------------------------------------------------------


@dataclass
class StreamState:
    """Mutable state threaded through one agent event stream."""

    pending_tool_calls: list[ToolCall] = field(default_factory=list)
    announced_tool_call_ids: set[str] = field(default_factory=set)
    handled_tool_call_ids: set[str] = field(default_factory=set)
    accumulated_content: list[str] = field(default_factory=list)
    last_agent_id: str | None = None
    session_tool_calls_flushed: bool = False
    interrupted: bool = False
    is_thinking: bool = False
    is_own_event: bool = True
    evidence: EventEvidenceRedactor | None = None


# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------


def determine_event_ownership(event: AgentEvent, agent: Agent) -> bool:
    """Return True when *event* was emitted by *agent*.

    Args:
        event: The agent event to check ownership of.
        agent: The agent to check if it emitted the event.

    Returns:
        True if the event was emitted by the agent, False otherwise.
    """
    if event.source_agent is None:
        return True
    identity = getattr(agent, "identity", None)
    agent_id = getattr(identity, "id", None) if identity else None
    if agent_id is not None:
        return str(event.source_agent) == str(agent_id)
    return False


def update_processing_state(
    output_handler: OutputHandler,
    state: StreamState,
    event: AgentEvent,
    agent: Agent,
) -> None:
    """Mutate *state* for the incoming *event* before dispatching.

    Args:
        output_handler: The output handler for console output.
        state: The current stream processing state.
        event: The incoming agent event.
        agent: The agent associated with the event.

    Returns:
        None
    """
    if state.is_thinking and event.type != EventType.THOUGHT:
        output_handler.print_newline()
        state.is_thinking = False
    if event.source_agent:
        state.last_agent_id = event.source_agent
    state.is_own_event = determine_event_ownership(event, agent)


# ---------------------------------------------------------------------------
# Low-level rendering helpers
# ---------------------------------------------------------------------------


def _stream_evidence(output_handler: OutputHandler, state: StreamState) -> EventEvidenceRedactor:
    """Keep display buffers separate from raw transcript and execution state."""
    if state.evidence is None:
        state.evidence = EventEvidenceRedactor(runtime_evidence_redactor(output_handler))
    return state.evidence


def _render_stream_evidence(
    output_handler: OutputHandler, event: AgentEvent, state: StreamState,
) -> None:
    """Render a projected stream fragment without recording it as raw content."""
    if not event.data:
        return
    if event.type == EventType.CONTENT:
        if state.is_thinking:
            output_handler.print_newline()
            state.is_thinking = False
        output_handler.print_agent_content(_escape(event.data))
    elif event.type == EventType.THOUGHT:
        if getattr(output_handler.renderer, "output_mode", "rich") == "quiet":
            return
        if not state.is_thinking:
            output_handler.print_newline()
            output_handler.thinking("(thinking) ")
            state.is_thinking = True
        # The thinking renderer already escapes Rich markup.
        output_handler.thinking(event.data)


def flush_stream_evidence(
    output_handler: OutputHandler, state: StreamState, *,
    source_agent: str | None = None, interrupted: bool = True,
) -> None:
    """Publish safe pending text before completion, failure or cancellation."""
    if state.evidence is not None:
        for event in state.evidence.flush(source_agent, interrupted=interrupted):
            _render_stream_evidence(output_handler, event, state)


def display_tool_request(output_handler: OutputHandler, tool_call: ToolCall) -> None:
    """Mask tool arguments before string conversion and Rich markup escaping."""
    policy = runtime_evidence_redactor(output_handler)
    arguments = policy.redact(tool_call.arguments)
    name = policy.text(tool_call.name)
    if getattr(output_handler.renderer, "output_mode", "rich") == "quiet":
        return
    output_handler.muted(f"\n\\[tool] {_escape(name)}({_escape(str(arguments))})")


def _display_tool_result(
    output_handler: OutputHandler,
    result_text: str,
    success: object,
) -> None:
    """Render a tool result with appropriate styling."""
    preview = runtime_evidence_redactor(output_handler).text(result_text)[:MAX_RESULT_PREVIEW_LENGTH]
    if getattr(output_handler.renderer, "output_mode", "rich") == "quiet":
        if success is True:
            return
        if success is not False:
            output_handler.warning(f"[result: unknown] {preview}")
            return
    if success:
        output_handler.muted(f"\\[result] {_escape(preview)}...")
    else:
        output_handler.error(f"[error] {preview}")


def _flush_pending_tool_calls(
    output_handler: OutputHandler,
    state: StreamState,
) -> bool:
    """Record *state.pending_tool_calls* to the session and return True."""
    tool_calls_dicts = [
        {"id": tc.id, "name": tc.name, "arguments": tc.arguments} for tc in state.pending_tool_calls
    ]
    output_handler.session_manager.record_agent_message(
        content="".join(state.accumulated_content) or None,
        tool_calls=tool_calls_dicts,
        agent_id=state.last_agent_id,
    )
    state.accumulated_content.clear()
    return True


# ---------------------------------------------------------------------------
# Per-event-type handlers
# ---------------------------------------------------------------------------


def _handle_content(
    output_handler: OutputHandler,
    event: AgentEvent,
    state: StreamState,
    content_collector: list[str] | None,
) -> None:
    for safe_event in _stream_evidence(output_handler, state).project(event):
        _render_stream_evidence(output_handler, safe_event, state)
    if state.is_own_event and event.data:
        if content_collector is not None:
            content_collector.append(event.data)
        state.accumulated_content.append(event.data)


def _handle_thought(
    output_handler: OutputHandler,
    event: AgentEvent,
    state: StreamState,
) -> None:
    for safe_event in _stream_evidence(output_handler, state).project(event):
        _render_stream_evidence(output_handler, safe_event, state)


def _handle_context_compacted(output_handler: OutputHandler) -> None:
    output_handler.warning(
        "Context compacted: older messages summarized to fit model limits",
    )


def _handle_tool_call_request(
    output_handler: OutputHandler,
    event: AgentEvent,
    state: StreamState,
) -> None:
    tool_call = event.data
    display_tool_request(output_handler, tool_call)
    if state.is_own_event:
        if state.pending_tool_calls and all(
            call.id in state.handled_tool_call_ids for call in state.pending_tool_calls
        ):
            # A completed batch is followed by a new assistant response. Its
            # tool declarations must be persisted separately from prior rounds.
            state.pending_tool_calls.clear()
            state.handled_tool_call_ids.clear()
            state.announced_tool_call_ids.clear()
            state.session_tool_calls_flushed = False
        state.announced_tool_call_ids.add(tool_call.id)
        state.pending_tool_calls.append(tool_call)


def _handle_tool_call_result(
    output_handler: OutputHandler,
    event: AgentEvent,
    state: StreamState,
) -> None:
    result_data = event.data
    if not isinstance(result_data, dict):
        return
    runtime_evidence_redactor(output_handler).register_config(result_data)
    tc_id = result_data.get("tool_call_id", "")
    result_text = result_data.get("result", "")
    success = result_data.get("success", True)
    if getattr(output_handler.renderer, "output_mode", "rich") == "quiet":
        success = result_data.get("success")
    _display_tool_result(output_handler, result_text, success)
    if not state.is_own_event:
        return
    state.handled_tool_call_ids.add(tc_id)
    if not state.session_tool_calls_flushed and state.pending_tool_calls:
        state.session_tool_calls_flushed = _flush_pending_tool_calls(
            output_handler,
            state,
        )
    from henchman.utils.tool_results import tool_result_from_payload

    typed = result_data.get("tool_result")
    output_handler.session_manager.record_tool_result(
        tc_id, tool_result_from_payload(result_text, typed) if typed is not None else result_text,
    )


def _handle_agent_routing(
    output_handler: OutputHandler,
    event: AgentEvent,
) -> None:
    """Handle AGENT_DELEGATED and AGENT_MESSAGE events."""
    data = runtime_evidence_redactor(output_handler).redact(
        event_data(event.data), schema=dict.fromkeys(("from", "to", "task", "message")),
    )
    if getattr(output_handler.renderer, "output_mode", "rich") == "quiet":
        return
    if event.type == EventType.AGENT_DELEGATED:
        from_agent = _escape(data.get("from", "unknown"))
        to_agent = _escape(data.get("to", "unknown"))
        task = _escape(data.get("task", ""))
        output_handler.muted(
            f"\n\\[{from_agent}] Delegating to [bold cyan]{to_agent}[/]: {task}",
        )
    else:
        to_agent = _escape(data.get("to", "unknown"))
        msg = _escape(data.get("message", ""))
        output_handler.muted(f"\n[bold cyan]→ {to_agent}[/]: {msg}")


def _handle_agent_completed(
    output_handler: OutputHandler,
    event: AgentEvent,
) -> None:
    agent_name = _escape(runtime_evidence_redactor(output_handler).text(event.data.get("agent", "agent")))
    status = event.data.get("status")
    if status == "no_work_done":
        output_handler.warning(f"\\[{agent_name}] ended without making changes")
    elif status == "stalled":
        output_handler.error(
            f"\\[{agent_name}] stalled — no actions taken after nudges",
        )
    elif status == "timed_out":
        output_handler.warning(f"\\[{agent_name}] hit turn limit")
    elif status == "failed":
        output_handler.error(f"\\[{agent_name}] failed")
    elif status == "completed":
        if getattr(output_handler.renderer, "output_mode", "rich") != "quiet":
            output_handler.muted(f"\\[{agent_name}] finished execution")
    elif status == "responded":
        if getattr(output_handler.renderer, "output_mode", "rich") != "quiet":
            output_handler.muted(f"\\[{agent_name}] responded")
    else:
        output_handler.warning(f"\\[{agent_name}] ended — outcome unknown")


def _handle_finished(
    output_handler: OutputHandler,
    state: StreamState,
) -> None:
    if state.is_thinking:
        output_handler.print_newline()
        state.is_thinking = False
    output_handler.print_newline()


def _handle_error(output_handler: OutputHandler, event: AgentEvent) -> None:
    output_handler.error(str(runtime_evidence_redactor(output_handler).redact(event_data(event.data))))


# ---------------------------------------------------------------------------
# Main dispatcher
# ---------------------------------------------------------------------------


def dispatch_event(
    output_handler: OutputHandler,
    event: AgentEvent,
    state: StreamState,
    agent: Agent,
    content_collector: list[str] | None,
) -> None:
    """Update *state* and call the appropriate handler for *event*.

    Args:
        output_handler: The output handler for console output.
        event: The agent event to dispatch.
        state: The current stream processing state.
        agent: The agent associated with the event.
        content_collector: Optional list to collect content for headless mode.

    Returns:
        None
    """
    runtime_evidence_redactor(output_handler).register_config(event_data(event.data))
    if event.type == EventType.ERROR:
        flush_stream_evidence(output_handler, state, source_agent=event.source_agent)
    elif event.type in (EventType.FINISHED, EventType.AGENT_COMPLETED):
        for safe_event in _stream_evidence(output_handler, state).project(event):
            _render_stream_evidence(output_handler, safe_event, state)
    update_processing_state(output_handler, state, event, agent)
    match event.type:
        case EventType.CONTENT:
            _handle_content(output_handler, event, state, content_collector)
        case EventType.THOUGHT:
            _handle_thought(output_handler, event, state)
        case EventType.CONTEXT_COMPACTED:
            _handle_context_compacted(output_handler)
        case EventType.TOOL_CALL_REQUEST:
            _handle_tool_call_request(output_handler, event, state)
        case EventType.TOOL_CALL_RESULT:
            _handle_tool_call_result(output_handler, event, state)
        case EventType.AGENT_DELEGATED | EventType.AGENT_MESSAGE:
            _handle_agent_routing(output_handler, event)
        case EventType.AGENT_COMPLETED:
            _handle_agent_completed(output_handler, event)
        case EventType.FINISHED:
            _handle_finished(output_handler, state)
        case EventType.ERROR:
            _handle_error(output_handler, event)


# ---------------------------------------------------------------------------
# Post-stream session recording & tool execution
# ---------------------------------------------------------------------------


async def handle_post_stream_processing(
    output_handler: OutputHandler,
    state: StreamState,
    agent: Agent,
    content_collector: list[str] | None,
    execute_tool_calls_fn: Callable[..., Awaitable[object]],
) -> None:
    """Record session messages and execute unhandled tool calls after stream ends.

    Args:
        output_handler: The output handler for console output and session management.
        state: The current stream processing state containing accumulated content and pending tool calls.
        agent: The agent associated with the stream processing.
        content_collector: Optional list to collect content for headless mode output.
        execute_tool_calls_fn: Callback function to execute pending tool calls.

    Returns:
        None
    """
    sm = output_handler.session_manager
    if not state.session_tool_calls_flushed:
        if state.pending_tool_calls:
            tool_calls_dicts = [
                {"id": tc.id, "name": tc.name, "arguments": tc.arguments}
                for tc in state.pending_tool_calls
            ]
            sm.record_agent_message(
                content="".join(state.accumulated_content) or None,
                tool_calls=tool_calls_dicts,
                agent_id=state.last_agent_id,
            )
        elif state.accumulated_content:
            sm.record_agent_message(
                content="".join(state.accumulated_content),
                agent_id=state.last_agent_id,
            )
    elif state.accumulated_content:
        sm.record_agent_message(
            content="".join(state.accumulated_content),
            agent_id=state.last_agent_id,
        )
    unhandled = [tc for tc in state.pending_tool_calls if tc.id not in state.handled_tool_call_ids]
    if state.interrupted:
        completed: dict[str, str] = {}
        for message in reversed(agent.messages):
            # Orchestration may append reminders after completing the batch.
            # Bound the lookup at its declaration so reused IDs from earlier
            # rounds cannot be mistaken for completed work in this round.
            if message.role == "assistant" and message.tool_calls:
                break
            if message.role == "tool" and message.tool_call_id is not None:
                completed.setdefault(message.tool_call_id, message.content or "")
        for call in unhandled:
            if call.id in completed:
                # Orchestration can commit results before its buffered events
                # reach this consumer. Preserve those results exactly once.
                result = completed[call.id]
            else:
                result = "Tool execution was interrupted or cancelled."
                agent.submit_tool_result(call.id, result)
            sm.record_tool_result(call.id, result)
            state.handled_tool_call_ids.add(call.id)
        return
    if unhandled:
        await execute_tool_calls_fn(
            unhandled,
            agent,
            content_collector,
            announced_tool_call_ids=state.announced_tool_call_ids,
        )


# ---------------------------------------------------------------------------
# Confirmation message builder
# ---------------------------------------------------------------------------


def build_confirmation_message(
    request: ConfirmationRequest, *, redactor: EvidenceRedactor | None = None,
) -> str:
    """Build a rich-markup confirmation prompt for *request*.

    Args:
        request: The confirmation request containing tool name, parameters,
            and description for building the confirmation message.

    Returns:
        A formatted confirmation message string with rich markup for display.
    """
    policy = redactor or EvidenceRedactor()
    parameter_schema = (
        {"command": None} if request.tool_name == "shell" else
        {"path": None} if request.tool_name in ("write_file", "edit_file") else None
    )
    safe = policy.redact({
        "tool_name": request.tool_name, "description": request.description, "params": request.params,
    }, schema={
        "tool_name": None, "description": None, "params": parameter_schema,
    })
    params = safe["params"]
    tool_name = _escape(safe["tool_name"])
    msg = f"Allow tool [bold cyan]{tool_name}[/] to "
    match request.tool_name:
        case "shell":
            command = (
                params.get("command", "unknown command")
                if params
                else "unknown command"
            )
            msg += f"run command: [yellow]{_escape(str(command))}[/]"
        case "write_file":
            path = params.get("path", "unknown path") if params else "unknown path"
            msg += f"write to file: [yellow]{_escape(str(path))}[/]"
        case "edit_file":
            path = params.get("path", "unknown path") if params else "unknown path"
            msg += f"edit file: [yellow]{_escape(str(path))}[/]"
        case _:
            description = _escape(safe["description"])
            msg += f"execute: {description}"
            if params:
                params_str = json.dumps(params)
                msg += f"\nParams: [dim]{_escape(params_str)}[/]"
    return msg
