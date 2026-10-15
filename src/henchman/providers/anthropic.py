"""Anthropic Claude provider.

This provider uses the Anthropic SDK to communicate with Claude models.
Unlike OpenAI-compatible APIs, Anthropic has its own message format.
"""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import aclosing, asynccontextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, AsyncIterator

from anthropic import AsyncAnthropic, RateLimitError

from henchman.providers.base import (
    FinishReason,
    Message,
    ModelProvider,
    StreamChunk,
    ToolCall,
    ToolDeclaration,
)
from henchman.providers.request_budget import (
    OutputBudget,
    estimate_serialized_input,
    validate_output_tokens,
)
from henchman.providers.utils import parse_finish_reason, parse_tool_arguments, validate_messages
from henchman.utils.ratelimit import AsyncRateLimiter
from henchman.utils.tokens import TokenCounter

__all__ = ["AnthropicProvider"]

logger = logging.getLogger(__name__)

# Constants
DEFAULT_MAX_TOKENS: Final[int] = 8192
DEFAULT_TOKENS_PER_MINUTE: Final[int] = 30000
DEFAULT_MAX_RETRIES: Final[int] = 3
DEFAULT_RETRY_BACKOFF_BASE: Final[float] = 5.0

# Mapping from Anthropic stop reasons to our FinishReason enum
ANTHROPIC_FINISH_REASON_MAPPING: Final[dict[str, FinishReason]] = {
    "end_turn": FinishReason.STOP,
    "stop_sequence": FinishReason.STOP,
    "tool_use": FinishReason.TOOL_CALLS,
    "max_tokens": FinishReason.LENGTH,
}


@dataclass
class EventProcessingResultParams:
    """Parameters for creating an EventProcessingResult."""

    content: str | None = None
    thinking: str | None = None
    tool_calls: list[ToolCall] | None = None
    finish_reason: FinishReason | None = None
    current_tool_id: str | None = None
    total_output_tokens_delta: int = 0


class _EventProcessingResult:
    """Result of processing a single Anthropic stream event."""

    __slots__ = (
        "content",
        "current_tool_id",
        "finish_reason",
        "should_yield",
        "thinking",
        "tool_calls",
        "total_output_tokens_delta",
    )

    def __init__(
        self: _EventProcessingResult,
        params: EventProcessingResultParams,
    ) -> None:
        """Initialize the event processing result.

        Args:
            params: Configuration parameters for the result.
        """
        self.content = params.content
        self.thinking = params.thinking
        self.tool_calls = params.tool_calls
        self.finish_reason = params.finish_reason
        self.current_tool_id = params.current_tool_id
        self.total_output_tokens_delta = params.total_output_tokens_delta
        self.should_yield = self._should_yield()

    def _should_yield(self: _EventProcessingResult) -> bool:
        """Determine if this result should yield a StreamChunk."""
        return (
            self.content is not None
            or self.thinking is not None
            or self.tool_calls is not None
            or self.finish_reason is not None
        )


# Available Claude models
ANTHROPIC_MODELS: Final[list[str]] = [
    "claude-opus-4-6",
    "claude-sonnet-4-20250514",
    "claude-3-7-sonnet-20250219",
    "claude-3-5-sonnet-20241022",
    "claude-3-5-haiku-20241022",
    "claude-3-opus-20240229",
    "claude-3-sonnet-20240229",
    "claude-3-haiku-20240307",
]


@dataclass
class AnthropicProviderConfig:
    """Configuration parameters for AnthropicProvider."""

    api_key: str | None = None
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = DEFAULT_MAX_TOKENS
    tokens_per_minute: int = DEFAULT_TOKENS_PER_MINUTE
    max_retries: int = DEFAULT_MAX_RETRIES


# ---------------------------------------------------------------------------
# Module-level helpers (not subject to Feature Envy checks)
# ---------------------------------------------------------------------------


def _format_tool_for_anthropic(tool: ToolDeclaration) -> dict[str, Any]:
    """Format a ToolDeclaration into the shape required by the Anthropic API."""
    return {
        "name": tool.name,
        "description": tool.description,
        "input_schema": tool.parameters,
    }


def _format_assistant_tool_call_message(message: Message) -> dict[str, Any]:
    """Build the Anthropic API payload for an assistant message that contains tool calls."""
    content: list[dict[str, Any]] = []
    if message.content:
        content.append({"type": "text", "text": message.content})
    content.extend(
        {
            "type": "tool_use",
            "id": tc.id,
            "name": tc.name,
            "input": tc.arguments,
        }
        for tc in (message.tool_calls or [])
    )
    return {"role": message.role, "content": content}


