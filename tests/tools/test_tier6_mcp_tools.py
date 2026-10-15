"""Tests for Tier 6 MCP management builtin tools."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from henchman.cli.tool_manager import ToolManager
from henchman.config.schema import McpServerConfig as SchemaMcpServerConfig
from henchman.config.schema import Settings
from henchman.mcp.auth import McpAuthService
from henchman.mcp.client import McpToolDefinition
from henchman.mcp.manager import McpManager


@dataclass(slots=True)
class _FakeClient:
    """Simple connected-client state used by the fake MCP manager."""

    is_connected: bool


class _FakeMcpManager:
    """Minimal MCP manager stub for builtin tool tests."""

    def __init__(self) -> None:
        from henchman.config.schema import McpServerConfig as SchemaMcpServerConfig

        self.configs = {
            "serena": SchemaMcpServerConfig(command="echo", args=["serena"], trusted=True),
            "filesystem": SchemaMcpServerConfig(command="echo", args=["filesystem"], trusted=False),
        }
        self.clients: dict[str, _FakeClient] = {}
        self._tools = {
            "serena": [
                McpToolDefinition(
                    name="find_symbol",
                    description="Find symbol",
                    input_schema={"type": "object", "properties": {"name": {"type": "string"}}},
                ),
            ],
            "filesystem": [
                McpToolDefinition(
                    name="read_file",
                    description="Read file",
                    input_schema={"type": "object", "properties": {"path": {"type": "string"}}},
                ),
            ],
        }

    async def connect_server(self, name: str) -> None:
        self.clients[name] = _FakeClient(is_connected=True)

    async def disconnect_server(self, name: str) -> None:
        self.clients.pop(name, None)

    def list_servers(self) -> list[dict[str, object]]:
        return [
            {
                "name": name,
                "connected": name in self.clients,
                "trusted": config.trusted,
            }
            for name, config in self.configs.items()
        ]

    def discover_tools(self, server: str | None = None) -> list[McpToolDefinition]:
        if server is not None:
            return list(self._tools.get(server, []))
        discovered: list[McpToolDefinition] = []
        for tools in self._tools.values():
            discovered.extend(tools)
        return discovered


def test_builtin_surface_includes_tier6_mcp_tools() -> None:
    """The builtin surface should expose Tier 6 MCP management tools."""

    import henchman.tools.builtins as builtins_mod

    assert {"MCPTool", "McpAuthTool"} <= set(builtins_mod.__all__)

    def _instantiate(tool_class: object) -> object:
        if tool_class is builtins_mod.ShellTool:
            return builtins_mod.ShellTool(default_timeout=60)
        if tool_class is builtins_mod.RagSearchTool:
            from unittest.mock import MagicMock

            return builtins_mod.RagSearchTool(store=MagicMock())
        return tool_class()

    names = {_instantiate(tool_class).name for tool_class in builtins_mod.iter_available_builtin_tool_classes()}

    assert {"mcp", "mcp_auth"} <= names


@pytest.mark.anyio
async def test_mcp_tools_manage_auth_and_server_lifecycle(tmp_path: Path) -> None:
    """Tier 6 MCP tools should persist auth state and manage server lifecycle."""

    manager = ToolManager()
    manager.bind_runtime(project_root=tmp_path, mcp_manager=_FakeMcpManager())
    manager.register_builtin_tools()

    stored = await manager.registry.execute(
        "mcp_auth",
        {"action": "set", "server": "serena", "token": "secret-token"},
    )
    status_before = await manager.registry.execute("mcp", {"action": "status"})
    connected = await manager.registry.execute("mcp", {"action": "connect", "server": "serena"})
    discovered = await manager.registry.execute("mcp", {"action": "discover", "server": "serena"})
    status_after = await manager.registry.execute("mcp", {"action": "status"})
    cleared = await manager.registry.execute(
        "mcp_auth",
        {"action": "clear", "server": "serena"},
    )

    assert stored.success is True
    assert connected.success is True
    assert discovered.success is True
    assert cleared.success is True
    assert "serena" in status_before.content
    assert "auth=yes" in status_before.content
    assert "find_symbol" in discovered.content
    assert "connected=yes" in status_after.content
    assert (tmp_path / ".henchman" / "mcp" / "auth.json").exists()


@pytest.mark.anyio
async def test_mcp_manager_restores_persisted_auth_on_startup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Startup wiring should reload persisted MCP auth without exposing the token."""

    monkeypatch.chdir(tmp_path)
    McpAuthService(tmp_path).set_token("serena", "persisted-secret")
    settings = Settings(
        mcp_servers={
            "serena": SchemaMcpServerConfig(command="echo", args=["serena"], trusted=True),
        },
    )

    with patch("henchman.mcp.manager.McpClient") as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.connect = AsyncMock()

        manager = McpManager.create_from_settings(settings)
        await manager.connect_server("serena")

    assert manager.list_servers() == [
        {
            "name": "serena",
            "connected": True,
            "trusted": True,
            "auth_configured": True,
        },
    ]
    args, _ = mock_client_class.call_args
    config = args[1]
    assert config.env["HMN_MCP_AUTH_TOKEN"] == "persisted-secret"
