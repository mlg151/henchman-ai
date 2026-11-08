"""Anthropic Claude provider.

This provider uses the Anthropic SDK to communicate with Claude models.
Unlike OpenAI-compatible APIs, Anthropic has its own message format.
"""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import aclosing, asynccontextmanager
from copy import deepcopy
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
from henchman.providers.continuation import (
    ContinuationAccumulator,
    ContinuationEnvelope,
    ProviderContinuationError,
    request_continuation_binding,
    validate_continuations,
)
from henchman.providers.request_budget import (
    OutputBudget,
    estimate_serialized_input,
    validate_output_tokens,
)
from henchman.providers.runtime_budget import budget_attempt, prepare_budget_operation
from henchman.providers.schema_projections import project_tool_parameters
from henchman.providers.usage import UsageReport, token_count, usage_field
from henchman.providers.utils import parse_finish_reason, parse_tool_arguments, validate_messages
from henchman.utils.exception_evidence import exception_text
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
        "input_schema": project_tool_parameters(tool.parameters, "anthropic"),
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
    from henchman.utils.tool_results import tool_message_content

    block: dict[str, Any] = {
        "type": "tool_result", "tool_use_id": message.tool_call_id,
        "content": tool_message_content(message.content, message.tool_result),
    }
    if message.tool_result is not None and "success" in message.tool_result:
        block["is_error"] = not message.tool_result["success"]
    return {
        "role": "user",
        "content": [block],
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
    if message.continuation is not None:
        envelope = ContinuationEnvelope.from_dict(message.continuation)
        return {"role": role, "content": envelope.payload()}
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
    if block.type == "text":
        return _EventProcessingResult(EventProcessingResultParams(content=block.text or None))
    if block.type == "thinking":
        return _EventProcessingResult(EventProcessingResultParams(thinking=block.thinking or None))
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


def _build_stream_chunk(
    result: _EventProcessingResult, usage: dict[str, int] | None = None,
) -> StreamChunk | None:
    """Convert an _EventProcessingResult into a StreamChunk, or None if nothing to yield."""
    if not result.should_yield and usage is None:
        return None
    return StreamChunk(
        content=result.content,
        tool_calls=result.tool_calls,
        finish_reason=result.finish_reason,
        thinking=result.thinking,
        usage=usage,
    )


def _update_usage(event: Any, counts: dict[str, int]) -> dict[str, int] | None:
    """Normalize Anthropic cumulative counts, including all input cache subsets."""
    if event.type == "message_start":
        usage = usage_field(usage_field(event, "message"), "usage")
    elif event.type == "message_delta":
        usage = usage_field(event, "usage")
    else:
        return None
    if usage is None:
        return None
    for name in ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"):
        count = token_count(usage, name)
        if count is not None:
            counts[name] = count
    prompt = counts.get("input_tokens")
    cached = counts.get("cache_read_input_tokens")
    created = counts.get("cache_creation_input_tokens")
    if prompt is not None:
        prompt += (cached or 0) + (created or 0)
    return UsageReport(
        prompt_tokens=prompt,
        completion_tokens=counts.get("output_tokens"),
        cached_tokens=cached,
        cache_creation_tokens=created,
        source="reported",
    ).to_counts() or None


def _raise_if_retries_exhausted(
    retries: int,
    max_retries: int,
    exc: RateLimitError,
) -> None:
    """Raise *exc* if the retry limit has been reached."""
    if retries > max_retries:
        raise exc


@asynccontextmanager
async def _stream_context(manager: Any, *, provider: Any = None) -> AsyncIterator[Any]:
    """Preserve the primary stream error when SDK context cleanup also fails."""
    from henchman.core.failure_evidence import failure_evidence_redactor

    evidence = failure_evidence_redactor(provider)
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
        logger.error("Failed to close Anthropic stream after an error: %s", exception_text(
            exc, failure_evidence_redactor(provider, redactor=evidence), include_traceback=True,
        ))
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
        *, client: Any | None = None, binding: dict[str, str] | None = None,
    ) -> AsyncGenerator[StreamChunk]:
        """Process the stream from Anthropic API.

        Args:
            params: Request parameters for the Anthropic API.
            input_tokens: Number of input tokens for rate limiting.

        Yields:
            StreamChunk objects as the response is generated.
        """
        total_output_tokens = 0
        usage_counts: dict[str, int] = {}
        client = client if client is not None else self._provider._client
        binding = binding if binding is not None else request_continuation_binding(self._provider, params)
        opaque = False
        finished: StreamChunk | None = None
        stopped = False
        latest_usage: dict[str, int] | None = None
        accumulator = ContinuationAccumulator()
        try:
            async with _stream_context(client.messages.stream(**params), provider=self._provider) as stream:
                pending_tool_calls: dict[str, dict[str, Any]] = {}
                current_tool_id: str | None = None

                async for event in stream:
                    if finished is not None and event.type not in {"message_delta", "message_stop"}:
                        raise ProviderContinuationError("continuation_after_finish",
                            continuation=ContinuationEnvelope.unavailable(binding).to_dict() if binding else None)
                    if event.type == "message_start":
                        initial = getattr(event.message, "content", None)
                        if isinstance(initial, list) and initial:
                            raise ProviderContinuationError("unsupported_initial_content",
                                continuation=ContinuationEnvelope.unavailable(binding).to_dict() if binding else None)
                    stopped = stopped or event.type == "message_stop"
                    if event.type == "content_block_start":
                        kind = event.content_block.type
                        if kind not in {"text", "tool_use", "thinking", "redacted_thinking"}:
                            raise ProviderContinuationError("unsupported_continuation_block")
                        if not opaque and kind in {"thinking", "redacted_thinking"} and binding is not None:
                            yield StreamChunk(continuation=ContinuationEnvelope.unavailable(binding).to_dict())
                        opaque = opaque or kind in {"thinking", "redacted_thinking"}
                        if opaque:
                            accumulator.add(event.content_block.model_dump(exclude_none=True))
                    elif opaque and event.type == "content_block_delta":
                        accumulator.add(event.delta.model_dump(exclude_none=True))
                    usage = _update_usage(event, usage_counts)
                    if usage is not None:
                        latest_usage = usage
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

                    stream_chunk = _build_stream_chunk(chunk, usage)
                    if stream_chunk is not None:
                        if stream_chunk.finish_reason is not None:
                            if finished is not None and stream_chunk.finish_reason != finished.finish_reason:
                                raise ProviderContinuationError("inconsistent_stream_finish")
                            if finished is None:
                                finished = stream_chunk
                        else:
                            yield stream_chunk
                if opaque:
                    final_message = await stream.get_final_message()
                    if finished is None or binding is None or not stopped:
                        raise ProviderContinuationError("incomplete_continuation")
                    blocks = [block.model_dump(exclude_none=True) for block in final_message.content]
                    finished.continuation = ContinuationEnvelope.from_payload(binding, blocks).to_dict()
                    if finished.finish_reason == FinishReason.TOOL_CALLS:
                        finished.tool_calls = [ToolCall(block["id"], block["name"], block["input"]) for block in blocks if block["type"] == "tool_use"]
                if finished is not None:
                    if latest_usage is not None:
                        finished.usage = latest_usage
                        finished.usage_source = "reported"
                    yield finished
        except BaseException as exc:
            if opaque and binding is not None:
                unavailable = ContinuationEnvelope.unavailable(binding).to_dict()
                if isinstance(exc, ProviderContinuationError):
                    exc.continuation = unavailable
                elif isinstance(exc, Exception):
                    raise ProviderContinuationError("incomplete_continuation", continuation=unavailable) from None
            raise

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

    supports_run_budget = True

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
        kwargs = deepcopy(kwargs)
        effective_model = (kwargs.get("extra_body") or {}).get("model", kwargs.get("model", self.default_model))
        validate_continuations(messages, self, model=effective_model)

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

        binding = request_continuation_binding(self, params)
        validate_continuations(messages, self, model=effective_model, request_binding=binding)
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
        params = deepcopy(params)
        retries = 0
        operation = prepare_budget_operation(self, params)
        binding = request_continuation_binding(self, params)
        client = self._client.with_options(max_retries=0) if operation is not None else self._client

        while True:
            try:
                with budget_attempt(operation) as attempt:
                    await self._rate_limiter.wait_for_capacity(input_tokens)
                    if attempt is not None:
                        attempt.start()
                    stream = self._process_stream(params, input_tokens, client=client, binding=binding)
                    async with aclosing(stream) as chunks:
                        async for chunk in chunks:
                            if attempt is not None:
                                attempt.observe(chunk)
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
        *, client: Any | None = None, binding: dict[str, str] | None = None,
    ) -> AsyncGenerator[StreamChunk]:
        """Process the stream from Anthropic API."""
        stream = self._stream_processor.process_stream(params, input_tokens, client=client, binding=binding)
        async with aclosing(stream) as chunks:
            async for chunk in chunks:
                yield chunk
