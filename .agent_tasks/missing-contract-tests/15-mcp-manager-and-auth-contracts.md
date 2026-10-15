# Missing Contract: MCP Manager and Auth Service Interfaces

**Severity:** Medium  
**Location:** `src/henchman/mcp/manager.py`, `src/henchman/mcp/auth.py`

## The gap

### McpManager

`test_mcp_contracts.py` covers the `McpClientProtocol` and validates MCP
payload shapes (`McpToolDefinition`, `McpToolResult`). **No contract test**
verifies:

- `McpManager.get_all_tools()` returns tools with correct prefixed names
- `McpManager.connect_server(name)` initializes clients
- `McpManager.disconnect_all()` cleans up
- Server configs from `McpServerConfig` are properly passed to the client factory

### MCP Auth

`src/henchman/mcp/auth.py` handles authentication tokens for MCP servers.
**No contract test** exists for:
- Token persistence and retrieval
- Auth header construction
- Token lifecycle (set, clear, status)

### MCP Config

`src/henchman/mcp/config.py` handles configuration loading for MCP servers.
**No contract test** validates that configs produce valid `McpServerConfig` objects.

## What's consumed

- `McpManager` is consumed by `cli/repl.py`, `cli/tool_manager.py`, and
  `cli/output_handler.py`.
- MCP auth is consumed by `mcp/client.py` for server connections.
- MCP config is consumed by the CLI startup pipeline.

## Recommended contract test

Add to `tests/contracts/test_mcp_contracts.py`:

```python
def test_mcp_manager_get_all_tools_contract():
    """McpManager.get_all_tools() must prefix tool names with 'mcp_SERVERNAME_'."""
    double = _McpClientDouble(name="test")
    double._tools = [McpToolDefinition(name="search", description="...", input_schema={})]

    def factory(name, config, verbose):
        return double

    manager = McpManager(configs={"my_server": McpServerConfig(command="true")}, client_factory=factory)
    tools = manager.get_all_tools()
    assert len(tools) == 1
    assert tools[0].name == "mcp_my_server_search"


def test_mcp_auth_token_lifecycle_contract():
    """MCP auth service should support set/clear/status operations."""
    auth = McpAuthService(...)
    
    assert auth.status("my_server") is None
    auth.set("my_server", "token-123")
    assert auth.status("my_server") == "token-123"
    auth.clear("my_server")
    assert auth.status("my_server") is None


def test_mcp_server_config_matches_contract(contract_suite):
    """MCP server configurations must satisfy the config contract."""
    config = McpServerConfig(
        command="uvx",
        args=["mcp-server"],
        env={"DEBUG": "1"},
        trusted=True,
    )
    payload = asdict(config)
    assert_contract_matches(
        payload=payload,
        schema_name="config/mcp_server_config",
        contract_suite=contract_suite,
    )
```

## Existing coverage

The MCP tool definition and result schemas have contract tests. The
`McpManager` orchestration and auth lifecycle are the gaps.

## Priority

Medium — MCP is a significant integration point and manager behavior is
critical for tool availability.
