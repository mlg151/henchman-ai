"""Published settings shapes preserve restricted controls and budget lifetime."""

import pytest

from henchman.config.schema import Settings
from henchman.testing.contract import ContractSuite
from tests.contracts.helpers import load_contract_schema


@pytest.mark.parametrize("persistence", ["process", "durable"])
@pytest.mark.parametrize("roots", [None, [], [".", "/explicit/root"]])
def test_settings_contract_preserves_null_empty_and_explicit_roots(persistence, roots):
    settings = Settings.model_validate({
        "usage": {"persistence": persistence},
        "tools": {"filesystem_read_roots": roots, "filesystem_write_roots": [], "network_access": "disabled"},
    })
    payload = settings.model_dump(mode="json")
    suite = ContractSuite()
    assert suite.validate_json_schema(payload, load_contract_schema("config/settings")) == []
    assert suite.validate_json_schema(payload["tools"], load_contract_schema("config/tool_settings")) == []
    assert payload["tools"]["filesystem_read_roots"] == roots
    assert payload["usage"]["persistence"] == persistence


@pytest.mark.parametrize("group,key,value", [
    ("usage", "persistence", "cloud"),
    ("tools", "network_access", "allow_anything"),
    ("tools", "filesystem_read_roots", "not-an-array"),
    ("tools", "filesystem_write_roots", [42]),
])
def test_settings_contract_rejects_invalid_control_shapes(group, key, value):
    payload = Settings().model_dump(mode="json")
    payload[group][key] = value
    assert ContractSuite().validate_json_schema(payload, load_contract_schema("config/settings"))
