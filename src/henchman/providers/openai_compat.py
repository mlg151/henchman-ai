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
        if reason is None:
            return None
        mapping = {
            "stop": FinishReason.STOP,
            "tool_calls": FinishReason.TOOL_CALLS,
            "length": FinishReason.LENGTH,
            "content_filter": FinishReason.CONTENT_FILTER,
        }
        return mapping.get(reason, FinishReason.STOP)

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
        # Validation errors should be raised, not caught
        # Validate messages are not empty
        if not messages:
            raise ValueError("Messages list cannot be empty")

        # Validate each message has content (unless it's a tool call response)
        for message in messages:
            # Tool/function messages can have empty content
            if message.role in ["tool", "function"]:
                continue

            # Assistant messages can have empty content (e.g., when only tool calls are made)
            if message.role == "assistant":
                continue

            # All other messages must have non-empty content
            if not (message.content or "").strip():
                raise ValueError(f"Message with role '{message.role}' cannot have empty content")

        logger.debug("OpenAICompatibleProvider.chat_completion_stream: Starting with %d messages", len(messages))

        # Run the actual API call with error handling
        try:
            # Original implementation continues...

            # Build request parameters
            # Last-resort defense: validate and repair message sequence to
            # prevent 400 errors from the API about broken tool sequences.
            from henchman.utils.validation import (
                is_valid_message_sequence,
                repair_message_sequence,
            )

            if not is_valid_message_sequence(messages):
                messages = repair_message_sequence(messages)

            params: dict[str, Any] = {
                "model": kwargs.pop("model", self.default_model),
                "messages": [self._format_message(m) for m in messages],
                "stream": True,
                **kwargs,
            }

            if tools:
                params["tools"] = [self._format_tool(t) for t in tools]

            # Stream the response with error handling
            try:
                response = await self._client.chat.completions.create(**params)
            except APIStatusError as e:
                if e.status_code == 413:
                    raise ContextTooLargeError(
                        "Request too large. Try using start_line/end_line when reading "
                        "files to limit context size, or start a new conversation."
                    ) from e
                raise

            # Track tool calls across chunks (they come in pieces)
            pending_tool_calls: dict[int, dict[str, Any]] = {}

            async for chunk in response:
                if not chunk.choices:
                    continue

                choice = chunk.choices[0]
                delta = choice.delta

                # Handle content
                content = getattr(delta, "content", None)

                # Handle thinking (for reasoning models)
                thinking = getattr(delta, "reasoning_content", None)

                # Handle tool calls (they come incrementally)
                tool_calls = None
                if hasattr(delta, "tool_calls") and delta.tool_calls:
                    for tc_delta in delta.tool_calls:
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

                # Handle finish reason
                finish_reason = self._parse_finish_reason(choice.finish_reason)

                # If we're done and have pending tool calls, emit them
                if finish_reason and pending_tool_calls:
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

                # Extract usage information if available
                usage = None
                if hasattr(chunk, 'usage') and chunk.usage:
                    usage = {
                        'prompt_tokens': chunk.usage.prompt_tokens,
                        'completion_tokens': chunk.usage.completion_tokens,
                        'total_tokens': chunk.usage.total_tokens,
                    }

                yield StreamChunk(
                    content=content,
                    tool_calls=tool_calls,
                    finish_reason=finish_reason,
                    thinking=thinking,
                    usage=usage,
                )

        except (ValueError, ContextTooLargeError, APIStatusError):
            # Re-raise validation, context too large, and API status errors
            raise
        except Exception as e:
            logger.debug("OpenAICompatibleProvider: Caught exception: %s", e)
            # Yield an error StreamChunk for API/network errors
            from henchman.providers.base import FinishReason
            yield StreamChunk(
                content=f"❌ Provider Error: {e}",
                finish_reason=FinishReason.STOP,
            )
