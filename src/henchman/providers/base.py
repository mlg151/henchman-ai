"""Base types and abstractions for model providers."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any

from henchman.providers.request_budget import (
    OutputBudget,
    estimate_serialized_input,
    validate_output_tokens,
)

__all__ = [
    "ContextTooLargeError",
    "FinishReason",
    "Message",
    "ModelProvider",
    "StreamChunk",
    "ToolCall",
    "ToolDeclaration",
]


class ContextTooLargeError(Exception):
    """Raised when the context/request is too large for the API.

    This typically happens when the conversation history plus tool outputs
    exceeds the model's context window or the API's request size limit.
    """

    def __init__(self, message: str = "Request too large for API") -> None:
        """Initialize the error.

        Args:
            message: Error message with guidance for the user.
        """
        super().__init__(message)


class FinishReason(Enum):
    """Reasons why the model stopped generating."""

    STOP = "stop"
    TOOL_CALLS = "tool_calls"
    LENGTH = "length"
    CONTENT_FILTER = "content_filter"


@dataclass
class ToolCall:
    """A tool call requested by the model."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class ToolDeclaration:
    """Declaration of a tool available to the model."""

    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema


@dataclass
class Message:
    """A message in the conversation history."""

    role: str  # "system" | "user" | "assistant" | "tool"
    content: str | None = None
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None
    reasoning_content: str | None = None


@dataclass
class StreamChunk:
    """A chunk of streaming response from the model."""

    content: str | None = None
    tool_calls: list[ToolCall] | None = None
    finish_reason: FinishReason | None = None
    thinking: str | None = None  # For reasoning models like deepseek-reasoner
    usage: dict[str, int] | None = (
        None  # Token usage information (prompt_tokens, completion_tokens, total_tokens)
    )


class ModelProvider(ABC):
    """Abstract base class for model providers."""

    def required_tool_names(self) -> list[str]:
        """Return named schemas that must survive optional catalog reduction."""
        return []

    def prepare_output_budget(self, default_max_tokens: int) -> OutputBudget:
        """Reserve and request a deliberate portable output cap."""
        cap = validate_output_tokens(default_max_tokens)
        return OutputBudget(cap, {"max_tokens": cap})

    def estimate_input_tokens(
        self, messages: list[Message], tools: list[ToolDeclaration] | None,
    ) -> int:
        """Estimate generic message/tool JSON, including reasoning and schemas."""
        payload: dict[str, Any] = {"messages": [asdict(message) for message in messages]}
        if tools:
            payload["tools"] = [asdict(tool) for tool in tools]
        return estimate_serialized_input(payload)

    @property
    @abstractmethod
    def name(self) -> str:
        """The unique name of this provider."""
        ...  # pragma: no cover

    @abstractmethod
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
            **kwargs: Additional provider-specific parameters.

        Yields:
            StreamChunk objects as the response is generated.
        """
        ...  # pragma: no cover
        # Make this an async generator
        if False:  # pragma: no cover
            yield StreamChunk()
