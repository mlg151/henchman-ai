"""Token counting utilities with tiktoken integration.

This module provides accurate token counting using tiktoken for OpenAI-compatible
models, with model-specific limits and fallback to cl100k_base encoding.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

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


def get_model_limit(model: str) -> int:
    """Get the context window limit for a model.

    Args:
        model: The model name.

    Returns:
        The context window size in tokens.
    """
    return MODEL_LIMITS.get(model, DEFAULT_MODEL_LIMIT)


class TokenCounter:
    """Counts tokens using tiktoken for accurate estimation.

    Uses cl100k_base encoding by default (used by GPT-4, GPT-3.5-turbo,
    and OpenAI-compatible APIs like DeepSeek).
    """

    # Cache encodings to avoid repeated initialization
    _encodings: dict[str, tiktoken.Encoding] = {}

    @classmethod
    def _get_encoding(cls, model: str | None = None) -> tiktoken.Encoding:
        """Get the tiktoken encoding for a model.

        Args:
            model: Optional model name. Uses cl100k_base if not specified
                   or if model encoding is not found.

        Returns:
            The tiktoken Encoding object.
        """
        # Use cl100k_base as default (works for GPT-4, GPT-3.5, DeepSeek, etc.)
        encoding_name = "cl100k_base"

        if model:
            try:
                # Try to get model-specific encoding
                return tiktoken.encoding_for_model(model)
            except KeyError:
                # Model not found, use default
                pass

        # Use cached encoding if available
        if encoding_name not in cls._encodings:
            cls._encodings[encoding_name] = tiktoken.get_encoding(encoding_name)

        return cls._encodings[encoding_name]

    @classmethod
    def count_text(cls, text: str, model: str | None = None) -> int:
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
    def truncate_text(cls, text: str, max_tokens: int, model: str | None = None) -> str:
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
        # Note: We don't handle partial unicode bytes here as tiktoken handles text -> tokens -> text  # noqa: E501
        return encoding.decode(tokens[:max_tokens])

    @classmethod
    def count_messages(cls, messages: list[Message], model: str | None = None) -> int:
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
        encoding_encode = encoding.encode
        total = 0

        # Per-message overhead (varies by model, using GPT-4 defaults)
        # See: https://cookbook.openai.com/examples/how_to_count_tokens_with_tiktoken
        tokens_per_message = 3  # <|start|>{role/name}\n{content}<|end|>\n

        for msg in messages:
            total += tokens_per_message
            msg_role = msg.role
            msg_content = msg.content

            # Count role
            total += len(encoding_encode(msg_role))

            # Count content
            if msg_content:
                total += len(encoding_encode(msg_content))

            # Count tool calls (JSON serialized)
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    # Approximate: function name + arguments as JSON
                    total += len(encoding.encode(tc.name))
                    import json

                    total += len(encoding.encode(json.dumps(tc.arguments)))
                    total += 10  # Overhead for tool call structure

            # Count tool_call_id
            if msg.tool_call_id:
                total += len(encoding.encode(msg.tool_call_id))

        # Every reply is primed with <|start|>assistant<|message|>
        total += 3

        return total