def _format_tool_result(message: Message) -> dict[str, Any]:
    """Build the Anthropic API payload for a tool result message."""
    return {
        "role": "user",
        "content": [
            {
                "type": "tool_result",
                "tool_use_id": message.tool_call_id,
                "content": message.content or "",
            },
        ],
    }


def _format_plain_message(message: Message) -> dict[str, Any]:
    """Build the Anthropic API payload for a plain user/assistant message."""
    return {
        "role": message.role,
        "content": message.content or "",
    }


def _format_message_by_role(message: Message) -> dict[str, Any] | None:
    """Select the correct formatter based on message role and content."""
    role = message.role
    if role == "tool" and message.tool_call_id:
        return _format_tool_result(message)
    if role == "assistant" and message.tool_calls:
        return _format_assistant_tool_call_message(message)
    return _format_plain_message(message)


def _handle_content_block_start_event(
    event: Any,
    pending_tool_calls: dict[str, dict[str, Any]],
) -> _EventProcessingResult:
    """Handle a content_block_start event from the Anthropic stream."""
    block = event.content_block
    if block.type == "tool_use":
        block_id = block.id
        pending_tool_calls[block_id] = {
            "id": block_id,
            "name": block.name,
            "arguments": "",
        }
        return _EventProcessingResult(
            EventProcessingResultParams(current_tool_id=block_id),
        )
    return _EventProcessingResult(EventProcessingResultParams())


def _handle_content_block_delta_event(
    event: Any,
    current_tool_id: str | None,
    pending_tool_calls: dict[str, dict[str, Any]],
    default_model: str,
) -> _EventProcessingResult:
    """Handle a content_block_delta event from the Anthropic stream."""
    delta = event.delta
    delta_type = delta.type
    content: str | None = None
    thinking: str | None = None
    tokens_delta = 0

    if delta_type == "text_delta":
        content = delta.text
        if content:
            tokens_delta = TokenCounter.count_text(content, model=default_model)
    elif delta_type == "thinking_delta":
        thinking = delta.thinking
        if thinking:
            tokens_delta = TokenCounter.count_text(thinking, model=default_model)
    elif delta_type == "input_json_delta" and current_tool_id:
        partial_json = delta.partial_json
        pending_tool_calls[current_tool_id]["arguments"] += partial_json
        tokens_delta = TokenCounter.count_text(partial_json, model=default_model)

    return _EventProcessingResult(
        EventProcessingResultParams(
            content=content,
            thinking=thinking,
            total_output_tokens_delta=tokens_delta,
        ),
    )


def _build_stream_chunk(result: _EventProcessingResult) -> StreamChunk | None:
    """Convert an _EventProcessingResult into a StreamChunk, or None if nothing to yield."""
    if not result.should_yield:
        return None
    return StreamChunk(
        content=result.content,
        tool_calls=result.tool_calls,
        finish_reason=result.finish_reason,
        thinking=result.thinking,
    )


def _raise_if_retries_exhausted(
    retries: int,
    max_retries: int,
    exc: RateLimitError,
) -> None:
    """Raise *exc* if the retry limit has been reached."""
    if retries > max_retries:
        raise exc


@asynccontextmanager
async def _stream_context(manager: Any) -> AsyncIterator[Any]:
    """Preserve the primary stream error when SDK context cleanup also fails."""
    primary_error: BaseException | None = None
    try:
        async with manager as stream:
            try:
                yield stream
            except BaseException as exc:
                primary_error = exc
                raise
    except Exception as exc:
        if primary_error is None or exc is primary_error:
            raise
        logger.exception("Failed to close Anthropic stream after an error")
        raise primary_error from None


