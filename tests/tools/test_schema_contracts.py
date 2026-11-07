"""Canonical contracts validate locally without rewriting tool input or fetching refs."""

from copy import deepcopy

import pytest

from henchman.tools.contracts import SchemaContract, SchemaContractError, validate_tool_input


def test_nested_local_reference_preserves_missing_null_and_originals():
    schema = {
        "$defs": {"value": {"type": ["string", "null"]}},
        "type": "object", "properties": {"value": {"$ref": "#/$defs/value", "default": "fallback"}},
        "additionalProperties": False,
    }
    before = deepcopy(schema)
    contract = SchemaContract(schema)
    for arguments in ({}, {"value": None}, {"value": "text"}):
        original = deepcopy(arguments)
        contract.validate(arguments)
        assert arguments == original
    assert schema == before
    with pytest.raises(SchemaContractError):
        contract.validate({"value": 3})


@pytest.mark.parametrize(("schema", "value"), [
    ({"type": "null"}, None),
    ({"type": "array", "items": {"type": "integer"}, "minItems": 1}, [1, 2]),
    ({"oneOf": [{"type": "integer"}, {"type": "string"}]}, "value"),
    ({"type": "boolean"}, False),
    (True, {"any": "json"}),
])
def test_output_contracts_allow_scalars_arrays_and_null(schema, value):
    SchemaContract(schema).validate(value)


def test_required_nullable_is_different_from_optional():
    contract = SchemaContract({"type": "object", "properties": {"value": {"type": "null"}}, "required": ["value"]})
    contract.validate({"value": None})
    with pytest.raises(SchemaContractError, match="required"):
        contract.validate({})


@pytest.mark.parametrize("reference", ["https://example.com/schema", "file:///tmp/schema", "other.json#/value"])
def test_external_references_fail_during_compilation(reference):
    with pytest.raises(SchemaContractError, match="external_reference"):
        SchemaContract({"$defs": {"hidden": {"$ref": reference}}})


def test_annotation_examples_and_property_names_are_not_schema_keywords():
    SchemaContract({"type": "object", "properties": {"$ref": {"type": "string"}},
                    "examples": [{"$ref": "https://not-a-schema.example"}]}).validate({"$ref": "value"})


def test_recursive_local_definition_accepts_bounded_tree():
    schema = {"$defs": {"node": {"type": "object", "properties": {"child": {"$ref": "#/$defs/node"}},
                                 "additionalProperties": False}}, "$ref": "#/$defs/node"}
    SchemaContract(schema).validate({"child": {"child": {}}})


def test_dangling_reference_fails_even_in_unused_definition():
    with pytest.raises(SchemaContractError, match="unresolved_reference"):
        SchemaContract({"$defs": {"hidden": {"$ref": "#/$defs/missing"}}})


def test_declared_dialect_and_anchors_keep_local_recursion_bounded():
    schema = {"$schema": "https://json-schema.org/draft/2020-12/schema", "$anchor": "node",
              "type": "object", "properties": {"next": {"$ref": "#node"}}}
    SchemaContract(schema).validate({"next": {}})
    with pytest.raises(SchemaContractError, match="validation_limit"):
        SchemaContract({"$schema": schema["$schema"], "$ref": "#"}).validate({})


def test_nonproductive_recursion_is_a_diagnostic_failure():
    with pytest.raises(SchemaContractError, match="validation_limit"):
        SchemaContract({"$ref": "#"}).validate({})


@pytest.mark.parametrize("schema", [{"type": "not-a-type"}, {"$schema": "http://json-schema.org/draft-07/schema#"},
                                   {"properties": {"nested": {"$id": "https://example.com/nested"}}}])
def test_invalid_or_unsupported_dialects_fail_explicitly(schema):
    with pytest.raises(SchemaContractError):
        SchemaContract(schema)


def test_schema_and_input_are_detached_from_mutable_caller_values():
    schema = {"type": "integer", "minimum": 3}
    contract = SchemaContract(schema)
    schema["minimum"] = 0
    exposed = contract.schema
    exposed["minimum"] = 0
    with pytest.raises(SchemaContractError):
        contract.validate(1)


@pytest.mark.parametrize("value", [float("nan"), {1: "not-json"}, {"value": {1, 2}}])
def test_non_json_values_are_not_coerced(value):
    with pytest.raises(SchemaContractError, match="invalid_json"):
        SchemaContract(True).validate(value)


def test_complexity_and_payload_are_bounded():
    with pytest.raises(SchemaContractError, match="payload_limit"):
        SchemaContract(True).validate("x" * (1024 * 1024 + 1))
    nested = {}
    for _ in range(70):
        nested = {"child": nested}
    with pytest.raises(SchemaContractError, match="depth_limit"):
        SchemaContract(True).validate(nested)


def test_unsupported_regex_is_rejected_before_unbounded_matching():
    with pytest.raises(SchemaContractError, match="unsupported_regex"):
        SchemaContract({"type": "string", "pattern": "(a+)+$"})
    contract = SchemaContract({"type": "string", "pattern": "^[a-z]+$"})
    with pytest.raises(SchemaContractError) as error:
        contract.validate("private-canary")
    assert "private-canary" not in str(error.value)


def test_pattern_properties_and_unevaluated_properties_keep_canonical_meaning():
    contract = SchemaContract({"type": "object", "patternProperties": {"^x": {"type": "integer"}},
                               "unevaluatedProperties": False})
    contract.validate({"x1": 2})
    with pytest.raises(SchemaContractError):
        contract.validate({"x1": None})
    with pytest.raises(SchemaContractError):
        contract.validate({"y": 2})


def test_input_helper_rejects_invalid_before_dispatch_without_exposing_values():
    with pytest.raises(SchemaContractError, match="type") as error:
        validate_tool_input({"type": "object", "properties": {"number": {"type": "integer"}}},
                            {"number": "credential-canary"})
    assert "credential-canary" not in str(error.value)
