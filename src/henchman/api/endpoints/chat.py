"""Chat endpoints for Henchman-AI API."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from henchman.api.auth import verify_api_key
from henchman.api.state import state
from henchman.core import Agent, AgentEvent, EventType
from henchman.providers import Message, ToolCall

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


class ChatMessage(BaseModel):
    """Chat message model."""

    role: str = Field(description="Message role (user, assistant, system)")
    content: str = Field(description="Message content")
    tool_calls: list[dict[str, Any]] | None = Field(
        default=None, description="Tool calls associated with the message",
    )
    tool_call_id: str | None = Field(default=None, description="Tool call ID for tool responses")


class ChatRequest(BaseModel):
    """Chat completion request model."""

    messages: list[ChatMessage] = Field(description="Conversation history")
    stream: bool = Field(default=False, description="Whether to stream the response")
    max_tokens: int | None = Field(default=None, description="Maximum tokens to generate")
    temperature: float | None = Field(default=None, description="Sampling temperature")
    system_prompt: str | None = Field(default=None, description="System prompt override")


class ChatResponse(BaseModel):
    """Chat completion response model."""

    message: ChatMessage = Field(description="Assistant message")
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
    agent: Agent, request_messages: list[ChatMessage], last_user_index: int,
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
        tool_calls.append(event.data)
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
            "tool_calls_successful", 0,
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
        chunk_data = {"tool_call": event.data}
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


@router.post("/completions", response_model=ChatResponse)
async def chat_completion(
    request: ChatRequest,
    api_key: Annotated[str | None, Depends(verify_api_key)],
    agent: Annotated[Agent, Depends(get_agent)],
) -> ChatResponse:
    """Create a chat completion.

    Args:
        request: Chat completion request.
        api_key: API key for authentication.
        agent: Agent instance.

    Returns:
        Chat completion response.
    """
    if not await verify_api_key(api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    # Set system prompt if provided
    if request.system_prompt:
        agent.system_prompt = request.system_prompt

    # Extract last user message from conversation history
    user_input = ""
    last_user_index = -1
    # Find the last user message in the conversation
    for i in range(len(request.messages) - 1, -1, -1):
        msg = request.messages[i]
        if msg.role == "user":
            user_input = msg.content
            last_user_index = i
            break

    # Set up agent history from conversation
    _setup_agent_history(agent, request.messages, last_user_index)

    # Collect all events
    content_parts: list[str] = []
    tool_calls: list[dict[str, Any]] = []
    finish_reason: str | None = None
    usage: dict[str, int] | None = None

    # Valid finish reasons from FinishReason enum
    valid_finish_reasons = {"stop", "tool_calls", "length", "content_filter"}

    try:
        async for event in agent.run(user_input=user_input):
            event_finish_reason, event_usage = _process_agent_event(
                event, content_parts, tool_calls, valid_finish_reasons,
            )
            if event_finish_reason is not None and finish_reason is None:
                finish_reason = event_finish_reason
                usage = event_usage
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating completion: {e!s}",
        ) from e

    # Build response
    response_message = ChatMessage(
        role="assistant",
        content="".join(content_parts),
        tool_calls=tool_calls or None,
    )

    # Update metrics
    _update_metrics(usage, tool_calls)

    return ChatResponse(
        message=response_message,
        usage=usage,
        finish_reason=finish_reason,
    )


@router.post("/completions/stream")
async def chat_completion_stream(
    request: ChatRequest,
    api_key: Annotated[str | None, Depends(verify_api_key)],
    agent: Annotated[Agent, Depends(get_agent)],
) -> StreamingResponse:
    """Create a streaming chat completion.

    Args:
        request: Chat completion request.
        api_key: API key for authentication.
        agent: Agent instance.

    Returns:
        Streaming response with SSE events.
    """
    if not await verify_api_key(api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    # Set system prompt if provided
    if request.system_prompt:
        agent.system_prompt = request.system_prompt

    # Extract last user message from conversation history
    user_input = ""
    last_user_index = -1
    # Find the last user message in the conversation
    for i in range(len(request.messages) - 1, -1, -1):
        msg = request.messages[i]
        if msg.role == "user":
            user_input = msg.content
            last_user_index = i
            break

    # Set up agent history from conversation
    _setup_agent_history(agent, request.messages, last_user_index)

    # Track metrics for streaming requests
    if state.metrics:
        state.metrics["requests_total"] = state.metrics.get("requests_total", 0) + 1

    async def event_generator() -> AsyncIterator[str]:
        """Generate SSE events from agent events."""
        index = 0
        tool_calls_count = 0
        try:
            async for event in agent.run(user_input=user_input):
                chunk_type, chunk_data, index, tool_calls_count = _process_stream_event(
                    event, index, tool_calls_count,
                )

                chunk = ChatStreamChunk(
                    type=chunk_type,
                    data=chunk_data,
                    index=index - 1,  # index was incremented in _process_stream_event
                )

                yield f"data: {chunk.model_dump_json()}\n\n"

            # Update successful request and tool call metrics
            _update_stream_metrics(tool_calls_count)

            # Send final done event
            done_chunk = ChatStreamChunk(
                type="done",
                data={},
                index=index,
            )
            yield f"data: {done_chunk.model_dump_json()}\n\n"

        except Exception as e:  # noqa: BLE001
            yield _handle_stream_error(e, index)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.get("/history")
async def get_chat_history(
    api_key: Annotated[str | None, Depends(verify_api_key)],
    agent: Annotated[Agent, Depends(get_agent)],
    limit: Annotated[int, Query(ge=1, le=1000, description="Maximum number of messages to return")] = 100,  # noqa: E501
) -> list[ChatMessage]:
    """Get chat history.

    Args:
        api_key: API key for authentication.
        agent: Agent instance.
        limit: Maximum number of messages to return.

    Returns:
        List of chat messages.
    """
    if not await verify_api_key(api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    # Get messages from agent
    messages = agent.get_messages_for_api()

    # Convert to response format
    return [
        ChatMessage(
            role=msg.role,
            content=msg.content or "",
            tool_calls=msg.tool_calls,
            tool_call_id=msg.tool_call_id,
        )
        for msg in messages[-limit:]
    ]



@router.delete("/history")
async def clear_chat_history(
    api_key: Annotated[str | None, Depends(verify_api_key)],
    agent: Annotated[Agent, Depends(get_agent)],
) -> dict[str, str]:
    """Clear chat history.

    Args:
        api_key: API key for authentication.
        agent: Agent instance.

    Returns:
        Success message.
    """
    if not await verify_api_key(api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    # Clear agent messages
    agent.messages.clear()

    return {"message": "Chat history cleared"}
