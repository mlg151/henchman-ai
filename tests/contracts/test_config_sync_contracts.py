"""Version-compatible file-transfer shape with no persisted acceptance authority."""

from copy import deepcopy

import pytest
from jsonschema import Draft202012Validator

from tests.config.test_settings_control_transfer import CONTROLS
from tests.contracts.helpers import load_contract_schema


def test_transfer_schema_accepts_legacy_ui_and_new_control_payloads() -> None:
    schema = load_contract_schema("config/sync_payload")
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    for payload in ({}, {"ui": {"theme": "light", "layout": {"compact_tables": False}}}, CONTROLS):
        assert not list(validator.iter_errors(payload))


@pytest.mark.parametrize(
    "payload",
    [
        {"accept_control_changes": True},
        {"providers": {}},
        {"tools": {}},
        {"operations": {"persistence": "unsafe"}},
        {"usage": {"limits": {"max_requests": -1}}},
        {"usage": {"limits": {"max_tokens": True}}},
        {"usage": {"prices": [{"provider": "x", "model": "y", "token": "private"}]}},
        {
            "verification": {
                "checks": [{"kind": "file_changed", "path": "x.py", "baseline_captured": True}]
            }
        },
    ],
)
def test_transfer_contract_rejects_unknown_authority_and_invalid_shapes(payload) -> None:
    original = deepcopy(payload)
    validator = Draft202012Validator(load_contract_schema("config/sync_payload"))
    assert list(validator.iter_errors(payload))
    assert payload == original
