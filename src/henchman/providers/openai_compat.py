"""OpenAI-compatible provider base class.

This provider works with any API that follows the OpenAI chat completions format,
including DeepSeek, Together, Groq, Fireworks, and others.
"""

from __future__ import annotations

import json
import logging
from contextlib import aclosing
from copy import deepcopy
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

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
from henchman.providers.request_budget import (
    OutputBudget,
    estimate_serialized_input,
    validate_output_tokens,
)
from henchman.providers.utils import parse_finish_reason, parse_tool_arguments, validate_messages

__all__ = ["OpenAICompatibleProvider"]

logger = logging.getLogger(__name__)

_HTTP_REQUEST_TOO_LARGE = 413


@dataclass
class ProviderConfig:
    """Configuration for an OpenAI-compatible provider."""

    api_key: str
    base_url: str
    default_model: str


def _format_tool(tool: ToolDeclaration) -> dict[str, Any]:
    """Format a tool declaration for the OpenAI API."""
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
        },
    }


def _required_function_name(choice: object) -> str:
    """Read one named function choice without modifying its wire representation."""
    if isinstance(choice, dict) and choice.get("type") == "function":
        function = choice.get("function")
        if isinstance(function, dict):
            name = function.get("name")
            if isinstance(name, str) and name.strip():
                return name
    raise ValueError("Cannot reduce tool schemas: tool_choice requires a named function")


def _format_tool_call_for_message(tc: ToolCall) -> dict[str, Any]:
    """Format a single tool call for inclusion in a message."""
    return {
        "id": tc.id,
        "type": "function",
        "function": {
            "name": tc.name,
            "arguments": json.dumps(tc.arguments),
        },
    }


def _format_message(message: Message) -> dict[str, Any]:
    """Format a message for the OpenAI API."""
    result: dict[str, Any] = {
        "role": message.role,
        "content": message.content,
    }
    if message.reasoning_content:
        result["reasoning_content"] = message.reasoning_content
    if message.tool_calls:
        result["tool_calls"] = [_format_tool_call_for_message(tc) for tc in message.tool_calls]
    if message.tool_call_id:
        result["tool_call_id"] = message.tool_call_id
    return result


def _parse_single_tool_call(tc: Any) -> ToolCall:
    """Parse a single tool call from the API response."""
    return ToolCall(
        id=tc.id,
        name=tc.function.name,
        arguments=parse_tool_arguments(tc.function.arguments),
    )


