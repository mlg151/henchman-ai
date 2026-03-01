"""OpenAI-compatible provider base class.

This provider works with any API that follows the OpenAI chat completions format,
including DeepSeek, Together, Groq, Fireworks, and others.
"""

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from openai import APIStatusError, AsyncOpenAI

from henchman.providers.base import (
    ContextTooLargeError,
    FinishReason,
    Message,
    ModelProvider,
    StreamChunk,
    ToolCall,
    ToolDeclaration,
)
from henchman.providers.utils import validate_messages, parse_finish_reason

__all__ = ["OpenAICompatibleProvider"]

logger = logging.getLogger(__name__)


class OpenAICompatibleProvider(ModelProvider):
    """Base provider for OpenAI-compatible APIs."""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        default_model: str,
    ) -> None:
        """Initialize the provider.

        Args:
            api_key: API key for authentication.
            base_url: Base URL for the API.
            default_model: Default model to use for completions.
        """
        self.api_key = api_key
        self.base_url = base_url
        self.default_model = default_model
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    @property
    def name(self) -> str:
        """The unique name of this provider."""
        return "openai-compatible"

    def _format_tool(self, tool: ToolDeclaration) -> dict[str, Any]:
        """Format a tool declaration for the OpenAI API."""
        return {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            },
        }

    def _format_message(self, message: Message) -> dict[str, Any]:
        """Format a message for the OpenAI API."""
        result: dict[str, Any] = {
            "role": message.role,
            "content": message.content,
        }

        if message.reasoning_content:
            result["reasoning_content"] = message.reasoning_content

        if message.tool_calls:
            result["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments),
                    },
                }
                for tc in message.tool_calls
            ]

        if message.tool_call_id:
            result["tool_call_id"] = message.tool_call_id

        return result

    def _parse_finish_reason(self, reason: str | None) -> FinishReason | None:
        """Parse OpenAI finish reason to our enum."""
        # OpenAI uses standard mapping, so we can use the default
        return parse_finish_reason(reason)

    def _parse_tool_calls(self, tool_calls: list[Any] | None) -> list[ToolCall] | None:
        """Parse tool calls from the API response."""
        if not tool_calls:
            return None

        result = []
        for tc in tool_calls:
            try:
                arguments = json.loads(tc.function.arguments)
            except (json.JSONDecodeError, AttributeError):
                arguments = {}

            result.append(
                ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=arguments,
                )
            )
        return result if result else None

    async def chat_completion_stream(
        self,
        messages: list[Message],
        tools: list[ToolDeclaration] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[StreamChunk]:
        """Stream a chat completion from the model.

        Args:
            messages: The conversation history.
            tools: Optional list of tools available to the model.
            **kwargs: Additional parameters passed to the API.

        Yields:
            StreamChunk objects as the response is generated.
        """
        self._validate_messages(messages)
        logger.debug("OpenAICompatibleProvider.chat_completion_stream: Starting with %d messages", len(messages))

        try:
            messages = self._repair_message_sequence_if_needed(messages)
            params = self._build_request_params(messages, tools, kwargs)
            response = await self._make_api_request(params)

            async for chunk in self._process_stream_response(response):
                yield chunk

        except (ValueError, ContextTooLargeError, APIStatusError):
            # Re-raise validation, context too large, and API status errors
            raise
        except Exception as e:
            yield self._create_error_chunk(e)

    def _validate_messages(self, messages: list[Message]) -> None:
        """Validate that messages are not empty and have content where required.

        Args:
            messages: The conversation history to validate.

        Raises:
            ValueError: If messages are empty or have invalid content.
        """
        validate_messages(messages)

    def _repair_message_sequence_if_needed(self, messages: list[Message]) -> list[Message]:
        """Repair message sequence if it's invalid to prevent API errors.

        Args:
            messages: The conversation history.

        Returns:
            The repaired message sequence.
        """
        from henchman.utils.validation import (
            is_valid_message_sequence,
            repair_message_sequence,
        )

        if not is_valid_message_sequence(messages):
            return repair_message_sequence(messages)
        return messages

    def _build_request_params(
        self,
        messages: list[Message],
        tools: list[ToolDeclaration] | None,
        kwargs: dict[str, Any]
    ) -> dict[str, Any]:
        """Build the request parameters for the API call.

        Args:
            messages: The conversation history.
            tools: Optional list of tools available to the model.
            kwargs: Additional parameters passed to the API.

        Returns:
            The request parameters dictionary.
        """
        params: dict[str, Any] = {
            "model": kwargs.pop("model", self.default_model),
            "messages": [self._format_message(m) for m in messages],
            "stream": True,
            **kwargs,
        }

        if tools:
            params["tools"] = [self._format_tool(t) for t in tools]

        return params

    async def _make_api_request(self, params: dict[str, Any]) -> Any:
        """Make the API request with error handling for context too large errors.

        Args:
            params: The request parameters.

        Returns:
            The API response.

        Raises:
            ContextTooLargeError: If the request is too large (413 error).
            APIStatusError: For other API errors.
        """
        try:
            return await self._client.chat.completions.create(**params)
        except APIStatusError as e:
            if e.status_code == 413:
                raise ContextTooLargeError(
                    "Request too large. Try using start_line/end_line when reading "
                    "files to limit context size, or start a new conversation."
                ) from e
            raise

    async def _process_stream_response(self, response: Any) -> AsyncIterator[StreamChunk]:
        """Process the streaming response and yield StreamChunk objects.

        Args:
            response: The API response stream.

        Yields:
            StreamChunk objects as the response is generated.
        """
        pending_tool_calls: dict[int, dict[str, Any]] = {}

        async for chunk in response:
            if not chunk.choices:
                continue

            choice = chunk.choices[0]
            delta = choice.delta

            # Handle content and thinking
            content = getattr(delta, "content", None)
            thinking = getattr(delta, "reasoning_content", None)

            # Handle tool calls
            tool_calls = None
            if hasattr(delta, "tool_calls") and delta.tool_calls:
                self._update_pending_tool_calls(pending_tool_calls, delta.tool_calls)

            # Handle finish reason
            finish_reason = self._parse_finish_reason(choice.finish_reason)

            # If we're done and have pending tool calls, emit them
            if finish_reason and pending_tool_calls:
                tool_calls = self._build_tool_calls_from_pending(pending_tool_calls)

            # Extract usage information if available
            usage = self._extract_usage_info(chunk)

            yield StreamChunk(
                content=content,
                tool_calls=tool_calls,
                finish_reason=finish_reason,
                thinking=thinking,
                usage=usage,
            )

    def _update_pending_tool_calls(
        self,
        pending_tool_calls: dict[int, dict[str, Any]],
        tool_call_deltas: list[Any]
    ) -> None:
        """Update pending tool calls with new delta information.

        Args:
            pending_tool_calls: Dictionary tracking tool calls across chunks.
            tool_call_deltas: List of tool call delta objects from the API.
        """
        for tc_delta in tool_call_deltas:
            idx = tc_delta.index
            if idx not in pending_tool_calls:
                pending_tool_calls[idx] = {
                    "id": tc_delta.id or "",
                    "name": "",
                    "arguments": "",
                }

            if tc_delta.id:
                pending_tool_calls[idx]["id"] = tc_delta.id
            if tc_delta.function:
                if tc_delta.function.name:
                    pending_tool_calls[idx]["name"] = tc_delta.function.name
                if tc_delta.function.arguments:
                    pending_tool_calls[idx]["arguments"] += tc_delta.function.arguments

    def _build_tool_calls_from_pending(
        self,
        pending_tool_calls: dict[int, dict[str, Any]]
    ) -> list[ToolCall]:
        """Build ToolCall objects from pending tool call data.

        Args:
            pending_tool_calls: Dictionary tracking tool calls across chunks.

        Returns:
            List of ToolCall objects.
        """
        tool_calls = []
        for tc_data in pending_tool_calls.values():
            try:
                arguments = json.loads(tc_data["arguments"])
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

    def _extract_usage_info(self, chunk: Any) -> dict[str, int] | None:
        """Extract usage information from the chunk if available.

        Args:
            chunk: The API response chunk.

        Returns:
            Usage dictionary or None if not available.
        """
        if hasattr(chunk, 'usage') and chunk.usage:
            return {
                'prompt_tokens': chunk.usage.prompt_tokens,
                'completion_tokens': chunk.usage.completion_tokens,
                'total_tokens': chunk.usage.total_tokens,
            }
        return None

    def _create_error_chunk(self, error: Exception) -> StreamChunk:
        """Create an error StreamChunk for API/network errors.

        Args:
            error: The exception that occurred.

        Returns:
            An error StreamChunk.
        """
        logger.debug("OpenAICompatibleProvider: Caught exception: %s", error)
        from henchman.providers.base import FinishReason
        return StreamChunk(
            content=f"❌ Provider Error: {error}",
            finish_reason=FinishReason.STOP,
        )
