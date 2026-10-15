"""Contract tests for MCP (Model Context Protocol) boundaries."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from henchman.config.schema import McpServerConfig
from henchman.mcp.auth import McpAuthService
from henchman.mcp.client import (
    McpClient,
    McpClientProtocol,
    McpToolDefinition,
    McpToolResult,
)
from henchman.mcp.manager import McpManager
from tests.contracts.helpers import assert_contract_matches, serialize_contract_value


class _McpClientDouble:
    """Runtime double that satisfies the McpClientProtocol."""

    def __init__(self, name: str) -> None:
        self.name = name
        self._connected = False
        self._tools: list[McpToolDefinition] = []

    async def connect(self) -> None:
        self._connected = True

    async def disconnect(self) -> None:
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def get_tools(self) -> list[McpToolDefinition]:
        return self._tools

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> McpToolResult:
        return McpToolResult(content=f"Called {name} with {arguments}")


def _accept_mcp_client(client: McpClientProtocol) -> McpClientProtocol:
    """Type-level helper for the mcp-client contract."""
    return client


def test_mcp_client_matches_protocol() -> None:
    """The default McpClient should satisfy the McpClientProtocol."""
    client = McpClient(name="test-server", config=McpServerConfig(command="true"))
    # This check is both static (mypy) and runtime (isinstance)
    assert isinstance(client, McpClientProtocol)
    verified = _accept_mcp_client(client)
    assert verified.name == "test-server"


def test_mcp_client_double_matches_protocol() -> None:
    """A mock double should also satisfy the McpClientProtocol."""
    double = _McpClientDouble(name="mock-server")
    assert isinstance(double, McpClientProtocol)
    verified = _accept_mcp_client(double)
    assert verified.name == "mock-server"


@pytest.mark.anyio
async def test_mcp_client_contract_behavior() -> None:
    """Verify the expected behavior of any McpClientProtocol implementation."""
    client: McpClientProtocol = _McpClientDouble(name="test")

    await client.connect()
    assert client.is_connected() is True

    tools = client.get_tools()
    assert isinstance(tools, list)

    result = await client.call_tool("echo", {"msg": "hi"})
    assert isinstance(result, McpToolResult)
    assert not result.is_error

    await client.disconnect()
    assert client.is_connected() is False


def test_mcp_manager_consumer_contract() -> None:
    """The McpManager should be able to work with anything satisfying the protocol."""
    # We can now inject a double via the factory
    double_instance = _McpClientDouble(name="injected")

    def factory(_name: str, _config: Any, _verbose: bool) -> McpClientProtocol:
        return double_instance

    manager = McpManager(
        configs={"test": McpServerConfig(command="true")},
        client_factory=factory
    )
    assert manager.clients == {}

    # Verify the existing coupling for now as a baseline.
    client = McpClient(name="baseline", config=McpServerConfig(command="true"))
    assert isinstance(client, McpClientProtocol)


@pytest.mark.anyio
async def test_mcp_manager_integration_with_protocol_double() -> None:
    """Verify McpManager correctly uses an injected protocol double."""
    double_instance = _McpClientDouble(name="injected")
    double_instance._tools = [
        McpToolDefinition(name="test_tool", description="A test tool", input_schema={})
    ]

    def factory(_name: str, _config: Any, _verbose: bool) -> McpClientProtocol:
        return double_instance

    manager = McpManager(
        configs={"test": McpServerConfig(command="true")},
        client_factory=factory
    )

    await manager.connect_server("test")
    assert "test" in manager.clients
    assert manager.clients["test"] is double_instance
    assert double_instance.is_connected() is True

    tools = manager.get_all_tools()
    assert len(tools) == 1
    assert tools[0].name == "mcp_test_test_tool"


def test_mcp_payloads_match_contracts(contract_suite) -> None:
    """Serialized MCP payloads should satisfy their contracts."""
    tool_def = McpToolDefinition(
        name="test_tool",
        description="A test tool",
        input_schema={"type": "object", "properties": {"foo": {"type": "string"}}}
    )
    tool_result = McpToolResult(
        content="success",
        is_error=False,
    )

    assert_contract_matches(
        payload=serialize_contract_value(tool_def),
        schema_name="mcp/tool_definition",
        contract_suite=contract_suite,
    )
    assert_contract_matches(
        payload=serialize_contract_value(tool_result),
        schema_name="mcp/tool_result",
        contract_suite=contract_suite,
    )


# ===========================================================================
# MCP server config shape contracts
# ===========================================================================


def test_mcp_server_config_matches_contract(contract_suite) -> None:
    """McpServerConfig shape must satisfy the config schema."""
    config = McpServerConfig(
        command="uvx",
        args=["mcp-server"],
        env={"DEBUG": "1"},
        trusted=True,
    )
    payload = serialize_contract_value(config)
    assert_contract_matches(
        payload=payload,
        schema_name="config/mcp_server_config",
        contract_suite=contract_suite,
    )


def test_mcp_server_config_minimal_matches_contract(contract_suite) -> None:
    """McpServerConfig with only required fields must satisfy the schema."""
    config = McpServerConfig(command="true")
    payload = serialize_contract_value(config)
    assert_contract_matches(
        payload=payload,
        schema_name="config/mcp_server_config",
        contract_suite=contract_suite,
    )


# ===========================================================================
# MCP auth service lifecycle contracts
# ===========================================================================


class TestMcpAuthServiceContract:
    """McpAuthService must satisfy the token lifecycle contract."""

    def test_auth_token_set_and_get(self, tmp_path: Path) -> None:
        """Set and get should roundtrip correctly."""
        auth = McpAuthService(project_root=tmp_path)
        auth.set_token("my_server", "token-123")
        assert auth.get_token("my_server") == "token-123"

    def test_auth_token_get_nonexistent(self, tmp_path: Path) -> None:
        """Getting a token for an unknown server should return None."""
        auth = McpAuthService(project_root=tmp_path)
        assert auth.get_token("nonexistent") is None

    def test_auth_token_clear(self, tmp_path: Path) -> None:
        """Clearing a token should remove it."""
        auth = McpAuthService(project_root=tmp_path)
        auth.set_token("my_server", "token-123")
        assert auth.clear_token("my_server") is True
        assert auth.get_token("my_server") is None

    def test_auth_token_clear_nonexistent(self, tmp_path: Path) -> None:
        """Clearing a non-existent token should return False."""
        auth = McpAuthService(project_root=tmp_path)
        assert auth.clear_token("nonexistent") is False

    def test_auth_token_has_token(self, tmp_path: Path) -> None:
        """Has token should reflect token presence."""
        auth = McpAuthService(project_root=tmp_path)
        assert auth.has_token("my_server") is False
        auth.set_token("my_server", "token-123")
        assert auth.has_token("my_server") is True

    def test_auth_token_overwrite(self, tmp_path: Path) -> None:
        """Setting a token twice should overwrite."""
        auth = McpAuthService(project_root=tmp_path)
        auth.set_token("my_server", "token-123")
        auth.set_token("my_server", "token-456")
        assert auth.get_token("my_server") == "token-456"

    def test_list_statuses(self, tmp_path: Path) -> None:
        """list_statuses should return presence mapping."""
        auth = McpAuthService(project_root=tmp_path)
        auth.set_token("server_a", "tok-a")
        auth.set_token("server_b", "tok-b")
        statuses = auth.list_statuses()
        assert statuses == {"server_a": True, "server_b": True}
