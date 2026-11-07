"""Transport settings are explicit, bounded, and compatible with stdio configs."""

from __future__ import annotations

import pytest

from henchman.config.schema import McpServerConfig
from henchman.mcp.config import McpServerConfig as LegacyMcpServerConfig


def test_existing_command_config_keeps_stdio_defaults():
    config = McpServerConfig(command="fixture", env={"TOKEN": "${TOKEN}"})
    assert config.transport == "stdio"
    assert config.url is None
    assert config.request_timeout_seconds == 30
    assert config.negotiation_timeout_seconds == 40
    assert config.catalog_timeout_seconds == 60


@pytest.mark.parametrize("url", [
    "https://example.test/mcp", "https://example.test:8443/mcp", "http://127.0.0.1:8765/mcp", "http://[::1]:8765/mcp",
])
def test_explicit_http_endpoint_needs_no_stdio_command(url):
    config = McpServerConfig(transport="streamable_http", url=url)
    assert config.command is None
    assert config.url == url
    assert config.args == [] and config.env == {}


@pytest.mark.parametrize("payload", [
    {}, {"command": ""}, {"command": "   "},
    {"command": "fixture", "url": "https://example.test/mcp"},
    {"transport": "streamable_http"},
    {"transport": "streamable_http", "url": "https://example.test/mcp", "command": "fixture"},
    {"transport": "streamable_http", "url": "https://example.test/mcp", "args": ["--secret"]},
    {"transport": "streamable_http", "url": "https://example.test/mcp", "env": {"TOKEN": "private"}},
    {"transport": "sse", "url": "https://example.test/mcp"},
    {"transport": "streamable_http", "url": "https://example.test/mcp", "headers": {"Authorization": "private"}},
])
def test_mixed_missing_or_unsupported_transport_settings_fail(payload):
    with pytest.raises(ValueError):
        McpServerConfig(**payload)


@pytest.mark.parametrize("url", [
    "http://example.test/mcp", "http://localhost/mcp", "ftp://example.test/mcp", "/mcp",
    "https://user:private@example.test/mcp", "https://example.test/mcp?token=private",
    "https://example.test/mcp#fragment", "https://example.test/mcp?", "https://example.test/mcp#",
    "https://example.test/\nmcp", " https://example.test/mcp", "https://example.test/with space",
    "https://example.test:invalid/mcp", "https://example.test:99999/mcp", "https:///mcp",
    "https://example.test\\evil.test/mcp", "http://[fe80::1%eth0]/mcp",
])
def test_http_endpoint_rejects_ambiguous_or_credential_bearing_destinations(url):
    with pytest.raises(ValueError):
        McpServerConfig(transport="streamable_http", url=url)


@pytest.mark.parametrize("field", ["request_timeout_seconds", "negotiation_timeout_seconds", "catalog_timeout_seconds"])
@pytest.mark.parametrize("value", [0, -1, float("inf"), float("nan"), True, 3601])
def test_transport_deadlines_must_be_finite_positive_and_bounded(field, value):
    with pytest.raises(ValueError):
        McpServerConfig(command="fixture", **{field: value})


@pytest.mark.parametrize("config", [
    McpServerConfig(command="fixture", args=["-u"], env={"TOKEN": "${TOKEN}"}),
    {"transport": "streamable_http", "url": "https://example.test/mcp", "request_timeout_seconds": 12},
])
def test_legacy_config_adapter_round_trips_the_same_validated_transport(config):
    raw = config.model_dump() if isinstance(config, McpServerConfig) else config
    legacy = LegacyMcpServerConfig.from_dict(raw)
    settings = McpServerConfig.model_validate(legacy.to_dict())
    assert settings.model_dump() == McpServerConfig.model_validate(raw).model_dump()


def test_legacy_http_constructor_does_not_reinterpret_endpoint_as_command():
    config = LegacyMcpServerConfig(transport="streamable_http", url="https://example.test/mcp")
    assert config.command is None
    assert config.url == "https://example.test/mcp"
