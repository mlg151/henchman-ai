"""Resolve explicitly configured MCP environment references at the process boundary."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping

_REFERENCE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def resolve_environment(environment: Mapping[str, str]) -> dict[str, str]:
    """Copy literals and resolve whole-value references exactly once, without ambient injection."""
    resolved: dict[str, str] = {}
    for name, value in environment.items():
        reference = _REFERENCE.fullmatch(value)
        if reference is not None:
            variable = reference.group(1)
            replacement = os.environ.get(variable)
            if not replacement:
                raise ValueError(f"Set {variable} before connecting the MCP server: required environment reference is missing")
            resolved[name] = replacement
        elif "${" in value:
            raise ValueError("MCP environment reference must be a complete ${NAME} value")
        else:
            resolved[name] = value
    return resolved


def reference_values(environment: Mapping[str, str], resolved: Mapping[str, str]) -> tuple[str, ...]:
    """Return actual injected reference values for explicit evidence registration."""
    return tuple(resolved[name] for name, value in environment.items() if _REFERENCE.fullmatch(value))


def environment_references(environment: Mapping[str, str]) -> tuple[str, ...]:
    """Identify explicit reference strings for a live evidence registry, without injection."""
    return tuple(value for value in environment.values() if _REFERENCE.fullmatch(value))
