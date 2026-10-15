"""Shared helpers for redacting secret-like config values in CLI output."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final

_REDACTED_VALUE: Final[str] = "<redacted>"
_SECRET_NAMES: Final[frozenset[str]] = frozenset(
    {
        "api_key",
        "api_keys",
        "key",
        "keys",
        "passphrase",
        "passwd",
        "password",
        "private_key",
        "private_keys",
        "secret",
        "secrets",
        "token",
        "tokens",
    }
)


def redact_config_value_for_display(*, key_path: str, value: Any) -> Any:
    """Redact a config value using the shared secret-like display policy."""
    if _is_secret_like_key_path(key_path):
        return _REDACTED_VALUE
    if isinstance(value, Mapping):
        return _redact_mapping(value)
    if isinstance(value, list):
        return _redact_list(value, parent_key=_last_key_segment(key_path))
    return value


def redact_config_mapping_for_display(value: Mapping[str, Any]) -> dict[str, Any]:
    """Redact secret-like values inside a nested mapping."""
    return _redact_mapping(value)


def is_secret_like_key_path(key_path: str) -> bool:
    """Return whether any segment of a dotted key path looks secret-bearing."""
    return _is_secret_like_key_path(key_path)


def _redact_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    """Redact secret-like values inside a nested mapping."""
    redacted: dict[str, Any] = {}
    for key, nested_value in value.items():
        if _is_secret_like_name(key):
            redacted[key] = _REDACTED_VALUE
            continue
        if isinstance(nested_value, Mapping):
            redacted[key] = _redact_mapping(nested_value)
            continue
        if isinstance(nested_value, list):
            redacted[key] = _redact_list(nested_value, parent_key=key)
            continue
        redacted[key] = nested_value
    return redacted


def _redact_list(value: list[Any], *, parent_key: str) -> Any:
    """Redact or recurse through a list for human-readable output."""
    if _is_secret_like_name(parent_key):
        return _REDACTED_VALUE
    return [_redact_mapping(item) if isinstance(item, Mapping) else item for item in value]


def _is_secret_like_key_path(key_path: str) -> bool:
    """Return whether any segment of a dotted key path looks secret-bearing."""
    return any(_is_secret_like_name(segment) for segment in key_path.split("."))


def _is_secret_like_name(value: str) -> bool:
    """Return whether a key name looks secret-bearing."""
    normalized = value.strip().lower().replace("-", "_")
    return normalized in _SECRET_NAMES or normalized.endswith(
        ("_key", "_keys", "_password", "_secret", "_token")
    )


def _last_key_segment(key_path: str) -> str:
    """Return the last segment of a dotted key path."""
    return key_path.rsplit(".", maxsplit=1)[-1]


__all__ = [
    "is_secret_like_key_path",
    "redact_config_mapping_for_display",
    "redact_config_value_for_display",
]
