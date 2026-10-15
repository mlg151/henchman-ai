"""Contract assertions for Tier 8 API and runtime payloads."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

JsonSchema = Mapping[str, Any]


def _is_integer(value: Any) -> bool:
    """Return whether *value* is a JSON-schema integer."""
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value: Any) -> bool:
    """Return whether *value* is a JSON-schema number."""
    return (isinstance(value, int | float) and not isinstance(value, bool))


def _matches_json_type(value: Any, expected_type: str) -> bool:
    """Return whether a value matches one JSON-schema type name."""
    if expected_type == "array":
        return isinstance(value, list)
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "integer":
        return _is_integer(value)
    if expected_type == "null":
        return value is None
    if expected_type == "number":
        return _is_number(value)
    if expected_type == "object":
        return isinstance(value, Mapping)
    if expected_type == "string":
        return isinstance(value, str)
    return True


def _normalize_expected_types(raw_type: object) -> list[str]:
    """Normalize JSON-schema ``type`` values to a list of strings."""
    if isinstance(raw_type, str):
        return [raw_type]
    if isinstance(raw_type, list):
        return [str(item) for item in raw_type]
    return []


def _validate_type(value: Any, schema: JsonSchema, path: str) -> list[str]:
    """Validate the JSON-schema ``type`` keyword."""
    expected_types = _normalize_expected_types(schema.get("type"))
    if not expected_types:
        return []
    if any(_matches_json_type(value, expected_type) for expected_type in expected_types):
        return []
    allowed = ", ".join(expected_types)
    return [f"{path} expected type [{allowed}], got {type(value).__name__}"]


def _validate_enum(value: Any, schema: JsonSchema, path: str) -> list[str]:
    """Validate the JSON-schema ``enum`` keyword."""
    enum_values = schema.get("enum")
    if not isinstance(enum_values, list):
        return []
    if value in enum_values:
        return []
    return [f"{path} expected one of {enum_values!r}, got {value!r}"]


def _validate_numeric_bounds(value: Any, schema: JsonSchema, path: str) -> list[str]:
    """Validate JSON-schema numeric bound keywords."""
    if not _is_number(value):
        return []
    errors: list[str] = []
    minimum = schema.get("minimum")
    if isinstance(minimum, int | float) and value < minimum:
        errors.append(f"{path} expected value >= {minimum}, got {value}")
    maximum = schema.get("maximum")
    if isinstance(maximum, int | float) and value > maximum:
        errors.append(f"{path} expected value <= {maximum}, got {value}")
    return errors


def _validate_any_of(value: Any, schema: JsonSchema, path: str) -> list[str]:
    """Validate the JSON-schema ``anyOf`` keyword."""
    raw_options = schema.get("anyOf")
    if not isinstance(raw_options, list):
        return []
    for option in raw_options:
        if isinstance(option, Mapping) and not _validate_schema(value, option, path):
            return []
    return [f"{path} did not match any allowed schema"]


def _validate_array(value: Any, schema: JsonSchema, path: str) -> list[str]:
    """Validate array items when the payload is an array."""
    if not isinstance(value, list):
        return []
    item_schema = schema.get("items")
    if not isinstance(item_schema, Mapping):
        return []
    errors: list[str] = []
    for index, item in enumerate(value):
        errors.extend(_validate_schema(item, item_schema, f"{path}[{index}]"))
    return errors


def _validate_object(value: Any, schema: JsonSchema, path: str) -> list[str]:
    """Validate object properties when the payload is an object."""
    if not isinstance(value, Mapping):
        return []

    errors: list[str] = []
    properties = schema.get("properties", {})
    property_schemas = properties if isinstance(properties, Mapping) else {}
    required = schema.get("required", [])

    if isinstance(required, list):
        for field_name in required:
            if isinstance(field_name, str) and field_name not in value:
                errors.append(f"{path} missing required property '{field_name}'")

    for field_name, field_schema in property_schemas.items():
        if field_name in value and isinstance(field_schema, Mapping):
            errors.extend(_validate_schema(value[field_name], field_schema, f"{path}.{field_name}"))

    additional_properties = schema.get("additionalProperties", True)
    if additional_properties is False:
        for field_name in value:
            if field_name not in property_schemas:
                errors.append(f"{path} contains unexpected property '{field_name}'")
    elif isinstance(additional_properties, Mapping):
        for field_name, field_value in value.items():
            if field_name not in property_schemas:
                errors.extend(
                    _validate_schema(
                        field_value,
                        additional_properties,
                        f"{path}.{field_name}",
                    ),
                )

    return errors


def _validate_schema(value: Any, schema: JsonSchema, path: str) -> list[str]:
    """Validate a value against the supported JSON-schema subset."""
    if not schema:
        return []

    errors: list[str] = []
    errors.extend(_validate_any_of(value, schema, path))
    if errors:
        return errors

    errors.extend(_validate_type(value, schema, path))
    if errors:
        return errors

    const = schema.get("const")
    if "const" in schema and value != const:
        errors.append(f"{path} expected constant {const!r}, got {value!r}")

    errors.extend(_validate_enum(value, schema, path))
    errors.extend(_validate_numeric_bounds(value, schema, path))
    errors.extend(_validate_array(value, schema, path))
    errors.extend(_validate_object(value, schema, path))
    return errors


class ContractSuite:
    """Validate response payloads against lightweight shape contracts."""

    def validate(
        self,
        payload: Mapping[str, Any],
        schema: Mapping[str, type[Any]],
    ) -> list[str]:
        """Validate a payload against a flat contract schema.

        Args:
            payload: Response payload to validate.
            schema: Mapping of required field name to expected type.

        Returns:
            List of validation errors. Empty means the contract passed.
        """
        if not all(isinstance(expected_type, type) for expected_type in schema.values()):
            return self.validate_json_schema(payload, schema)

        errors: list[str] = []
        for field_name, expected_type in schema.items():
            if field_name not in payload:
                errors.append(f"Missing required field: {field_name}")
                continue
            value = payload[field_name]
            if not isinstance(value, expected_type):
                errors.append(
                    f"Field {field_name} expected {expected_type.__name__}, got {type(value).__name__}",
                )
        return errors

    def validate_json_schema(
        self,
        payload: Any,
        schema: JsonSchema,
    ) -> list[str]:
        """Validate a payload against a JSON-schema-style contract subset.

        Supported keywords:
        - ``type``
        - ``properties``
        - ``required``
        - ``items``
        - ``enum``
        - ``const``
        - ``additionalProperties``
        - ``anyOf``
        - ``minimum`` / ``maximum``

        Args:
            payload: Payload to validate.
            schema: JSON-schema-style contract.

        Returns:
            List of validation errors. Empty means the contract passed.
        """
        return _validate_schema(payload, schema, "$")
