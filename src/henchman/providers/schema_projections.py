"""Explicit version-one non-strict tool-schema projections for shipped adapters.

These are conservative client profiles, not a promise about every remote model.
No profile makes optional properties required or substitutes null for omission.
Unsupported constructs fail before a transport attempt instead of being erased.
"""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

PROJECTION_VERSION = 1
PROVIDER_SCHEMA_PROFILES = {
    "anthropic": "anthropic-input-schema-v1",
    "deepseek": "deepseek-chat-nonstrict-v1",
    "ollama": "ollama-chat-nonstrict-v1",
    "openrouter": "openrouter-chat-nonstrict-v1",
    "openai_compat": "compatible-chat-nonstrict-v1",
}
_ANNOTATIONS = {"description", "title", "default", "examples", "$comment"}
_SUPPORTED = _ANNOTATIONS | {"type", "properties", "required", "additionalProperties", "items",
                            "enum", "const", "anyOf", "minimum", "maximum", "exclusiveMinimum",
                            "exclusiveMaximum", "multipleOf", "minLength", "maxLength", "pattern",
                            "minItems", "maxItems", "uniqueItems", "minProperties", "maxProperties"}


class SchemaProjectionError(ValueError):
    """An explicit profile failure containing no schema or argument values."""

    def __init__(self, provider: str, reason: str) -> None:
        self.provider = provider
        self.reason = reason
        super().__init__(f"Tool schema projection failed for {provider}: {reason}")


def project_tool_parameters(parameters: dict[str, Any], provider: str) -> dict[str, Any]:
    """Detach and inline local acyclic references without changing assertions."""
    # Lazy imports avoid the providers -> tools -> providers package cycle.
    from referencing import Registry, Resource
    from referencing.jsonschema import DRAFT202012

    from henchman.tools.contracts import MAX_SCHEMA_BYTES, SchemaContract, SchemaContractError

    if provider == "openai-compatible":
        provider = "openai_compat"
    if provider not in PROVIDER_SCHEMA_PROFILES:
        raise SchemaProjectionError("unknown", "unsupported_profile")
    try:
        canonical = SchemaContract(parameters).schema
    except SchemaContractError as error:
        raise SchemaProjectionError(provider, error.reason) from None
    resolver = Registry().resolver_with_root(Resource.from_contents(canonical, default_specification=DRAFT202012))
    remaining = 4096

    def project(node: Any, ancestry: frozenset[str], depth: int) -> Any:
        nonlocal remaining
        remaining -= 1
        if remaining < 0 or depth > 64:
            raise SchemaProjectionError(provider, "projection_limit")
        if isinstance(node, bool):
            # Boolean additionalProperties has a portable meaning. Standalone
            # Boolean tool/subschemas are rejected by their calling position.
            return node
        if not isinstance(node, dict):
            raise SchemaProjectionError(provider, "unsupported_schema_shape")
        if "$dynamicRef" in node or "$dynamicAnchor" in node:
            raise SchemaProjectionError(provider, "dynamic_reference")
        if "$ref" in node:
            reference = node["$ref"]
            if reference in ancestry:
                raise SchemaProjectionError(provider, "recursive_reference")
            if set(node) - (_ANNOTATIONS | {"$ref", "$schema", "$defs", "definitions", "$anchor"}):
                raise SchemaProjectionError(provider, "reference_siblings")
            expanded = project(resolver.lookup(reference).contents, ancestry | {reference}, depth + 1)
            if not isinstance(expanded, dict):
                raise SchemaProjectionError(provider, "boolean_reference")
            expanded.update({key: deepcopy(value) for key, value in node.items() if key in _ANNOTATIONS})
            return expanded
        result: dict[str, Any] = {}
        for key, value in node.items():
            if key in {"$schema", "$defs", "definitions", "$anchor"}:
                continue
            if key not in _SUPPORTED:
                raise SchemaProjectionError(provider, "unsupported_keyword")
            if key == "properties":
                result[key] = {name: project(child, ancestry, depth + 1) for name, child in value.items()}
                if any(isinstance(child, bool) for child in result[key].values()):
                    raise SchemaProjectionError(provider, "boolean_subschema")
            elif key in {"items", "additionalProperties"}:
                result[key] = project(value, ancestry, depth + 1)
                if key == "items" and isinstance(value, bool):
                    raise SchemaProjectionError(provider, "boolean_subschema")
            elif key == "anyOf":
                result[key] = [project(child, ancestry, depth + 1) for child in value]
                if any(isinstance(child, bool) for child in result[key]):
                    raise SchemaProjectionError(provider, "boolean_subschema")
            else:
                result[key] = deepcopy(value)
        return result

    projected = project(canonical, frozenset(), 0)
    if not isinstance(projected, dict) or ("type" in projected and projected["type"] != "object"):
        raise SchemaProjectionError(provider, "tool_input_must_be_object")
    if len(json.dumps(projected, ensure_ascii=True)) > MAX_SCHEMA_BYTES:
        raise SchemaProjectionError(provider, "projection_limit")
    return projected
