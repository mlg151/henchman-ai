"""Utility functions for provider management."""

import json
import os
from typing import Any, Final

from henchman.providers.base import FinishReason, Message


def _reject_json_constant(_value: str) -> None:
    """Reject nonstandard NaN and Infinity literals accepted by Python's decoder."""
    raise ValueError("Tool arguments must be a valid JSON object")


def parse_tool_arguments(raw: str) -> dict[str, Any]:
    """Parse complete tool arguments without inventing values for invalid input."""
    try:
        arguments = {} if raw == "" else json.loads(raw, parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValueError("Tool arguments must be a valid JSON object") from exc
    if not isinstance(arguments, dict):
        raise ValueError("Tool arguments must be a valid JSON object")
    return arguments


def get_env_var_for_provider(provider_name: str) -> str:
    """Get the environment variable name for a provider's API key.

    Args:
        provider_name: Name of the provider.

    Returns:
        Environment variable name.
    """
    # Mapping of provider names to their default environment variables
    env_var_mapping: Final[dict[str, str]] = {
        "deepseek": "DEEPSEEK_API_KEY",
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "openai_compat": "HENCHMAN_API_KEY",
        "together": "TOGETHER_API_KEY",
        "groq": "GROQ_API_KEY",
        "fireworks": "FIREWORKS_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
        "ollama": "",  # Ollama doesn't need an API key
    }

    # Default to HENCHMAN_API_KEY for unknown providers
    return env_var_mapping.get(provider_name, "HENCHMAN_API_KEY")


def get_api_key_for_provider(provider_name: str) -> str | None:
    """Get the API key for a provider from environment variables.

    Args:
        provider_name: Name of the provider.

    Returns:
        API key if found in environment, None otherwise.
    """
    # Try provider-specific environment variable first
    env_var_name = get_env_var_for_provider(provider_name)
    api_key = os.environ.get(env_var_name)

    if api_key:
        return api_key

    # Try generic HENCHMAN_API_KEY as fallback (except for ollama)
    if provider_name != "ollama":
        api_key = os.environ.get("HENCHMAN_API_KEY")
        if api_key:
            return api_key

    return None


def validate_messages(messages: list[Message]) -> None:
    """Validate that messages are not empty and have content where required.

    Args:
        messages: The conversation history to validate.

    Returns:
        None

    Raises:
        ValueError: If messages are empty or have invalid content.
    """
    if not messages:
        msg = "Messages list cannot be empty"
        raise ValueError(msg)

    for message in messages:
        # Tool/function messages can have empty content
        if message.role in ["tool", "function"]:
            continue

        # Assistant messages can have empty content (e.g., when only tool calls are made)
        if message.role == "assistant":
            continue

        # All other messages must have non-empty content
        if not (message.content or "").strip():
            msg = f"Message with role '{message.role}' cannot have empty content"
            raise ValueError(msg)


def parse_finish_reason(
    reason: str | None,
    provider_mapping: dict[str, FinishReason] | None = None,
) -> FinishReason | None:
    """Parse finish reason from provider-specific format to our enum.

    Args:
        reason: The provider-specific finish reason string.
        provider_mapping: Optional custom mapping for provider-specific reasons.
            If None, uses a default mapping.

    Returns:
        Mapped FinishReason or None if reason is None.
    """
    if reason is None:
        return None

    # Default mapping for providers that don't specify one
    default_mapping: Final[dict[str, FinishReason]] = {
        "stop": FinishReason.STOP,
        "tool_calls": FinishReason.TOOL_CALLS,
        "length": FinishReason.LENGTH,
        "content_filter": FinishReason.CONTENT_FILTER,
    }

    mapping = provider_mapping or default_mapping
    return mapping.get(reason, FinishReason.STOP)
