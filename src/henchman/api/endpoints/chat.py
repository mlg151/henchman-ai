"""Chat endpoints for Henchman-AI API."""

from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING, Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator

from henchman.api.auth import verified_chat_authority
from henchman.api.run_accounting import ApiChatRun, ApiChatRuns
from henchman.api.state import state
from henchman.core import Agent, AgentEvent, EventType
from henchman.core.run_budget import BudgetAccountingError, BudgetControlError, BudgetExceeded
from henchman.providers import Message, ToolCall
from henchman.utils.evidence_redaction import EvidenceRedactor

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


class ChatMessage(BaseModel):
    """Chat message model."""

    role: str = Field(description="Message role (user, assistant, system)")
    content: str = Field(description="Message content")
    tool_calls: list[dict[str, Any]] | None = Field(
        default=None,
        description="Tool calls associated with the message",
    )
    tool_call_id: str | None = Field(default=None, description="Tool call ID for tool responses")


class ChatRequest(BaseModel):
    """Chat completion request model."""

    model_config = ConfigDict(extra="forbid")

    messages: list[ChatMessage] = Field(description="Conversation history", min_length=1)
    run_id: str | None = Field(
        default=None,
        min_length=1,
        description="Original process run ID for tool-result continuation",
    )
    stream: bool = Field(default=False, description="Whether to stream the response")
    max_tokens: int | None = Field(default=None, description="Maximum tokens to generate")
    temperature: float | None = Field(default=None, description="Sampling temperature")
    system_prompt: str | None = Field(default=None, description="System prompt override")

    @model_validator(mode="after")
    def reject_unsupported_options(self) -> ChatRequest:
        supplied = self.model_fields_set.intersection({"max_tokens", "temperature"})
        if supplied:
            raise ValueError(
                f"Unsupported request options: {', '.join(sorted(supplied))}; omit them and configure provider request defaults on the server"
            )
        return self


class ChatResponse(BaseModel):
    """Chat completion response model."""

    message: ChatMessage = Field(description="Assistant message")
    run_id: str | None = None
    budget: dict[str, Any] | None = None
    accounting_lifetime: str = "process"
    usage: dict[str, int] | None = Field(default=None, description="Token usage information")
    finish_reason: str | None = Field(default=None, description="Reason for completion")


class ChatStreamChunk(BaseModel):
    """Chat stream chunk model."""

    type: str = Field(description="Event type (content, tool_call, finished)")
    data: dict[str, Any] = Field(description="Event data")
    index: int = Field(default=0, description="Chunk index for ordering")


router = APIRouter(prefix="/v1/chat", tags=["chat"])


def _convert_chat_message_to_internal(msg: ChatMessage) -> Message:
    """Convert a ChatMessage to internal Message format.

    Args:
        msg: ChatMessage to convert.

    Returns:
        Internal Message object.
    """
    message_tool_calls = None
    if msg.tool_calls:
        message_tool_calls = [
            ToolCall(
                id=tc.get("id", ""),
                name=tc.get("name", ""),
                arguments=tc.get("arguments", {}),
            )
            for tc in msg.tool_calls
        ]

    return Message(
        role=msg.role,
        content=msg.content,
        tool_calls=message_tool_calls,
        tool_call_id=msg.tool_call_id,
    )


def _setup_agent_history(
    agent: Agent,
    request_messages: list[ChatMessage],
    last_user_index: int,
) -> None:
    """Set up agent history from request messages.

    Args:
        agent: Agent instance to configure.
        request_messages: List of chat messages from request.
        last_user_index: Index of the last user message to exclude.
    """
    agent.messages.clear()
    # Add all messages except the last user message
    for i, msg in enumerate(request_messages):
        if i == last_user_index:
            # Skip the last user message
            continue

        agent.messages.append(_convert_chat_message_to_internal(msg))


def _process_agent_event(
    event: AgentEvent,
    content_parts: list[str],
    tool_calls: list[dict[str, Any]],
    valid_finish_reasons: set[str],
) -> tuple[str | None, dict[str, int] | None]:
    """Process a single agent event.

    Args:
        event: Agent event to process.
        content_parts: List to append content to.
        tool_calls: List to append tool calls to.
        valid_finish_reasons: Set of valid finish reasons.

    Returns:
        Tuple of (finish_reason, usage) if found, otherwise (None, None).
    """
    if event.type == EventType.CONTENT:
        content_parts.append(event.data)
        return None, None
    if event.type == EventType.TOOL_CALL_REQUEST:
        tool_calls.append(asdict(event.data) if isinstance(event.data, ToolCall) else event.data)
        return None, None
    if event.type == EventType.FINISHED:
        # Extract finish reason from first valid FINISHED event
        # Event data can be a string (finish reason) or a dict with finish_reason and usage
        if isinstance(event.data, dict):
            # New format with usage information
            if (
                "finish_reason" in event.data
                and event.data["finish_reason"] in valid_finish_reasons
            ):
                finish_reason = event.data["finish_reason"]
                usage = event.data.get("usage")
                return finish_reason, usage
        elif isinstance(event.data, str) and event.data in valid_finish_reasons:
            # Old format - just finish reason string
            return event.data, None

    return None, None


