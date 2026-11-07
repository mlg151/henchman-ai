"""Both MCP transport profiles remain inspectable typed configuration payloads."""

import pytest

from henchman.config.schema import McpServerConfig, Settings
from henchman.mcp.config import McpServerConfig as LegacyMcpServerConfig
from tests.contracts.helpers import assert_contract_matches, serialize_contract_value


@pytest.mark.parametrize("raw", [
    {"command": "fixture", "args": ["--stdio"]},
    {"transport": "streamable_http", "url": "https://example.test/mcp", "request_timeout_seconds": 12},
])
def test_transport_profiles_match_settings_and_compatibility_contracts(contract_suite, raw):
    config = McpServerConfig(**raw)
    for value in (config, LegacyMcpServerConfig.from_dict(raw)):
        assert_contract_matches(payload=serialize_contract_value(value), schema_name="config/mcp_server_config",
                                contract_suite=contract_suite)
    assert_contract_matches(payload=serialize_contract_value(Settings(mcp_servers={"fixture": config})),
                            schema_name="config/settings", contract_suite=contract_suite)