class _AnthropicStreamProcessor:
    """Processes Anthropic API streaming responses."""

    def __init__(
        self: _AnthropicStreamProcessor,
        provider: AnthropicProvider,
    ) -> None:
        """Initialize the stream processor.

        Args:
            provider: The parent AnthropicProvider instance.
        """
        self._provider = provider
        self._default_model = provider.default_model

    async def process_stream(
        self: _AnthropicStreamProcessor,
        params: dict[str, Any],
        input_tokens: int,
    ) -> AsyncGenerator[StreamChunk]:
        """Process the stream from Anthropic API.

        Args:
            params: Request parameters for the Anthropic API.
            input_tokens: Number of input tokens for rate limiting.

        Yields:
            StreamChunk objects as the response is generated.
        """
        total_output_tokens = 0
        async with _stream_context(self._provider._client.messages.stream(**params)) as stream:
            pending_tool_calls: dict[str, dict[str, Any]] = {}
            current_tool_id: str | None = None

            async for event in stream:
                chunk = await self._process_event(
                    event,
                    pending_tool_calls,
                    current_tool_id,
                    total_output_tokens,
                )

                chunk_tool_id = chunk.current_tool_id
                if chunk_tool_id is not None:
                    current_tool_id = chunk_tool_id

                chunk_tokens_delta = chunk.total_output_tokens_delta
                if chunk_tokens_delta > 0:
                    total_output_tokens += chunk_tokens_delta

                stream_chunk = _build_stream_chunk(chunk)
                if stream_chunk is not None:
                    yield stream_chunk

        rate_limiter = self._provider._rate_limiter
        await rate_limiter.add_usage(input_tokens + total_output_tokens)

    async def _process_event(
        self: _AnthropicStreamProcessor,
        event: Any,
        pending_tool_calls: dict[str, dict[str, Any]],
        current_tool_id: str | None,
        total_output_tokens: int,
    ) -> _EventProcessingResult:
        """Process a single event from the Anthropic stream."""
        event_type = event.type
        if event_type == "content_block_start":
            return _handle_content_block_start_event(event, pending_tool_calls)
        if event_type == "content_block_delta":
            return _handle_content_block_delta_event(
                event,
                current_tool_id,
                pending_tool_calls,
                self._default_model,
            )
        if event_type == "content_block_stop":
            return self._handle_content_block_stop()
        if event_type == "message_delta":
            return self._handle_message_delta(event, pending_tool_calls)
        return _EventProcessingResult(EventProcessingResultParams())

    def _handle_content_block_stop(
        self: _AnthropicStreamProcessor,
    ) -> _EventProcessingResult:
        """Handle content_block_stop event."""
        return _EventProcessingResult(EventProcessingResultParams(current_tool_id=None))

    def _handle_message_delta(
        self: _AnthropicStreamProcessor,
        event: Any,
        pending_tool_calls: dict[str, dict[str, Any]],
    ) -> _EventProcessingResult:
        """Handle message_delta event."""
        finish_reason = parse_finish_reason(
            event.delta.stop_reason,
            ANTHROPIC_FINISH_REASON_MAPPING,
        )
        tool_calls: list[ToolCall] | None = None

        if finish_reason == FinishReason.TOOL_CALLS and pending_tool_calls:
            tool_calls = self._build_tool_calls_from_pending(pending_tool_calls)

        return _EventProcessingResult(
            EventProcessingResultParams(
                finish_reason=finish_reason,
                tool_calls=tool_calls,
            ),
        )

    def _build_tool_calls_from_pending(
        self: _AnthropicStreamProcessor,
        pending_tool_calls: dict[str, dict[str, Any]],
    ) -> list[ToolCall]:
        """Build ToolCall objects from pending tool call data."""
        tool_calls = []
        for tc_data in pending_tool_calls.values():
            arguments = parse_tool_arguments(tc_data["arguments"])

            tool_calls.append(
                ToolCall(
                    id=tc_data["id"],
                    name=tc_data["name"],
                    arguments=arguments,
                ),
            )

        return tool_calls


