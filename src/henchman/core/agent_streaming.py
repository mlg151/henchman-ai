"""Streaming response handling for the Agent.

Provides the StreamState dataclass for accumulating streaming
responses, and a generator function for producing agent events.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from henchman.core.events import AgentEvent, EventType
from henchman.providers.base import (
    FinishReason,
    Message,
    ModelProvider,
    StreamChunk,
    ToolCall,
    ToolDeclaration,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


def _make_event(
    event_type: EventType,
    data: Any = None,
    source_agent: str | None = None,
) -> AgentEvent:
    """Create an AgentEvent with the given source agent.

    Args:
        event_type: The type of event to create.
        data: Optional data payload for the event.
        source_agent: Optional agent identity ID.

    Returns:
        A new AgentEvent instance.
    """
    return AgentEvent(type=event_type, data=data, source_agent=source_agent)


@dataclass
class StreamContext:
    """Groups parameters needed for a streaming API call.

    Attributes:
        provider: The model provider to stream from.
        api_messages: Messages to send to the provider.
        history: Full conversation history (mutated on finish).
        tool_declarations: Tool declarations for the provider.
        source_agent: Agent identity ID for events.
    """

    provider: ModelProvider
    api_messages: list[Message]
    history: list[Message]
    tool_declarations: list[ToolDeclaration]
    source_agent: str | None = None


@dataclass
class StreamState:
    """Accumulates data from a streaming provider response.

    Attributes:
        content: Accumulated text content.
        thinking: Accumulated thinking/reasoning content.
        tool_calls: Accumulated tool call requests.
        usage: Token usage information from the last chunk.
        content_yielded: Whether any content has been yielded to the caller.
        finish_reason: The finish reason from the stream.
    """

    content: str = ""
    thinking: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: dict[str, int] | None = None
    content_yielded: bool = False
    finish_reason: FinishReason | None = None

    def create_assistant_message(
        self: StreamState,
        chunk_tool_calls: list[ToolCall] | None = None,
    ) -> Message:
        """Create an assistant Message from accumulated state.

        Args:
            chunk_tool_calls: Tool calls from the final chunk, used as fallback.

        Returns:
            A Message with role 'assistant' and accumulated content.
        """
        calls = self.tool_calls or chunk_tool_calls
        return Message(
            role="assistant",
            content=self.content,
            tool_calls=calls or None,
            reasoning_content=self.thinking or None,
        )

    def create_finished_data(self: StreamState) -> str | dict[str, Any]:
        """Create data payload for the FINISHED event.

        Returns:
            A string finish reason, or dict with finish_reason and usage.
        """
        base = self.finish_reason.value if self.finish_reason else "Stream completed"
        if self.usage:
            return {"finish_reason": base, "usage": self.usage}
        return base

    def get_pending_tool_calls(
        self: StreamState,
        chunk_tool_calls: list[ToolCall] | None = None,
    ) -> list[ToolCall]:
        """Get tool calls to yield to the caller.

        Args:
            chunk_tool_calls: Tool calls from the final chunk, used as fallback.

        Returns:
            List of tool calls to yield.
        """
        return self.tool_calls or (chunk_tool_calls or [])

    def has_unreported_content(self: StreamState) -> bool:
        """Check if there is content that has not yet been yielded.

        Returns:
            True if content exists but has not been reported.
        """
        return bool(self.content and not self.content_yielded)


# ---------------------------------------------------------------------------
# Module-level helpers (not class methods → no Feature Envy)
# ---------------------------------------------------------------------------


def _accumulate_chunk(chunk: StreamChunk, state: StreamState) -> None:
    """Accumulate content, tool calls, and usage from a chunk.

    Args:
        chunk: The stream chunk to process.
        state: The accumulation state to update.
    """
    if chunk.thinking:
        state.thinking += chunk.thinking
    if chunk.content:
        state.content += chunk.content
    if chunk.tool_calls:
        state.tool_calls.extend(chunk.tool_calls)
    if chunk.usage:
        state.usage = chunk.usage


def _handle_finish(
    chunk: StreamChunk,
    state: StreamState,
    history: list[Message],
    source_agent: str | None,
) -> list[AgentEvent]:
    """Handle a chunk that carries a finish_reason.

    Args:
        chunk: The stream chunk with a finish reason.
        state: The accumulation state.
        history: Conversation history to append the assistant message to.
        source_agent: Agent identity ID for events.

    Returns:
        List of events to yield.
    """
    state.finish_reason = chunk.finish_reason
    assistant_msg = state.create_assistant_message(chunk.tool_calls)
    history.append(assistant_msg)
    events: list[AgentEvent] = []
    stop_reasons = (FinishReason.STOP, FinishReason.LENGTH, FinishReason.CONTENT_FILTER)
    if chunk.finish_reason in stop_reasons:
        if state.has_unreported_content():
            events.append(_make_event(EventType.CONTENT, state.content, source_agent))
    elif chunk.finish_reason == FinishReason.TOOL_CALLS:  # pragma: no branch
        events.extend(
            _make_event(EventType.TOOL_CALL_REQUEST, tc, source_agent)
            for tc in state.get_pending_tool_calls(chunk.tool_calls)
        )
    return events


async def generate_stream_events(
    ctx: StreamContext,
    state: StreamState,
    *,
    compacted: bool,
) -> AsyncIterator[AgentEvent]:
    """Generate agent events from a provider streaming response.

    Args:
        ctx: The streaming context with provider and messages.
        state: StreamState to accumulate response data into.
        compacted: Whether context was compacted this turn.

    Yields:
        AgentEvent instances for content, thinking, tool calls, errors, and finish.
    """
    if compacted:
        yield _make_event(
            EventType.CONTEXT_COMPACTED,
            {"message": "Context was compacted to fit model limits"},
            ctx.source_agent,
        )
    try:
        async for chunk in ctx.provider.chat_completion_stream(
            messages=ctx.api_messages,
            tools=ctx.tool_declarations,
        ):
            if chunk.thinking:
                yield _make_event(EventType.THOUGHT, chunk.thinking, ctx.source_agent)
            _accumulate_chunk(chunk, state)
            if chunk.finish_reason:
                for event in _handle_finish(chunk, state, ctx.history, ctx.source_agent):
                    yield event
            elif chunk.content:
                state.content_yielded = True
                yield _make_event(EventType.CONTENT, chunk.content, ctx.source_agent)
    except Exception as exc:
        yield _make_event(EventType.ERROR, f"Provider error: {exc}", ctx.source_agent)
    finally:
        yield _make_event(EventType.FINISHED, state.create_finished_data(), ctx.source_agent)
