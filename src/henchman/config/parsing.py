"""Parse money controls exactly without changing ordinary numeric settings."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal

import yaml

_RATES = frozenset({"input_per_1k", "output_per_1k", "cache_read_per_1k", "cache_write_per_1k"})


@dataclass(frozen=True)
class _FloatToken:
    """Keep the source spelling until its configuration location is known."""

    text: str
    ordinary: float


class _SettingsLoader(yaml.SafeLoader):
    pass


def _yaml_float(loader: _SettingsLoader, node: yaml.ScalarNode) -> _FloatToken:
    return _FloatToken(node.value, yaml.SafeLoader.construct_yaml_float(loader, node))


_SettingsLoader.add_constructor("tag:yaml.org,2002:float", _yaml_float)


def _money_text(text: str) -> str:
    """Normalize YAML float syntax using integer/string operations only."""
    value = text.replace("_", "").lower()
    negative = value.startswith("-")
    unsigned = value.lstrip("+-")
    if unsigned == ".inf":
        return "-Infinity" if negative else "Infinity"
    if unsigned == ".nan":
        return "NaN"
    if ":" not in unsigned:
        return value
    integral, _, fractional = unsigned.partition(".")
    whole = 0
    for part in integral.split(":"):
        whole = whole * 60 + int(part)
    return ("-" if negative else "") + str(whole) + "." + fractional


def _child_context(context: str, key: object) -> str:
    if context == "root" and key == "usage":
        return "usage"
    if context == "usage" and key in ("limits", "prices"):
        return str(key)
    if context == "limits" and key == "max_cost":
        return "money"
    if context == "price" and isinstance(key, str) and key in _RATES:
        return "money"
    return "other"


def parse_settings_text(
    text: str,
    *,
    format: Literal["json", "yaml"],
    key_path: str = "",
) -> Any:
    """Keep only typed monetary numeric tokens as exact decimal strings.

    ``key_path`` locates a CLI ``set`` value in the full settings document.
    All other floats, including opaque provider options, retain the standard
    parser's float values. Strings, integers, booleans and null remain unchanged.
    The result contains no Decimal or parser-private objects.
    """
    parsed = (
        json.loads(text, parse_float=lambda value: _FloatToken(value, float(value)))
        if format == "json"
        else yaml.load(text, Loader=_SettingsLoader)
    )
    context = "root"
    if key_path:
        for part in key_path.split("."):
            context = _child_context(context, part.strip())
    memo: dict[tuple[int, str], Any] = {}

    def normalize(value: Any, location: str) -> Any:
        if isinstance(value, _FloatToken):
            return _money_text(value.text) if location == "money" else value.ordinary
        if isinstance(value, tuple):
            return tuple(normalize(item, "other") for item in value)
        if isinstance(value, set):
            return {normalize(item, "other") for item in value}
        if isinstance(value, (dict, list)):
            identity = (id(value), location)
            if identity in memo:
                return memo[identity]
            if isinstance(value, dict):
                result: Any = {}
                memo[identity] = result
                for key, nested in value.items():
                    result[normalize(key, "other")] = normalize(
                        nested, _child_context(location, key)
                    )
            else:
                result = []
                memo[identity] = result
                result.extend(
                    normalize(item, "price" if location == "prices" else "other") for item in value
                )
            return result
        return value

    return normalize(parsed, context)
