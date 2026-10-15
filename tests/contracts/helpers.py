"""Helpers for contract-schema loading and payload normalization."""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from henchman.testing.contract import ContractSuite

SCHEMA_DIR = Path(__file__).parent / "schemas"


def load_contract_schema(name: str) -> dict[str, Any]:
    """Load a contract schema from the contract schema directory."""
    path = SCHEMA_DIR / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def serialize_contract_value(value: Any) -> Any:
    """Convert runtime objects into contract-friendly payloads."""
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return serialize_contract_value(asdict(value))
    if hasattr(value, "model_dump") and callable(value.model_dump):
        return serialize_contract_value(value.model_dump(mode="json"))
    if isinstance(value, dict):
        return {str(key): serialize_contract_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [serialize_contract_value(item) for item in value]
    if isinstance(value, tuple):
        return [serialize_contract_value(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "isoformat") and callable(value.isoformat):
        return value.isoformat()
    return value


def assert_contract_matches(
    *,
    payload: Any,
    schema_name: str,
    contract_suite: ContractSuite,
) -> None:
    """Assert that a payload satisfies the named contract schema."""
    schema = load_contract_schema(schema_name)
    errors = contract_suite.validate_json_schema(payload, schema)
    assert errors == []
