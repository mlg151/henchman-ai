"""Versioned local JSON Schema contracts with bounded, non-coercing validation.

The canonical dialect is 2020-12. References stay inside one document; resource
IDs, custom vocabularies and regex outside a conservative linear subset require
an explicit future capability. Format is an annotation, not an assertion.
"""

from __future__ import annotations

import json
import math
import re
import time
from collections.abc import Iterator
from contextvars import ContextVar
from copy import deepcopy
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from jsonschema import Draft202012Validator, validators  # type: ignore[import-untyped]
from jsonschema.exceptions import SchemaError, ValidationError  # type: ignore[import-untyped]
from referencing import Registry, Resource
from referencing.exceptions import NoSuchResource, Unresolvable
from referencing.jsonschema import DRAFT202012

if TYPE_CHECKING:
    from henchman.tools.base import ToolResult

SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"
CONTRACT_VERSION = 1
MAX_SCHEMA_BYTES = 65536
MAX_VALUE_BYTES = 1024 * 1024
MAX_DEPTH = 64
MAX_NODES = 16384
_MAP_SCHEMAS = {"properties", "patternProperties", "$defs", "definitions", "dependentSchemas"}
_SINGLE_SCHEMAS = {"additionalProperties", "unevaluatedProperties", "propertyNames", "items",
                   "contains", "unevaluatedItems", "not", "if", "then", "else", "contentSchema"}
_LIST_SCHEMAS = {"allOf", "anyOf", "oneOf", "prefixItems"}


