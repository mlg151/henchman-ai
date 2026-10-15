"""Upstream proxy configuration helpers for the API layer."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class UpstreamProxyConfig:
    """Normalized upstream proxy configuration."""

    base_url: str
    headers: dict[str, str] = field(default_factory=dict)


def build_proxy_config(api_settings: Any) -> UpstreamProxyConfig | None:
    """Build an upstream proxy configuration from API settings.

    Args:
        api_settings: API settings object or compatible namespace.

    Returns:
        Normalized proxy configuration, or ``None`` when proxying is disabled.
    """
    proxy_value = getattr(api_settings, "proxy", None)
    if not isinstance(proxy_value, Mapping):
        return None

    base_url = str(proxy_value.get("base_url", "")).rstrip("/")
    if not base_url:
        return None

    headers_value = proxy_value.get("headers", {})
    headers: dict[str, str] = {}
    if isinstance(headers_value, Mapping):
        headers = {str(key): str(value) for key, value in headers_value.items()}

    return UpstreamProxyConfig(base_url=base_url, headers=headers)
