"""Token counting utilities with tiktoken integration.

This module provides accurate token counting using tiktoken for OpenAI-compatible
models, with model-specific limits and fallback to cl100k_base encoding.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

import tiktoken

if TYPE_CHECKING:
    from henchman.providers.base import Message


# Model-specific context window limits (in tokens)
MODEL_LIMITS: dict[str, int] = {
    # DeepSeek models
    "deepseek-chat": 128000,
    "deepseek-reasoner": 128000,
    # OpenAI models
    "gpt-4-turbo": 128000,
    "gpt-4-turbo-preview": 128000,
    "gpt-4o": 128000,
    "gpt-4o-mini": 128000,
    "gpt-4": 8192,
    "gpt-3.5-turbo": 16385,
    # Anthropic models (these use different tokenization but we estimate)
    "claude-opus-4-6": 200000,
    "claude-sonnet-4-20250514": 200000,
    "claude-3-7-sonnet-20250219": 200000,
    "claude-3-5-sonnet-20241022": 200000,
    "claude-3-5-haiku-20241022": 200000,
    "claude-3-opus-20240229": 200000,
    # Ollama models (local, varies by model)
    "llama3.2": 131072,
    "llama3.1": 131072,
    "mistral": 32768,
    "codellama": 16384,
}

# Default limit for unknown models
DEFAULT_MODEL_LIMIT = 8000

# Default tiktoken encoding (works for GPT-4, GPT-3.5, DeepSeek, etc.)
DEFAULT_ENCODING_NAME = "cl100k_base"

# Per-message overhead: <|start|>{role/name}\n{content}<|end|>\n
# See: https://cookbook.openai.com/examples/how_to_count_tokens_with_tiktoken
TOKENS_PER_MESSAGE = 3

# Overhead tokens for tool call structure (function metadata, JSON wrapping, etc.)
TOOL_CALL_OVERHEAD_TOKENS = 10

# Every reply is primed with <|start|>assistant<|message|>
REPLY_PRIMER_TOKENS = 3


@dataclass
class TextTruncationParams:
    """Groups the parameters for truncating text to a token limit.

    Attributes:
        text: The text to truncate.
        max_tokens: Maximum number of tokens allowed.
        model: Optional model name for model-specific encoding.
    """

    text: str
    max_tokens: int
    model: str | None = None


def get_model_limit(model: str) -> int:
    """Get the context window limit for a model.

    Args:
        model: The model name.

    Returns:
        The context window size in tokens.
    """
    return MODEL_LIMITS.get(model, DEFAULT_MODEL_LIMIT)


def _resolve_tiktoken_encoding(
    model: str | None,
    cache: dict[str, tiktoken.Encoding],
) -> tiktoken.Encoding:
    """Resolve and cache a tiktoken encoding for the given model.

    Args:
        model: Optional model name. Falls back to DEFAULT_ENCODING_NAME if
               not provided or if model encoding is not found.
        cache: Mutable encoding cache to read from and write to.

    Returns:
        The tiktoken Encoding object.
    """
    if model:
        try:
            return tiktoken.encoding_for_model(model)
        except KeyError:
            pass

    if DEFAULT_ENCODING_NAME not in cache:
        cache[DEFAULT_ENCODING_NAME] = tiktoken.get_encoding(DEFAULT_ENCODING_NAME)

    return cache[DEFAULT_ENCODING_NAME]


def _count_single_message_tokens(msg: Message, encode: object) -> int:
    """Count tokens for one message including role, content, and tool calls.

    Args:
        msg: The message to count.
        encode: The tiktoken encoding.encode callable.

    Returns:
        Token count for the message plus per-message overhead.
    """
    total = TOKENS_PER_MESSAGE
    total += len(encode(msg.role))  # type: ignore[operator]

    if msg.content:
        total += len(encode(msg.content))  # type: ignore[operator]

    if msg.tool_calls:
        for tc in msg.tool_calls:
            total += len(encode(tc.name))  # type: ignore[operator]
            total += len(encode(json.dumps(tc.arguments)))  # type: ignore[operator]
            total += TOOL_CALL_OVERHEAD_TOKENS

    if msg.tool_call_id:
        total += len(encode(msg.tool_call_id))  # type: ignore[operator]

    return total


class TokenCounter:
    """Counts tokens using tiktoken for accurate estimation.

    Uses cl100k_base encoding by default (used by GPT-4, GPT-3.5-turbo,
    and OpenAI-compatible APIs like DeepSeek).
    """

    # Cache encodings to avoid repeated initialization
    _encodings: ClassVar[dict[str, tiktoken.Encoding]] = {}

    @classmethod
    def _get_encoding(
        cls: type[TokenCounter],
        model: str | None = None,
    ) -> tiktoken.Encoding:
        """Get the tiktoken encoding for a model.

        Args:
            model: Optional model name. Uses cl100k_base if not specified
                   or if model encoding is not found.

        Returns:
            The tiktoken Encoding object.
        """
        return _resolve_tiktoken_encoding(model, cls._encodings)

    @classmethod
    def count_text(
        cls: type[TokenCounter],
        text: str,
        model: str | None = None,
    ) -> int:
        """Count tokens in text using tiktoken.

        Args:
            text: The text to count tokens for.
            model: Optional model name for model-specific encoding.

        Returns:
            The number of tokens in the text.
        """
        if not text:
            return 0

        encoding = cls._get_encoding(model)
        return len(encoding.encode(text))

    @classmethod
    def truncate_text(
        cls: type[TokenCounter],
        text: str,
        max_tokens: int,
        model: str | None = None,
    ) -> str:
        """Truncate text to a maximum number of tokens.

        Args:
            text: The text to truncate.
            max_tokens: Maximum number of tokens allowed.
            model: Optional model name.

        Returns:
            The truncated text.
        """
        if not text:
            return ""

        encoding = cls._get_encoding(model)
        tokens = encoding.encode(text)
        if len(tokens) <= max_tokens:
            return text

        # Decode the truncated tokens
        # Note: tiktoken handles text -> tokens -> text round-tripping safely
        return encoding.decode(tokens[:max_tokens])

    @classmethod
    def count_messages(
        cls: type[TokenCounter],
        messages: list[Message],
        model: str | None = None,
    ) -> int:
        """Count tokens in a list of messages.

        Accounts for message structure overhead (role, separators, etc.)
        following OpenAI's token counting guidelines.

        Args:
            messages: List of messages to count.
            model: Optional model name for model-specific encoding.

        Returns:
            Total token count including message overhead.
        """
        encoding = cls._get_encoding(model)
        total = sum(
            _count_single_message_tokens(msg, encoding.encode)
            for msg in messages
        )
        # Every reply is primed with <|start|>assistant<|message|>
        return total + REPLY_PRIMER_TOKENS