class SchemaContractError(ValueError):
    """A safe diagnostic: never includes rejected argument values or schema text."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"Tool contract failed: {reason}")


def _json_copy(value: Any, limit: int) -> Any:
    pending = [(value, 0)]
    count = 0
    text_size = 0
    while pending:
        current, depth = pending.pop()
        count += 1
        if depth > MAX_DEPTH:
            raise SchemaContractError("depth_limit")
        if count > MAX_NODES:
            raise SchemaContractError("node_limit")
        if isinstance(current, dict):
            if len(current) * 2 + count > MAX_NODES:
                raise SchemaContractError("node_limit")
            if any(type(key) is not str for key in current):
                raise SchemaContractError("invalid_json")
            pending.extend((item, depth + 1) for item in current.values())
            pending.extend((key, depth + 1) for key in current)
        elif isinstance(current, list):
            if len(current) + count > MAX_NODES:
                raise SchemaContractError("node_limit")
            pending.extend((item, depth + 1) for item in current)
        elif type(current) is str:
            text_size += len(current)
            if text_size > limit:
                raise SchemaContractError("payload_limit")
        elif ((current is not None and type(current) not in {bool, int, float})
              or (type(current) is float and not math.isfinite(current))):
            raise SchemaContractError("invalid_json")
    try:
        payload = json.dumps(value, ensure_ascii=True, allow_nan=False, separators=(",", ":"))
    except (ValueError, TypeError, RecursionError):
        raise SchemaContractError("invalid_json") from None
    if len(payload) > limit:
        raise SchemaContractError("payload_limit")
    return json.loads(payload)


def _check_pattern(pattern: str) -> None:
    """Allow literals/classes and at most one quantified atom, anchored if present."""
    if len(pattern) > 256:
        raise SchemaContractError("unsupported_regex")
    try:
        re.compile(pattern)
    except re.error:
        raise SchemaContractError("invalid_regex") from None
    index = 0
    quantifiers = 0
    while index < len(pattern):
        char = pattern[index]
        if char == "\\":
            index += 1
            if pattern[index].isalnum() and pattern[index] not in "dDsSwW":
                raise SchemaContractError("unsupported_regex")
        elif char == "[":
            index += 1
            if index < len(pattern) and pattern[index] == "^":
                index += 1
            if index < len(pattern) and pattern[index] == "]":
                index += 1
            while index < len(pattern) and pattern[index] != "]":
                if pattern[index] == "\\":
                    index += 1
                index += 1
        elif char in "()|":
            raise SchemaContractError("unsupported_regex")
        elif char in "*+?{":
            quantifiers += 1
            if char == "{":
                end = pattern.find("}", index)
                if end < 0 or not re.fullmatch(r"\d{1,4}(,\d{0,4})?", pattern[index + 1:end]):
                    raise SchemaContractError("unsupported_regex")
                index = end
        index += 1
    if quantifiers > 1 or (quantifiers and not pattern.startswith("^")):
        raise SchemaContractError("unsupported_regex")


def _check_local_schema(schema: Any) -> list[dict[str, Any]]:
    pending = [schema]
    nodes = []
    while pending:
        current = pending.pop()
        if not isinstance(current, dict):
            continue
        nodes.append(current)
        if "$schema" in current and current["$schema"] != SCHEMA_DIALECT:
            raise SchemaContractError("unsupported_dialect")
        if "$id" in current or "$vocabulary" in current:
            raise SchemaContractError("unsupported_resource_scope")
        for keyword in ("$ref", "$dynamicRef"):
            reference = current.get(keyword)
            if isinstance(reference, str) and not reference.startswith("#"):
                raise SchemaContractError("external_reference")
        if isinstance(current.get("pattern"), str):
            _check_pattern(current["pattern"])
        for key, value in current.items():
            if key in _MAP_SCHEMAS and isinstance(value, dict):
                pending.extend(value.values())
                if key == "patternProperties":
                    for pattern in value:
                        _check_pattern(pattern)
            elif key in _SINGLE_SCHEMAS:
                pending.append(value)
            elif key in _LIST_SCHEMAS and isinstance(value, list):
                pending.extend(value)
    return nodes


@dataclass
class _ValidationBudget:
    deadline: float
    remaining: int = 50000

    def consume(self) -> None:
        self.remaining -= 1
        if self.remaining < 0 or time.monotonic() > self.deadline:
            raise SchemaContractError("validation_limit")


_BUDGET: ContextVar[_ValidationBudget | None] = ContextVar("tool_contract_validation", default=None)


def _bounded(keyword: str, validator: Any) -> Any:
    def validate(instance_validator: Any, constraint: Any, instance: Any, schema: Any) -> Iterator[ValidationError]:
        budget = _BUDGET.get()
        if budget is not None:
            budget.consume()
        yield from validator(instance_validator, constraint, instance, schema)
    validate.__name__ = keyword
    return validate


_Validator = validators.extend(Draft202012Validator, {
    keyword: _bounded(keyword, validator) for keyword, validator in Draft202012Validator.VALIDATORS.items()
})


def _no_retrieval(uri: str) -> Any:
    raise NoSuchResource(uri)


class SchemaContract:
    """An immutable schema snapshot; values are validated without default insertion."""

    def __init__(self, schema: dict[str, Any] | bool) -> None:
        self._schema = _json_copy(schema, MAX_SCHEMA_BYTES)
        nodes = _check_local_schema(self._schema)
        try:
            Draft202012Validator.check_schema(self._schema)
        except (SchemaError, RecursionError, re.error):
            raise SchemaContractError("invalid_schema") from None
        # referencing uses attrs-generated initializers, which this project's
        # mypy configuration does not infer. The registry never retrieves URLs.
        registry = Registry(retrieve=_no_retrieval)  # type: ignore[call-arg]
        resolver = registry.resolver_with_root(Resource.from_contents(self._schema, default_specification=DRAFT202012))
        try:
            for node in nodes:
                for keyword in ("$ref", "$dynamicRef"):
                    if keyword in node:
                        resolver.lookup(node[keyword])
        except Unresolvable:
            raise SchemaContractError("unresolved_reference") from None
        validation_schema = deepcopy(self._schema)
        # Every accepted declaration has the same dialect. Removing its marker
        # only in the validator copy prevents evolve() selecting an unbounded
        # stock validator for a nested declared schema.
        for node in _check_local_schema(validation_schema):
            node.pop("$schema", None)
        self._validator = _Validator(validation_schema, registry=registry)

    @property
    def schema(self) -> Any:
        return deepcopy(self._schema)

    def validate(self, value: Any) -> None:
        """Raise a value-free diagnostic on a mismatch, unresolved ref or limit."""
        candidate = _json_copy(value, MAX_VALUE_BYTES)
        token = _BUDGET.set(_ValidationBudget(time.monotonic() + 0.25))
        try:
            error = next(self._validator.iter_errors(candidate), None)
            if error is not None:
                keyword = error.validator if error.validator in Draft202012Validator.VALIDATORS else "schema"
                raise SchemaContractError(f"validation_{keyword}")
        except (RecursionError, TimeoutError):
            raise SchemaContractError("validation_limit") from None
        except Unresolvable:
            raise SchemaContractError("unresolved_reference") from None
        finally:
            _BUDGET.reset(token)


def validate_tool_input(parameters: dict[str, Any], arguments: dict[str, Any]) -> None:
    """Validate captured tool input before approval or dispatch, without coercion."""
    SchemaContract(parameters).validate(arguments)


def validate_tool_output(result: ToolResult, contract: SchemaContract | None) -> ToolResult:
    """Validate and detach typed evidence; failed tools need no success payload."""
    from dataclasses import replace

    from henchman.tools.base import ToolResult
    from henchman.utils.tool_results import tool_result_from_payload, tool_result_payload

    if (not isinstance(result, ToolResult) or not isinstance(result.content, str)
            or type(result.success) is not bool or type(result.structured_content_present) is not bool
            or (result.display is not None and not isinstance(result.display, str))):
        raise SchemaContractError("result_shape")
    if not result.structured_content_present and result.structured_content is not None:
        raise SchemaContractError("result_presence")
    payload = tool_result_payload(result)
    if result.success and contract is not None:
        if not result.structured_content_present:
            raise SchemaContractError("missing_structured_output")
        contract.validate(result.structured_content)
    return replace(tool_result_from_payload(result.content, payload), display=result.display)
