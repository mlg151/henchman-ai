"""Construct providers consistently from application settings."""

from __future__ import annotations

import os
import re
from typing import TYPE_CHECKING, Any

from henchman.providers.openai_compat import OpenAICompatibleProvider
from henchman.providers.registry import ProviderRegistry, get_default_registry
from henchman.providers.utils import get_api_key_for_provider, get_env_var_for_provider

if TYPE_CHECKING:
    from henchman.config.schema import ProviderSettings
    from henchman.providers.base import ModelProvider

_CLOUD_PROVIDERS = frozenset(
    {"deepseek", "anthropic", "openrouter", "openai", "together", "groq", "fireworks"}
)


def resolve_api_key(provider_name: str, configured: object = None) -> str | None:
    """Resolve an explicit key or environment reference before environment defaults."""
    if configured is not None and not isinstance(configured, str):
        raise ValueError(f"providers.{provider_name}.api_key must be a string")
    if isinstance(configured, str):
        reference = re.fullmatch(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", configured)
        if reference:
            variable = reference.group(1)
            value = os.environ.get(variable)
            if not value:
                raise ValueError(f"Set {variable} referenced by providers.{provider_name}.api_key")
            return value
        if configured:
            return configured
    return get_api_key_for_provider(provider_name)


def create_configured_provider(
    settings: ProviderSettings,
    *,
    provider_name: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    registry: ProviderRegistry | None = None,
) -> ModelProvider:
    """Create the selected provider without changing settings or probing the network.

    Explicit arguments override saved settings. Credentials otherwise come from
    the selected provider's settings, its environment variable, then the generic
    environment variable. Unrelated credentials never select another provider.
    """
    name = provider_name if provider_name is not None else settings.default
    registry = registry if registry is not None else get_default_registry()
    try:
        provider_class = registry.get(name)
    except KeyError as exc:
        raise ValueError(f"Provider '{name}' is not registered") from exc
    configured = getattr(settings, name, {})
    if not isinstance(configured, dict):
        raise ValueError(f"providers.{name} must be a configuration mapping")
    options: dict[str, Any] = configured.copy()
    if model is not None:
        options["model"] = model
    if "model" in options and (
        not isinstance(options["model"], str) or not options["model"].strip()
    ):
        raise ValueError(f"providers.{name}.model must be a nonempty string")

    if name != "ollama":
        key = resolve_api_key(name, api_key if api_key is not None else options.get("api_key"))
        if name in _CLOUD_PROVIDERS and not key:
            raise ValueError(
                f"No API key configured for {name}. Set {get_env_var_for_provider(name)} or providers.{name}.api_key"
            )
        if key is not None or provider_class is OpenAICompatibleProvider:
            options["api_key"] = key or ""

    if provider_class is OpenAICompatibleProvider:
        if "model" in options:
            options["default_model"] = options.pop("model")
        if name == "openai":
            options.setdefault("base_url", "https://api.openai.com/v1")
        for field in ("base_url", "default_model"):
            if not isinstance(options.get(field), str) or not options[field].strip():
                setting = "model" if field == "default_model" else field
                raise ValueError(f"Configure providers.{name}.{setting}")

    try:
        return registry.create(name, **options)
    except TypeError as exc:
        raise ValueError(f"Invalid provider options for {name}; check providers.{name}") from exc