def _update_metrics(usage: dict[str, int] | None, tool_calls: list[dict[str, Any]]) -> None:
    """Update metrics in global state.

    Args:
        usage: Token usage information.
        tool_calls: List of tool calls made.
    """
    if not state.metrics:
        return

    # Increment request counts
    state.metrics["requests_total"] = state.metrics.get("requests_total", 0) + 1
    state.metrics["requests_successful"] = state.metrics.get("requests_successful", 0) + 1

    # Update token usage if available
    if usage:
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        total_tokens = usage.get("total_tokens", 0)

        state.metrics["tokens_prompt"] = state.metrics.get("tokens_prompt", 0) + prompt_tokens
        state.metrics["tokens_completion"] = (
            state.metrics.get("tokens_completion", 0) + completion_tokens
        )
        state.metrics["tokens_total"] = state.metrics.get("tokens_total", 0) + total_tokens

    # Update tool call counts
    if tool_calls:
        state.metrics["tool_calls_total"] = state.metrics.get("tool_calls_total", 0) + len(
            tool_calls,
        )
        # Assume all tool calls are successful for now
        state.metrics["tool_calls_successful"] = state.metrics.get(
            "tool_calls_successful",
            0,
        ) + len(tool_calls)


def _process_stream_event(
    event: AgentEvent,
    index: int,
    tool_calls_count: int,
) -> tuple[str, dict[str, Any], int, int]:
    """Process a single agent event for streaming.

    Args:
        event: Agent event to process.
        index: Current event index.
        tool_calls_count: Current count of tool calls.

    Returns:
        Tuple of (chunk_type, chunk_data, new_index, new_tool_calls_count)
    """
    chunk_type = "content"
    chunk_data = {"text": event.data}

    if event.type == EventType.TOOL_CALL_REQUEST:
        chunk_type = "tool_call"
        chunk_data = {
            "tool_call": asdict(event.data) if isinstance(event.data, ToolCall) else event.data
        }
        tool_calls_count += 1
    elif event.type == EventType.FINISHED:
        chunk_type = "finished"
        # Use actual finish reason from event data
        reason = event.data or "stop"
        chunk_data = {"reason": reason}

        # Extract usage information if available
        if isinstance(event.data, dict) and "usage" in event.data:
            usage = event.data["usage"]
            # Update token usage metrics
            if state.metrics and usage:
                prompt_tokens = usage.get("prompt_tokens", 0)
                completion_tokens = usage.get("completion_tokens", 0)
                total_tokens = usage.get("total_tokens", 0)

                state.metrics["tokens_prompt"] = (
                    state.metrics.get("tokens_prompt", 0) + prompt_tokens
                )
                state.metrics["tokens_completion"] = (
                    state.metrics.get("tokens_completion", 0) + completion_tokens
                )
                state.metrics["tokens_total"] = state.metrics.get("tokens_total", 0) + total_tokens

    return chunk_type, chunk_data, index + 1, tool_calls_count


def _update_stream_metrics(tool_calls_count: int) -> None:
    """Update metrics for streaming requests.

    Args:
        tool_calls_count: Number of tool calls made during the stream.
    """
    if not state.metrics:
        return

    state.metrics["requests_successful"] = state.metrics.get("requests_successful", 0) + 1
    if tool_calls_count > 0:
        state.metrics["tool_calls_total"] = (
            state.metrics.get("tool_calls_total", 0) + tool_calls_count
        )
        state.metrics["tool_calls_successful"] = (
            state.metrics.get("tool_calls_successful", 0) + tool_calls_count
        )


def _handle_stream_error(e: Exception, index: int) -> str:
    """Handle errors in streaming response.

    Args:
        e: Exception that occurred.
        index: Current event index.

    Returns:
        Error chunk as SSE string.
    """
    # Update failed request metric
    if state.metrics:
        state.metrics["requests_failed"] = state.metrics.get("requests_failed", 0) + 1

    error_chunk = ChatStreamChunk(
        type="error",
        data={"error": str(e)},
        index=index,
    )
    return f"data: {error_chunk.model_dump_json()}\n\n"


async def get_agent() -> Agent:
    """Get or create an agent instance.

    Returns:
        Agent instance.

    Raises:
        HTTPException: If agent cannot be created.
    """
    if state.agent is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Agent not available",
        )
    return state.agent


def get_chat_runs() -> ApiChatRuns:
    """Require the lifespan-owned process registry; no unaccounted fallback."""
    if not isinstance(state.chat_runs, ApiChatRuns):
        raise HTTPException(503, "Chat accounting runtime is unavailable")
    return state.chat_runs


def _request_messages(request: ChatRequest) -> list[Message]:
    return [_convert_chat_message_to_internal(message) for message in request.messages]


