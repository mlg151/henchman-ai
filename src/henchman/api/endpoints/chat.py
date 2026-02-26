"""Chat endpoints for Henchman-AI API."""

from __future__ import annotations

from typing import Any, AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from henchman.api.auth import verify_api_key
from henchman.api.state import state
from henchman.core import Agent, AgentEvent, EventType
from henchman.providers import Message, ToolCall


class ChatMessage(BaseModel):
    """Chat message model."""

    role: str = Field(description="Message role (user, assistant, system)")
    content: str = Field(description="Message content")
    tool_calls: list[dict[str, Any]] | None = Field(
        default=None, description="Tool calls associated with the message"
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
    api_key: str | None = Depends(verify_api_key),
    agent: Agent = Depends(get_agent),
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
    # Convert messages to internal format
    messages = []
    for msg in request.messages:
        # Convert dictionary tool_calls to ToolCall objects if present
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
        
        messages.append(
            Message(
                role=msg.role,
                content=msg.content,
                tool_calls=message_tool_calls,
                tool_call_id=msg.tool_call_id,
            )
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
    
    # Set agent messages to conversation history (excluding the last user message
    # since agent.run() will add it)
    agent.messages.clear()
    # Add all messages except the last user message
    for i, msg in enumerate(request.messages):
        if i == last_user_index:
            # Skip the last user message
            continue
        
        # Convert to Message format (reusing the conversion logic from above)
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
        
        agent.messages.append(
            Message(
                role=msg.role,
                content=msg.content,
                tool_calls=message_tool_calls,
                tool_call_id=msg.tool_call_id,
            )
        )

    # Collect all events
    events: list[AgentEvent] = []
    content_parts: list[str] = []
    tool_calls: list[dict[str, Any]] = []
    finish_reason: str | None = None
    usage: dict[str, int] | None = None

    # Valid finish reasons from FinishReason enum
    valid_finish_reasons = {"stop", "tool_calls", "length", "content_filter"}

    try:
        async for event in agent.run(user_input=user_input):
            events.append(event)
            if event.type == EventType.CONTENT:
                content_parts.append(event.data)
            elif event.type == EventType.TOOL_CALL_REQUEST:
                tool_calls.append(event.data)
            elif event.type == EventType.FINISHED and finish_reason is None:
                # Extract finish reason from first valid FINISHED event
                # (there may be multiple, e.g., one from _process_streaming_response
                # with actual finish reason and one from run() with generic message)
                # Event data can be a string (finish reason) or a dict with finish_reason and usage
                if isinstance(event.data, dict):
                    # New format with usage information
                    if "finish_reason" in event.data and event.data["finish_reason"] in valid_finish_reasons:
                        finish_reason = event.data["finish_reason"]
                        # Extract usage from event data if available
                        if "usage" in event.data:
                            usage = event.data["usage"]
                elif isinstance(event.data, str) and event.data in valid_finish_reasons:
                    # Old format - just finish reason string
                    finish_reason = event.data
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating completion: {str(e)}",
        ) from e

    # Build response
    response_message = ChatMessage(
        role="assistant",
        content="".join(content_parts),
        tool_calls=tool_calls if tool_calls else None,
    )

    # Usage information is extracted from FINISHED event if available
    # usage variable is already set from event processing above
    
    # Update metrics in state
    if state.metrics:
        # Increment request counts
        state.metrics["requests_total"] = state.metrics.get("requests_total", 0) + 1
        state.metrics["requests_successful"] = state.metrics.get("requests_successful", 0) + 1
        
        # Update token usage if available
        if usage:
            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)
            total_tokens = usage.get("total_tokens", 0)
            
            state.metrics["tokens_prompt"] = state.metrics.get("tokens_prompt", 0) + prompt_tokens
            state.metrics["tokens_completion"] = state.metrics.get("tokens_completion", 0) + completion_tokens
            state.metrics["tokens_total"] = state.metrics.get("tokens_total", 0) + total_tokens
        
        # Update tool call counts
        if tool_calls:
            state.metrics["tool_calls_total"] = state.metrics.get("tool_calls_total", 0) + len(tool_calls)
            # Assume all tool calls are successful for now
            state.metrics["tool_calls_successful"] = state.metrics.get("tool_calls_successful", 0) + len(tool_calls)

    return ChatResponse(
        message=response_message,
        usage=usage,
        finish_reason=finish_reason,
    )