class AnthropicProvider(ModelProvider):
    """Provider for Anthropic Claude models.

    Uses the native Anthropic SDK for best compatibility with Claude features.

    Example:
        >>> provider = AnthropicProvider(api_key="your-api-key")
        >>> async for chunk in provider.chat_completion_stream(messages):
        ...     print(chunk.content, end="")
    """

    def __init__(
        self: AnthropicProvider,
        config: AnthropicProviderConfig | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the Anthropic provider.

        Args:
            config: Provider configuration. If None, one is built from ``kwargs``.
            **kwargs: Keyword arguments forwarded to ``AnthropicProviderConfig`` when
                ``config`` is not supplied (e.g. ``api_key``, ``model``,
                ``max_tokens``, ``tokens_per_minute``, ``max_retries``).
        """
        if config is None:
            config = AnthropicProviderConfig(**kwargs)
        self._initialize_from_config(config)

    def _initialize_from_config(
        self: AnthropicProvider,
        config: AnthropicProviderConfig,
    ) -> None:
        """Initialize provider from configuration object.

        Args:
            config: Configuration parameters.
        """
        self.api_key = config.api_key or os.getenv("ANTHROPIC_API_KEY", "")
        self.default_model = config.model
        self.max_tokens = config.max_tokens
        self.max_retries = config.max_retries
        self._client = AsyncAnthropic(api_key=self.api_key or "placeholder")
        self._rate_limiter = AsyncRateLimiter(config.tokens_per_minute)
        self._stream_processor = _AnthropicStreamProcessor(self)

    @property
    def name(self: AnthropicProvider) -> str:
        """The unique name of this provider."""
        return "anthropic"

    def prepare_output_budget(self, default_max_tokens: int) -> OutputBudget:
        """Reserve the configured native cap rather than the portable default."""
        cap = validate_output_tokens(self.max_tokens)
        return OutputBudget(cap, {"max_tokens": cap})

    def estimate_input_tokens(
        self, messages: list[Message], tools: list[ToolDeclaration] | None,
    ) -> int:
        """Estimate native system, message blocks and tool input schemas."""
        system, formatted = self._format_messages(messages)
        payload: dict[str, Any] = {"messages": formatted}
        if system:
            payload["system"] = system
        if tools:
            payload["tools"] = [_format_tool_for_anthropic(tool) for tool in tools]
        return estimate_serialized_input(payload, model=self.default_model)

    @staticmethod
    def list_models() -> list[str]:
        """List available Claude models.

        Returns:
            List of model names.
        """
        return ANTHROPIC_MODELS.copy()


    def _format_messages(
        self: AnthropicProvider,
        messages: list[Message],
    ) -> tuple[str | None, list[dict[str, Any]]]:
        """Format messages for the Anthropic API.

        Anthropic separates system messages from the conversation.

        Args:
            messages: The conversation history.

        Returns:
            Tuple of (system_prompt, formatted_messages).
        """
        system_prompt: str | None = None
        formatted: list[dict[str, Any]] = []

        for msg in messages:
            if msg.role == "system":
                system_prompt = msg.content
                continue

            formatted_message = _format_message_by_role(msg)
            if formatted_message:  # pragma: no branch
                formatted.append(formatted_message)

        return system_prompt, formatted





    async def chat_completion_stream(
        self: AnthropicProvider,
        messages: list[Message],
        tools: list[ToolDeclaration] | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[StreamChunk]:
        """Stream a chat completion from Claude.

        Args:
            messages: The conversation history.
            tools: Optional list of tools available to the model.
            **kwargs: Additional parameters passed to the API.

        Yields:
            StreamChunk objects as the response is generated.
        """
        validate_messages(messages)

        system_prompt, formatted_messages = self._format_messages(messages)
        messages = self._validate_and_repair_message_sequence(
            messages,
            system_prompt,
            formatted_messages,
        )

        params = self._prepare_request_params(
            system_prompt,
            formatted_messages,
            tools,
            kwargs,
        )

        input_tokens = TokenCounter.count_messages(messages, model=self.default_model)

        async with aclosing(self._stream_with_retry(params, input_tokens)) as chunks:
            async for chunk in chunks:
                yield chunk


    def _validate_and_repair_message_sequence(
        self: AnthropicProvider,
        messages: list[Message],
        system_prompt: str | None,
        formatted_messages: list[dict[str, Any]],
    ) -> list[Message]:
        """Validate and repair message sequence if needed."""
        from henchman.utils.validation import (
            is_valid_message_sequence,
            repair_message_sequence,
        )

        if not is_valid_message_sequence(messages):
            messages = repair_message_sequence(messages)
            _system_prompt, _formatted_messages = self._format_messages(messages)

        return messages

    def _prepare_request_params(
        self: AnthropicProvider,
        system_prompt: str | None,
        formatted_messages: list[dict[str, Any]],
        tools: list[ToolDeclaration] | None,
        kwargs: dict[str, Any],
    ) -> dict[str, Any]:
        """Prepare request parameters for the Anthropic API."""
        params: dict[str, Any] = {
            "model": kwargs.pop("model", self.default_model),
            "messages": formatted_messages,
            "max_tokens": kwargs.pop("max_tokens", self.max_tokens),
            **kwargs,
        }

        if system_prompt:
            params["system"] = system_prompt

        if tools:
            params["tools"] = [_format_tool_for_anthropic(t) for t in tools]

        return params

    async def _stream_with_retry(
        self: AnthropicProvider,
        params: dict[str, Any],
        input_tokens: int,
    ) -> AsyncGenerator[StreamChunk]:
        """Stream with retry logic for rate limits."""
        retries = 0

        while True:
            try:
                await self._rate_limiter.wait_for_capacity(input_tokens)

                async with aclosing(self._process_stream(params, input_tokens)) as chunks:
                    async for chunk in chunks:
                        yield chunk

                break  # Success, exit retry loop

            except RateLimitError as exc:
                retries += 1
                _raise_if_retries_exhausted(retries, self.max_retries, exc)
                wait_time = DEFAULT_RETRY_BACKOFF_BASE * (2 ** (retries - 1))
                await asyncio.sleep(wait_time)

    async def _process_stream(
        self: AnthropicProvider,
        params: dict[str, Any],
        input_tokens: int,
    ) -> AsyncGenerator[StreamChunk]:
        """Process the stream from Anthropic API."""
        async with aclosing(self._stream_processor.process_stream(params, input_tokens)) as chunks:
            async for chunk in chunks:
                yield chunk
