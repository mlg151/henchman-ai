"""Shared dotted key paths for settings mappings."""

from collections.abc import Mapping
from typing import Any


def flatten_key_paths(payload: Mapping[str, Any], prefix: str = "") -> list[str]:
    """Return dotted key paths for each leaf in a nested mapping."""
    key_paths: list[str] = []
    for key, value in payload.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, Mapping) and value:
            key_paths.extend(flatten_key_paths(value, path))
            continue
        key_paths.append(path)
    return key_paths
