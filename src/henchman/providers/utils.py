"""Utility functions for provider management."""

import os
from typing import Final


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
        "together": "HENCHMAN_API_KEY",
        "groq": "HENCHMAN_API_KEY",
        "fireworks": "HENCHMAN_API_KEY",
        "openrouter": "HENCHMAN_API_KEY",
        # Ollama doesn't need an API key
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
