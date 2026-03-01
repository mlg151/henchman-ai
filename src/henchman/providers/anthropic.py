"""Anthropic Claude provider.

This provider uses the Anthropic SDK to communicate with Claude models.
Unlike OpenAI-compatible APIs, Anthropic has its own message format.
"""

import asyncio
import json
import os
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Final

from anthropic import AsyncAnthropic, RateLimitError

from henchman.providers.base import (
    FinishReason,
    Message,
    ModelProvider,
    StreamChunk,
    ToolCall,
    ToolDeclaration,
)
from henchman.providers.utils import parse_finish_reason, validate_messages
from henchman.utils.ratelimit import AsyncRateLimiter
from henchman.utils.tokens import TokenCounter

__all__ = ["AnthropicProvider"]


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

    __slots__ = [
        "content",
        "thinking",
        "tool_calls",
        "finish_reason",
        "current_tool_id",
        "total_output_tokens_delta",
        "should_yield",
    ]

    def __init__(self, params: EventProcessingResultParams) -> None:
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

    def _should_yield(self) -> bool:
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
    max_tokens: int = 8192
    tokens_per_minute: int = 30000
    max_retries: int = 3


class _AnthropicStreamProcessor:
    """Processes Anthropic API streaming responses."""

    def __init__(self, provider: "AnthropicProvider") -> None:
        """Initialize the stream processor.
        
        Args:
            provider: The parent AnthropicProvider instance.
        """
        self._provider = provider
        self._default_model = provider.default_model

    async def process_stream(
        self,
        params: dict[str, Any],
        input_tokens: int,
    ) -> AsyncIterator[StreamChunk]:
        """Process the stream from Anthropic API.
        
        Args:
            params: Request parameters for the Anthropic API.
            input_tokens: Number of input tokens for rate limiting.
            
        Yields:
            StreamChunk objects as the response is generated.
        """
        total_output_tokens = 0
        async with self._provider._client.messages.stream(**params) as stream:
            pending_tool_calls: dict[str, dict[str, Any]] = {}
            current_tool_id: str | None = None

            async for event in stream:
                chunk = await self._process_event(
                    event, pending_tool_calls, current_tool_id, total_output_tokens
                )

                if chunk.current_tool_id is not None:
                    current_tool_id = chunk.current_tool_id

                if chunk.total_output_tokens_delta > 0:
                    total_output_tokens += chunk.total_output_tokens_delta

                if chunk.should_yield:
                    yield StreamChunk(
                        content=chunk.content,
                        tool_calls=chunk.tool_calls,
                        finish_reason=chunk.finish_reason,
                        thinking=chunk.thinking,
                    )

        # Record final usage
        await self._provider._rate_limiter.add_usage(input_tokens + total_output_tokens)

    async def _process_event(
        self,
        event: Any,
        pending_tool_calls: dict[str, dict[str, Any]],
        current_tool_id: str | None,
        total_output_tokens: int,
    ) -> "_EventProcessingResult":
        """Process a single event from the Anthropic stream."""
        if event.type == "content_block_start":
            return self._handle_content_block_start(event, pending_tool_calls)
        elif event.type == "content_block_delta":
            return self._handle_content_block_delta(
                event, current_tool_id, pending_tool_calls, total_output_tokens
            )
        elif event.type == "content_block_stop":
            return self._handle_content_block_stop()
        elif event.type == "message_delta":
            return self._handle_message_delta(event, pending_tool_calls)
        else:
            return _EventProcessingResult(EventProcessingResultParams())

    def _handle_content_block_start(
        self,
        event: Any,
        pending_tool_calls: dict[str, dict[str, Any]],
    ) -> "_EventProcessingResult":
        """Handle content_block_start event."""
        block = event.content_block
        if block.type == "tool_use":
            current_tool_id = block.id
            pending_tool_calls[block.id] = {
                "id": block.id,
                "name": block.name,
                "arguments": "",
            }
            params = EventProcessingResultParams(current_tool_id=current_tool_id)
            return _EventProcessingResult(params)

        return _EventProcessingResult(EventProcessingResultParams())

    def _handle_content_block_delta(
        self,
        event: Any,
        current_tool_id: str | None,
        pending_tool_calls: dict[str, dict[str, Any]],
        total_output_tokens: int,
    ) -> "_EventProcessingResult":
        """Handle content_block_delta event."""
        delta = event.delta
        content: str | None = None
        thinking: str | None = None
        tokens_delta = 0

        if delta.type == "text_delta":
            content = delta.text
            if content:  # Only count if content is not None/empty
                tokens_delta = TokenCounter.count_text(content, model=self._default_model)
        elif delta.type == "thinking_delta":
            thinking = delta.thinking
            if thinking:  # Only count if thinking is not None/empty
                tokens_delta = TokenCounter.count_text(thinking, model=self._default_model)
        elif delta.type == "input_json_delta" and current_tool_id:
            pending_tool_calls[current_tool_id]["arguments"] += delta.partial_json
            tokens_delta = TokenCounter.count_text(delta.partial_json, model=self._default_model)

        params = EventProcessingResultParams(
            content=content,
            thinking=thinking,
            total_output_tokens_delta=tokens_delta,
        )
        return _EventProcessingResult(params)

    def _handle_content_block_stop(self) -> "_EventProcessingResult":
        """Handle content_block_stop event."""
        params = EventProcessingResultParams(current_tool_id=None)
        return _EventProcessingResult(params)

    def _handle_message_delta(
        self,
        event: Any,
        pending_tool_calls: dict[str, dict[str, Any]],
    ) -> "_EventProcessingResult":
        """Handle message_delta event."""
        finish_reason = self._provider._parse_finish_reason(event.delta.stop_reason)
        tool_calls: list[ToolCall] | None = None

        if finish_reason == FinishReason.TOOL_CALLS and pending_tool_calls:
            tool_calls = self._build_tool_calls_from_pending(pending_tool_calls)

        params = EventProcessingResultParams(
            finish_reason=finish_reason,
            tool_calls=tool_calls,
        )
        return _EventProcessingResult(params)

    def _build_tool_calls_from_pending(
        self,
        pending_tool_calls: dict[str, dict[str, Any]],
    ) -> list[ToolCall]:
        """Build ToolCall objects from pending tool call data."""
        tool_calls = []
        for tc_data in pending_tool_calls.values():
            try:
                arguments = (
                    json.loads(tc_data["arguments"])
                    if tc_data["arguments"]
                    else {}
                )
            except json.JSONDecodeError:
                arguments = {}

            tool_calls.append(
                ToolCall(
                    id=tc_data["id"],
                    name=tc_data["name"],
                    arguments=arguments,
                )
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
        self,
        api_key: str | None = None,
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 8192,
        tokens_per_minute: int = 30000,
        max_retries: int = 3,
    ) -> None:
        """Initialize the Anthropic provider.

        Args:
            api_key: API key for authentication. Defaults to ANTHROPIC_API_KEY env var.
            model: Default model to use.
            max_tokens: Maximum tokens in response.
            tokens_per_minute: Maximum tokens per minute (rate limit).
            max_retries: Maximum number of retries for rate limits.
        """
        config = AnthropicProviderConfig(
            api_key=api_key,
            model=model,
            max_tokens=max_tokens,
            tokens_per_minute=tokens_per_minute,
            max_retries=max_retries,
        )
        self._initialize_from_config(config)

    def _initialize_from_config(self, config: AnthropicProviderConfig) -> None:
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
    def name(self) -> str:
        """The unique name of this provider."""
        return "anthropic"

    @staticmethod
    def list_models() -> list[str]:
        """List available Claude models.

        Returns:
            List of model names.
        """
        return ANTHROPIC_MODELS.copy()

    def _format_tool(self, tool: ToolDeclaration) -> dict[str, Any]:
        """Format a tool declaration for the Anthropic API."""
        return {
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.parameters,
        }

    def _format_messages(self, messages: list[Message]) -> tuple[str | None, list[dict[str, Any]]]:
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
                system_prompt = self._extract_system_prompt(msg)
                continue

            formatted_message = self._format_message_based_on_type(msg)
            if formatted_message:
                formatted.append(formatted_message)

        return system_prompt, formatted

    def _extract_system_prompt(self, message: Message) -> str | None:
        """Extract system prompt from a system message.
        
        Args:
            message: The system message.
            
        Returns:
            The system prompt content or None.
        """
        return message.content

    def _format_message_based_on_type(self, message: Message) -> dict[str, Any] | None:
        """Format a message based on its role and content.
        
        Args:
            message: The message to format.
            
        Returns:
            Formatted message dictionary or None if message should be skipped.
        """
        if message.role == "tool" and message.tool_call_id:
            return self._format_tool_result_message(message)
        elif message.role == "assistant" and message.tool_calls:
            return self._format_assistant_message_with_tool_calls(message)
        else:
            return self._format_regular_message(message)

    def _format_tool_result_message(self, message: Message) -> dict[str, Any]:
        """Format a tool result message for Anthropic API.
        
        Args:
            message: The tool result message.
            
        Returns:
            Formatted message dictionary.
        """
        return {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": message.tool_call_id,
                    "content": message.content or "",
                }
            ],
        }

    def _format_assistant_message_with_tool_calls(self, message: Message) -> dict[str, Any]:
        """Format an assistant message with tool calls for Anthropic API.
        
        Args:
            message: The assistant message with tool calls.
            
        Returns:
            Formatted message dictionary.
        """
        content: list[dict[str, Any]] = []

        if message.content:
            content.append({"type": "text", "text": message.content})

        for tc in message.tool_calls or []:
            content.append(
                {
                    "type": "tool_use",
                    "id": tc.id,
                    "name": tc.name,
                    "input": tc.arguments,
                }
            )

        return {
            "role": message.role,
            "content": content,
        }

    def _format_regular_message(self, message: Message) -> dict[str, Any]:
        """Format a regular message (user or assistant without tool calls).
        
        Args:
            message: The message to format.
            
        Returns:
            Formatted message dictionary.
        """
        return {
            "role": message.role,
            "content": message.content or "",
        }

    def _parse_finish_reason(self, stop_reason: str | None) -> FinishReason | None:
        """Parse Anthropic stop reason to our enum."""
        anthropic_mapping: dict[str, FinishReason] = {
            "end_turn": FinishReason.STOP,
            "stop_sequence": FinishReason.STOP,
            "tool_use": FinishReason.TOOL_CALLS,
            "max_tokens": FinishReason.LENGTH,
        }
        return parse_finish_reason(stop_reason, anthropic_mapping)

    async def chat_completion_stream(
        self,
        messages: list[Message],
        tools: list[ToolDeclaration] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[StreamChunk]:
        """Stream a chat completion from Claude.

        Args:
            messages: The conversation history.
            tools: Optional list of tools available to the model.
            **kwargs: Additional parameters passed to the API.

        Yields:
            StreamChunk objects as the response is generated.
        """
        self._validate_messages(messages)

        system_prompt, formatted_messages = self._format_messages(messages)
        messages = self._validate_and_repair_message_sequence(messages, system_prompt, formatted_messages)

        params = self._prepare_request_params(
            system_prompt, formatted_messages, tools, kwargs
        )

        input_tokens = TokenCounter.count_messages(messages, model=self.default_model)

        async for chunk in self._stream_with_retry(params, input_tokens):
            yield chunk

    def _validate_messages(self, messages: list[Message]) -> None:
        """Validate that messages are not empty and have appropriate content."""
        validate_messages(messages)

    def _validate_and_repair_message_sequence(
        self,
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
            system_prompt, formatted_messages = self._format_messages(messages)

        return messages

    def _prepare_request_params(
        self,
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
            params["tools"] = [self._format_tool(t) for t in tools]

        return params

    async def _stream_with_retry(
        self,
        params: dict[str, Any],
        input_tokens: int,
    ) -> AsyncIterator[StreamChunk]:
        """Stream with retry logic for rate limits."""
        retries = 0

        while True:
            try:
                await self._rate_limiter.wait_for_capacity(input_tokens)

                async for chunk in self._process_stream(params, input_tokens):
                    yield chunk

                break  # Success, exit retry loop

            except RateLimitError:
                retries += 1
                if retries > self.max_retries:
                    raise

                wait_time = 5.0 * (2 ** (retries - 1))  # Default backoff

                from rich.console import Console
                Console().print(
                    f"[yellow]Rate limit reached (429). Retrying in {wait_time:.1f}s... "
                    f"(Attempt {retries}/{self.max_retries})[/yellow]"
                )

                await asyncio.sleep(wait_time)

    async def _process_stream(
        self,
        params: dict[str, Any],
        input_tokens: int,
    ) -> AsyncIterator[StreamChunk]:
        """Process the stream from Anthropic API."""
        async for chunk in self._stream_processor.process_stream(params, input_tokens):
            yield chunk

    async def _process_event(
        self,
        event: Any,
        pending_tool_calls: dict[str, dict[str, Any]],
        current_tool_id: str | None,
        total_output_tokens: int,
    ) -> "_EventProcessingResult":
        """Process a single event from the Anthropic stream."""
        if event.type == "content_block_start":
            return self._handle_content_block_start(event, pending_tool_calls)
        elif event.type == "content_block_delta":
            return self._handle_content_block_delta(
                event, current_tool_id, pending_tool_calls, total_output_tokens
            )
        elif event.type == "content_block_stop":
            return self._handle_content_block_stop()
        elif event.type == "message_delta":
            return self._handle_message_delta(event, pending_tool_calls)
        else:
            return _EventProcessingResult(EventProcessingResultParams())

    def _handle_content_block_start(
        self,
        event: Any,
        pending_tool_calls: dict[str, dict[str, Any]],
    ) -> "_EventProcessingResult":
        """Handle content_block_start event."""
        block = event.content_block
        if block.type == "tool_use":
            current_tool_id = block.id
            pending_tool_calls[block.id] = {
                "id": block.id,
                "name": block.name,
                "arguments": "",
            }
            params = EventProcessingResultParams(current_tool_id=current_tool_id)
            return _EventProcessingResult(params)

        return _EventProcessingResult(EventProcessingResultParams())

    def _handle_content_block_delta(
        self,
        event: Any,
        current_tool_id: str | None,
        pending_tool_calls: dict[str, dict[str, Any]],
        total_output_tokens: int,
    ) -> "_EventProcessingResult":
        """Handle content_block_delta event."""
        delta = event.delta
        content: str | None = None
        thinking: str | None = None
        tokens_delta = 0

        if delta.type == "text_delta":
            content = delta.text
            if content:  # Only count if content is not None/empty
                tokens_delta = TokenCounter.count_text(content, model=self.default_model)
        elif delta.type == "thinking_delta":
            thinking = delta.thinking
            if thinking:  # Only count if thinking is not None/empty
                tokens_delta = TokenCounter.count_text(thinking, model=self.default_model)
        elif delta.type == "input_json_delta" and current_tool_id:
            pending_tool_calls[current_tool_id]["arguments"] += delta.partial_json
            tokens_delta = TokenCounter.count_text(delta.partial_json, model=self.default_model)

        params = EventProcessingResultParams(
            content=content,
            thinking=thinking,
            total_output_tokens_delta=tokens_delta,
        )
        return _EventProcessingResult(params)

    def _handle_content_block_stop(self) -> "_EventProcessingResult":
        """Handle content_block_stop event."""
        params = EventProcessingResultParams(current_tool_id=None)
        return _EventProcessingResult(params)

    def _handle_message_delta(
        self,
        event: Any,
        pending_tool_calls: dict[str, dict[str, Any]],
    ) -> "_EventProcessingResult":
        """Handle message_delta event."""
        finish_reason = self._parse_finish_reason(event.delta.stop_reason)
        tool_calls: list[ToolCall] | None = None

        if finish_reason == FinishReason.TOOL_CALLS and pending_tool_calls:
            tool_calls = self._build_tool_calls_from_pending(pending_tool_calls)

        params = EventProcessingResultParams(
            finish_reason=finish_reason,
            tool_calls=tool_calls,
        )
        return _EventProcessingResult(params)

    def _build_tool_calls_from_pending(
        self,
        pending_tool_calls: dict[str, dict[str, Any]],
    ) -> list[ToolCall]:
        """Build ToolCall objects from pending tool call data."""
        tool_calls = []
        for tc_data in pending_tool_calls.values():
            try:
                arguments = (
                    json.loads(tc_data["arguments"])
                    if tc_data["arguments"]
                    else {}
                )
            except json.JSONDecodeError:
                arguments = {}

            tool_calls.append(
                ToolCall(
                    id=tc_data["id"],
                    name=tc_data["name"],
                    arguments=arguments,
                )
            )

        return tool_calls