def _update_tool_call_accumulator(
    pending_tool_calls: dict[int, dict[str, Any]],
    tool_call_deltas: list[Any],
) -> None:
    """Accumulate streaming tool call delta fragments into pending_tool_calls.

    Args:
        pending_tool_calls: Dictionary tracking tool calls across chunks (mutated in place).
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
            tc_func = tc_delta.function
            if tc_func.name:
                pending_tool_calls[idx]["name"] = tc_func.name
            if tc_func.arguments:
                pending_tool_calls[idx]["arguments"] += tc_func.arguments


def _extract_usage_from_chunk(chunk: Any) -> dict[str, int] | None:
    """Extract token usage information from an API response chunk.

    Args:
        chunk: The API response chunk.

    Returns:
        Usage dictionary or None if not available.
    """
    if hasattr(chunk, "usage") and chunk.usage:
        return {
            "prompt_tokens": chunk.usage.prompt_tokens,
            "completion_tokens": chunk.usage.completion_tokens,
            "total_tokens": chunk.usage.total_tokens,
        }
    return None


def _extract_reasoning_text(delta: Any) -> str | None:
    """Accept compatible text dialects without duplicating aliased reasoning."""
    for field in ("reasoning_content", "reasoning"):
        value = getattr(delta, field, None)
        if isinstance(value, str) and value:
            return value
    return None


class OpenAICompatibleProvider(ModelProvider):
    """Base provider for OpenAI-compatible APIs."""

    def __init__(
        self: OpenAICompatibleProvider,
        api_key: str,
        base_url: str,
        default_model: str,
        **request_defaults: Any,
    ) -> None:
        """Initialize the provider.

        Args:
            api_key: API key for authentication.
            base_url: Base URL for the API.
            default_model: Default model to use for completions.
            **request_defaults: Request options overridden by per-call arguments.
        """
        if {"messages", "tools", "stream"}.intersection(request_defaults):
            raise ValueError("Provider request defaults cannot override messages, tools, or stream")
        self.request_defaults = deepcopy(request_defaults)
        self.config = ProviderConfig(
            api_key=api_key,
            base_url=base_url,
            default_model=default_model,
        )
        self.api_key = api_key
        self.base_url = base_url
        self.default_model = default_model
        # Newer SDKs reject empty credentials even for keyless compatible servers.
        # Keep the configured value intact and avoid inheriting SDK environment keys.
        self._client = AsyncOpenAI(api_key=api_key or "not-required", base_url=base_url)

    @property
    def name(self: OpenAICompatibleProvider) -> str:
        """The unique name of this provider."""
        return "openai-compatible"

    def _effective_budget_options(self) -> dict[str, Any]:
        """Mirror SDK body overrides for caps and known input-schema options."""
        extra = self.request_defaults.get("extra_body")
        if extra is None:
            extra = {}
        if not isinstance(extra, dict):
            raise ValueError("Budget accounting requires an object for extra_body")
        if {"messages", "tools"}.intersection(extra):
            raise ValueError("Budget accounting cannot override messages or tools in extra_body")
        return {**self.request_defaults, **extra}

    def required_tool_names(self) -> list[str]:
        """Preserve effective named choices when a caller reduces the catalog.

        This validation is opt-in at reduction time; ordinary request construction
        still forwards provider-specific choices unchanged.
        """
        options = self._effective_budget_options()
        if "tool_choice" not in options:
            return []
        choice = options["tool_choice"]
        if choice in ("auto", "none", "required"):
            return []
        if isinstance(choice, dict) and choice.get("type") == "allowed_tools":
            allowed = choice.get("allowed_tools")
            if isinstance(allowed, dict) and allowed.get("mode") in ("auto", "required"):
                tools = allowed.get("tools")
                if isinstance(tools, list | tuple) and tools:
                    return list(dict.fromkeys(_required_function_name(tool) for tool in tools))
            raise ValueError("Cannot reduce tool schemas: invalid allowed_tools tool_choice")
        return [_required_function_name(choice)]

    def prepare_output_budget(self, default_max_tokens: int) -> OutputBudget:
        """Reserve the effective saved cap, or explicitly request the default."""
        options = self._effective_budget_options()
        fields = [name for name in ("max_tokens", "max_completion_tokens") if name in options]
        if len(fields) > 1:
            raise ValueError("Configure only one of max_tokens and max_completion_tokens")
        field = fields[0] if fields else "max_tokens"
        cap = validate_output_tokens(options[field] if fields else default_max_tokens)
        return OutputBudget(cap, {field: cap})

    def estimate_input_tokens(
        self, messages: list[Message], tools: list[ToolDeclaration] | None,
    ) -> int:
        """Estimate actual message/tool shapes and known schema-bearing options."""
        options = self._effective_budget_options()
        messages = self._repair_message_sequence_if_needed(messages)
        payload: dict[str, Any] = {"messages": [_format_message(message) for message in messages]}
        if tools:
            payload["tools"] = [_format_tool(tool) for tool in tools]
        for name in ("response_format", "tool_choice"):
            if name in options:
                payload[name] = options[name]
        return estimate_serialized_input(payload, model=self.default_model)

    def _parse_tool_calls(
        self: OpenAICompatibleProvider,
        tool_calls: list[Any] | None,
    ) -> list[ToolCall] | None:
        """Parse tool calls from the API response."""
        if not tool_calls:
            return None
        result = [_parse_single_tool_call(tc) for tc in tool_calls]
        return result or None

    def _format_tool(
        self: OpenAICompatibleProvider,
        tool: ToolDeclaration,
    ) -> dict[str, Any]:
        """Format a tool declaration for the OpenAI API."""
        return _format_tool(tool)

    def _format_message(
        self: OpenAICompatibleProvider,
        message: Message,
    ) -> dict[str, Any]:
        """Format a message for the OpenAI API."""
        # Assign to variable to differentiate AST from _format_tool delegation
        result = _format_message(message)
        return result  # noqa: RET504 — intermediate variable differentiates AST from _format_tool

    def _parse_finish_reason(
        self: OpenAICompatibleProvider,
        reason: str | None,
    ) -> FinishReason | None:
        """Parse OpenAI finish reason to our enum."""
        return parse_finish_reason(reason)

    def _extract_usage_info(
        self: OpenAICompatibleProvider,
        chunk: Any,
    ) -> dict[str, int] | None:
        """Extract usage information from the chunk if available."""
        return _extract_usage_from_chunk(chunk)

    async def chat_completion_stream(
        self: OpenAICompatibleProvider,
        messages: list[Message],
        tools: list[ToolDeclaration] | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[StreamChunk]:
        """Stream a chat completion from the model.

        Args:
            messages: The conversation history.
            tools: Optional list of tools available to the model.
            **kwargs: Additional parameters passed to the API.

        Yields:
            StreamChunk objects as the response is generated.
        """
        validate_messages(messages)
        logger.debug(
            "OpenAICompatibleProvider.chat_completion_stream: Starting with %d messages",
            len(messages),
        )

        messages = self._repair_message_sequence_if_needed(messages)
        params = self._build_request_params(messages, tools, kwargs)
        response = await self._make_api_request(params)

        primary_error: BaseException | None = None
        try:
            async with aclosing(self._process_stream_response(response)) as chunks:
                async for chunk in chunks:
                    yield chunk
        except BaseException as exc:
            primary_error = exc
            raise
        finally:
            try:
                await response.close()
            except Exception:
                if primary_error is None:
                    raise
                logger.exception("Failed to close provider stream after an error")

    def _repair_message_sequence_if_needed(
        self: OpenAICompatibleProvider,
        messages: list[Message],
    ) -> list[Message]:
        """Repair message sequence if it is invalid to prevent API errors.

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
        self: OpenAICompatibleProvider,
        messages: list[Message],
        tools: list[ToolDeclaration] | None,
        kwargs: dict[str, Any],
    ) -> dict[str, Any]:
        """Build the request parameters for the API call.

        Args:
            messages: The conversation history.
            tools: Optional list of tools available to the model.
            kwargs: Additional parameters passed to the API.

        Returns:
            The request parameters dictionary.
        """
        options = {**deepcopy(self.request_defaults), **kwargs}
        params: dict[str, Any] = {
            "model": options.pop("model", self.default_model),
            "messages": [_format_message(m) for m in messages],
            "stream": True,
            **options,
        }

        if tools:
            params["tools"] = [_format_tool(t) for t in tools]

        return params

    async def _make_api_request(
        self: OpenAICompatibleProvider,
        params: dict[str, Any],
    ) -> Any:
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
            if e.status_code == _HTTP_REQUEST_TOO_LARGE:
                msg = (
                    "Request too large. Try using start_line/end_line when reading "
                    "files to limit context size, or start a new conversation."
                )
                raise ContextTooLargeError(msg) from e
            raise

    async def _process_stream_response(
        self: OpenAICompatibleProvider,
        response: Any,
    ) -> AsyncGenerator[StreamChunk]:
        """Process the streaming response and yield StreamChunk objects.

        Args:
            response: The API response stream.

        Yields:
            StreamChunk objects as the response is generated.
        """
        pending_tool_calls: dict[int, dict[str, Any]] = {}

        async for chunk in response:
            error = getattr(chunk, "error", None)
            if isinstance(error, dict) and error:
                raise RuntimeError("Provider stream reported an error")
            if not chunk.choices:
                usage = _extract_usage_from_chunk(chunk)
                if usage is not None:
                    yield StreamChunk(usage=usage)
                continue

            choice = chunk.choices[0]
            if choice.finish_reason == "error":
                raise RuntimeError("Provider stream reported an error")
            delta = choice.delta
            content = getattr(delta, "content", None)
            thinking = _extract_reasoning_text(delta)
            tool_calls = None

            if hasattr(delta, "tool_calls") and delta.tool_calls:
                _update_tool_call_accumulator(pending_tool_calls, delta.tool_calls)

            finish_reason = parse_finish_reason(choice.finish_reason)

            if finish_reason and pending_tool_calls:
                if finish_reason == FinishReason.TOOL_CALLS:
                    tool_calls = self._build_tool_calls_from_pending(pending_tool_calls)
                pending_tool_calls.clear()  # prevent re-yield if API sends multiple finish chunks

            yield StreamChunk(
                content=content,
                tool_calls=tool_calls,
                finish_reason=finish_reason,
                thinking=thinking,
                usage=_extract_usage_from_chunk(chunk),
            )

    def _build_tool_calls_from_pending(
        self: OpenAICompatibleProvider,
        pending_tool_calls: dict[int, dict[str, Any]],
    ) -> list[ToolCall]:
        """Build ToolCall objects from pending tool call data.

        Args:
            pending_tool_calls: Dictionary tracking tool calls across chunks.

        Returns:
            List of ToolCall objects.
        """
        tool_calls = []
        for tc_data in pending_tool_calls.values():
            tool_calls.append(
                ToolCall(
                    id=tc_data["id"],
                    name=tc_data["name"],
                    arguments=parse_tool_arguments(tc_data["arguments"]),
                ),
            )
        return tool_calls
