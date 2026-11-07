"""Shared dotted key paths for settings mappings."""

from collections.abc import Mapping
from typing import Any


def flatten_key_values(payload: Mapping[str, Any], prefix: str = "") -> dict[str, Any]:
    """Return a flat dictionary of key values from a nested mapping."""
    key_values: dict[str, Any] = {}
    for key, value in payload.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, Mapping) and value:
            key_values.update(flatten_key_values(value, path))
        else:
            key_values[path] = value
    return key_values


def flatten_key_paths(payload: Mapping[str, Any], prefix: str = "") -> list[str]:
    """Return dotted key paths for each leaf in a nested mapping."""
    return list(flatten_key_values(payload, prefix))
