"""Anthropic Claude provider.

This provider uses the Anthropic SDK to communicate with Claude models.
Unlike OpenAI-compatible APIs, Anthropic has its own message format.
"""

import json
import os
from collections.abc import AsyncIterator
from typing import Any

from anthropic import AsyncAnthropic

from mlg.providers.base import (
    FinishReason,
    Message,
    ModelProvider,
    StreamChunk,
    ToolCall,
    ToolDeclaration,
)

__all__ = ["AnthropicProvider"]

# Available Claude models
ANTHROPIC_MODELS = [
    "claude-sonnet-4-20250514",
    "claude-3-7-sonnet-20250219",
    "claude-3-5-sonnet-20241022",
    "claude-3-5-haiku-20241022",
    "claude-3-opus-20240229",
    "claude-3-sonnet-20240229",
    "claude-3-haiku-20240307",
]


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
    ) -> None:
        """Initialize the Anthropic provider.

        Args:
            api_key: API key for authentication. Defaults to ANTHROPIC_API_KEY env var.
            model: Default model to use.
            max_tokens: Maximum tokens in response.
        """
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
        self.default_model = model
        self.max_tokens = max_tokens
        self._client = AsyncAnthropic(api_key=self.api_key or "placeholder")

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

    def _format_messages(
        self, messages: list[Message]
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

            content: list[dict[str, Any]] | str = msg.content or ""

            # Handle tool results
            if msg.role == "tool" and msg.tool_call_id:
                formatted.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": msg.tool_call_id,
                            "content": msg.content or "",
                        }
                    ],
                })
                continue

            # Handle assistant messages with tool calls
            if msg.role == "assistant" and msg.tool_calls:
                content = []
                if msg.content:
                    content.append({"type": "text", "text": msg.content})
                for tc in msg.tool_calls:
                    content.append({
                        "type": "tool_use",
                        "id": tc.id,
                        "name": tc.name,
                        "input": tc.arguments,
                    })

            formatted.append({
                "role": msg.role,
                "content": content,
            })

        return system_prompt, formatted

    def _parse_finish_reason(self, stop_reason: str | None) -> FinishReason | None:
        """Parse Anthropic stop reason to our enum."""
        if stop_reason is None:
            return None
        mapping = {
            "end_turn": FinishReason.STOP,
            "stop_sequence": FinishReason.STOP,
            "tool_use": FinishReason.TOOL_CALLS,
            "max_tokens": FinishReason.LENGTH,
        }
        return mapping.get(stop_reason, FinishReason.STOP)

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
        system_prompt, formatted_messages = self._format_messages(messages)

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

        async with self._client.messages.stream(**params) as stream:
            pending_tool_calls: dict[str, dict[str, Any]] = {}
            current_tool_id: str | None = None

            async for event in stream:
                content: str | None = None
                thinking: str | None = None
                tool_calls: list[ToolCall] | None = None
                finish_reason: FinishReason | None = None

                if event.type == "content_block_start":
                    block = event.content_block
                    if block.type == "tool_use":
                        current_tool_id = block.id
                        pending_tool_calls[block.id] = {
                            "id": block.id,
                            "name": block.name,
                            "arguments": "",
                        }

                elif event.type == "content_block_delta":
                    delta = event.delta
                    if delta.type == "text_delta":
                        content = delta.text
                    elif delta.type == "thinking_delta":
                        thinking = delta.thinking
                    elif delta.type == "input_json_delta" and current_tool_id:
                        pending_tool_calls[current_tool_id]["arguments"] += delta.partial_json

                elif event.type == "content_block_stop":
                    current_tool_id = None

                elif event.type == "message_delta":
                    finish_reason = self._parse_finish_reason(event.delta.stop_reason)

                    # Emit completed tool calls
                    if finish_reason == FinishReason.TOOL_CALLS and pending_tool_calls:
                        tool_calls = []
                        for tc_data in pending_tool_calls.values():
                            try:
                                arguments = json.loads(tc_data["arguments"]) if tc_data["arguments"] else {}
                            except json.JSONDecodeError:
                                arguments = {}
                            tool_calls.append(
                                ToolCall(
                                    id=tc_data["id"],
                                    name=tc_data["name"],
                                    arguments=arguments,
                                )
                            )

                # Only yield if we have meaningful content
                if content is not None or thinking is not None or tool_calls or finish_reason:
                    yield StreamChunk(
                        content=content,
                        tool_calls=tool_calls,
                        finish_reason=finish_reason,
                        thinking=thinking,
                    )