def _failure_payload(error: Exception, run: ApiChatRun | None) -> tuple[int, dict[str, Any]]:
    policy = EvidenceRedactor()
    if state.settings is not None:
        policy.register_config(state.settings.model_dump())
    code = 500
    if isinstance(error, HTTPException):
        code = error.status_code
    elif isinstance(error, BudgetExceeded):
        code = 429
    elif isinstance(error, BudgetControlError):
        code = 503
    payload: dict[str, Any] = {"error": policy.text(str(error))}
    if isinstance(error, (BudgetExceeded, BudgetAccountingError)):
        payload["reason"] = error.reason
    if run is not None:
        payload.update(run_id=run.run_id, budget=run.budget(), accounting_lifetime="process")
    return code, payload


@router.post("/completions", response_model=ChatResponse)
async def chat_completion(
    request: ChatRequest,
    authority: Annotated[str, Depends(verified_chat_authority)],
) -> ChatResponse | StreamingResponse:
    """Run a new turn or continue one caller-owned process budget."""
    if request.stream:
        return _stream_response(request, authority)
    runs = get_chat_runs()
    run: ApiChatRun | None = None
    content_parts: list[str] = []
    tool_calls: list[dict[str, Any]] = []
    finish_reason: str | None = None
    usage: dict[str, int] | None = None
    try:
        async with runs.execute(
            authority,
            _request_messages(request),
            run_id=request.run_id,
            system_prompt=request.system_prompt,
        ) as (run, events):
            async for event in events:
                reason, event_usage = _process_agent_event(
                    event,
                    content_parts,
                    tool_calls,
                    {"stop", "tool_calls", "length", "content_filter"},
                )
                if reason is not None:
                    finish_reason, usage = reason, event_usage
    except HTTPException:
        raise
    except Exception as error:
        code, payload = _failure_payload(error, run)
        raise HTTPException(code, payload) from error
    _update_metrics(usage, tool_calls)
    assert run is not None
    return ChatResponse(
        message=ChatMessage(
            role="assistant", content="".join(content_parts), tool_calls=tool_calls or None
        ),
        usage=usage,
        finish_reason=finish_reason,
        run_id=run.run_id,
        budget=run.budget(),
    )


def _stream_response(request: ChatRequest, authority: str) -> StreamingResponse:
    runs = get_chat_runs()
    messages = _request_messages(request)
    runs.check_request(
        authority, messages, run_id=request.run_id, system_prompt=request.system_prompt
    )

    async def event_generator() -> AsyncIterator[str]:
        index, tool_count = 0, 0
        run: ApiChatRun | None = None
        if state.metrics:
            state.metrics["requests_total"] = state.metrics.get("requests_total", 0) + 1
        try:
            async with runs.execute(
                authority, messages, run_id=request.run_id, system_prompt=request.system_prompt
            ) as (run, events):
                start = ChatStreamChunk(
                    type="start",
                    data={"run_id": run.run_id, "accounting_lifetime": "process"},
                    index=index,
                )
                index += 1
                yield f"data: {start.model_dump_json()}\n\n"
                async for event in events:
                    kind, data, index, tool_count = _process_stream_event(event, index, tool_count)
                    chunk = ChatStreamChunk(type=kind, data=data, index=index - 1)
                    yield f"data: {chunk.model_dump_json()}\n\n"
            _update_stream_metrics(tool_count)
            done = ChatStreamChunk(
                type="done",
                data={
                    "run_id": run.run_id,
                    "budget": run.budget(),
                    "accounting_lifetime": "process",
                },
                index=index,
            )
            yield f"data: {done.model_dump_json()}\n\n"
        except Exception as error:
            code, payload = _failure_payload(error, run)
            if state.metrics:
                state.metrics["requests_failed"] = state.metrics.get("requests_failed", 0) + 1
            chunk = ChatStreamChunk(
                type="error", data={**payload, "status_code": code}, index=index
            )
            yield f"data: {chunk.model_dump_json()}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/completions/stream")
async def chat_completion_stream(
    request: ChatRequest,
    authority: Annotated[str, Depends(verified_chat_authority)],
) -> StreamingResponse:
    """Stream one isolated turn; follow-ups retain their original budget."""
    return _stream_response(request, authority)


@router.get("/history")
async def get_chat_history(
    authority: Annotated[str, Depends(verified_chat_authority)],
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    run_id: str | None = None,
) -> list[ChatMessage]:
    """Read this caller's selected run, or their latest retained run."""
    return [
        ChatMessage(
            role=message.role,
            content=message.content or "",
            tool_calls=[asdict(call) for call in message.tool_calls]
            if message.tool_calls
            else None,
            tool_call_id=message.tool_call_id,
        )
        for message in get_chat_runs().history(authority, run_id)[-limit:]
    ]


@router.delete("/history")
async def clear_chat_history(
    authority: Annotated[str, Depends(verified_chat_authority)],
    run_id: str | None = None,
) -> dict[str, str]:
    """Hide the history view while retaining continuation and budget authority."""
    get_chat_runs().hide_history(authority, run_id)
    return {"message": "Chat history cleared"}
