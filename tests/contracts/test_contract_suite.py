"""Tests for the shared contract validator."""

from __future__ import annotations

from henchman.testing.contract import ContractSuite


def test_validate_json_schema_accepts_nested_objects_and_arrays() -> None:
    """The contract validator should support nested JSON-schema-style payloads."""
    suite = ContractSuite()
    schema = {
        "type": "object",
        "required": ["status", "items"],
        "properties": {
            "status": {"type": "string", "enum": ["ok", "error"]},
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["id", "enabled"],
                    "properties": {
                        "id": {"type": "string"},
                        "enabled": {"type": "boolean"},
                    },
                    "additionalProperties": False,
                },
            },
        },
        "additionalProperties": False,
    }

    payload = {
        "status": "ok",
        "items": [
            {"id": "item-1", "enabled": True},
            {"id": "item-2", "enabled": False},
        ],
    }

    assert suite.validate_json_schema(payload, schema) == []


def test_validate_json_schema_reports_contract_violations() -> None:
    """The contract validator should report schema drift precisely."""
    suite = ContractSuite()
    schema = {
        "type": "object",
        "required": ["status", "count"],
        "properties": {
            "status": {"type": "string", "enum": ["ok"]},
            "count": {"type": "integer", "minimum": 0},
        },
        "additionalProperties": False,
    }

    payload = {
        "status": "bad",
        "count": -1,
        "unexpected": True,
    }

    errors = suite.validate_json_schema(payload, schema)

    assert "$.status expected one of ['ok'], got 'bad'" in errors
    assert "$.count expected value >= 0, got -1" in errors
    assert "$ contains unexpected property 'unexpected'" in errors