@router.post("/completions/stream")
async def chat_completion_stream(
    request: ChatRequest,
    api_key: str | None = Depends(verify_api_key),
    agent: Agent = Depends(get_agent),
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
    # Convert messages to internal format
    messages = []
    for msg in request.messages:
        # Convert dictionary tool_calls to ToolCall objects if present
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

        messages.append(
            Message(
                role=msg.role,
                content=msg.content,
                tool_calls=message_tool_calls,
                tool_call_id=msg.tool_call_id,
            )
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
    
    # Set agent messages to conversation history (excluding the last user message
    # since agent.run() will add it)
    agent.messages.clear()
    # Add all messages except the last user message
    for i, msg in enumerate(request.messages):
        if i == last_user_index:
            # Skip the last user message
            continue
        
        # Convert to Message format (reusing the conversion logic from above)
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
        
        agent.messages.append(
            Message(
                role=msg.role,
                content=msg.content,
                tool_calls=message_tool_calls,
                tool_call_id=msg.tool_call_id,
            )
        )

    # Track metrics for streaming requests
    if state.metrics:
        state.metrics["requests_total"] = state.metrics.get("requests_total", 0) + 1
    
    async def event_generator() -> AsyncIterator[str]:
        """Generate SSE events from agent events."""
        index = 0
        tool_calls_count = 0
        try:
            async for event in agent.run(user_input=user_input):
                chunk_type = "content"
                chunk_data = {"text": event.data}

                if event.type == EventType.TOOL_CALL_REQUEST:
                    chunk_type = "tool_call"
                    chunk_data = {"tool_call": event.data}
                    tool_calls_count += 1
                elif event.type == EventType.FINISHED:
                    chunk_type = "finished"
                    # Use actual finish reason from event data
                    reason = event.data if event.data else "stop"
                    chunk_data = {"reason": reason}
                    
                    # Extract usage information if available
                    if isinstance(event.data, dict) and "usage" in event.data:
                        usage = event.data["usage"]
                        # Update token usage metrics
                        if state.metrics and usage:
                            prompt_tokens = usage.get("prompt_tokens", 0)
                            completion_tokens = usage.get("completion_tokens", 0)
                            total_tokens = usage.get("total_tokens", 0)
                            
                            state.metrics["tokens_prompt"] = state.metrics.get("tokens_prompt", 0) + prompt_tokens
                            state.metrics["tokens_completion"] = state.metrics.get("tokens_completion", 0) + completion_tokens
                            state.metrics["tokens_total"] = state.metrics.get("tokens_total", 0) + total_tokens

                chunk = ChatStreamChunk(
                    type=chunk_type,
                    data=chunk_data,
                    index=index,
                )
                index += 1

                yield f"data: {chunk.model_dump_json()}\n\n"

            # Update successful request and tool call metrics
            if state.metrics:
                state.metrics["requests_successful"] = state.metrics.get("requests_successful", 0) + 1
                if tool_calls_count > 0:
                    state.metrics["tool_calls_total"] = state.metrics.get("tool_calls_total", 0) + tool_calls_count
                    state.metrics["tool_calls_successful"] = state.metrics.get("tool_calls_successful", 0) + tool_calls_count

            # Send final done event
            done_chunk = ChatStreamChunk(
                type="done",
                data={},
                index=index,
            )
            yield f"data: {done_chunk.model_dump_json()}\n\n"

        except Exception as e:
            # Update failed request metric
            if state.metrics:
                state.metrics["requests_failed"] = state.metrics.get("requests_failed", 0) + 1
            
            error_chunk = ChatStreamChunk(
                type="error",
                data={"error": str(e)},
                index=index,
            )
            yield f"data: {error_chunk.model_dump_json()}\n\n"

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
    api_key: str | None = Depends(verify_api_key),
    agent: Agent = Depends(get_agent),
    limit: int = Query(default=100, ge=1, le=1000, description="Maximum number of messages to return"),
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
    response_messages = []
    for msg in messages[-limit:]:  # Return most recent messages
        response_messages.append(
            ChatMessage(
                role=msg.role,
                content=msg.content or "",
                tool_calls=msg.tool_calls,
                tool_call_id=msg.tool_call_id,
            )
        )

    return response_messages


@router.delete("/history")
async def clear_chat_history(
    api_key: str | None = Depends(verify_api_key),
    agent: Agent = Depends(get_agent),
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
