"""Compatibility MCP manager with lightweight server lifecycle support."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Callable

logger = logging.getLogger(__name__)

from henchman.config.schema import McpServerConfig
from henchman.mcp.auth import McpAuthService
from henchman.mcp.client import McpClient, McpClientProtocol
from henchman.mcp.tool import McpTool

if TYPE_CHECKING:
    from henchman.config.schema import Settings
    from henchman.mcp.client import McpToolDefinition


ClientFactory = Callable[[str, McpServerConfig, bool], McpClientProtocol]


class McpManager:
    """Manage configured MCP clients and expose their wrapped tools."""

    def __init__(
        self,
        configs: dict[str, McpServerConfig] | None = None,
        *,
        verbose: bool = False,
        client_factory: ClientFactory | None = None,
    ) -> None:
        """Initialize the manager with server configurations."""

        self.configs = dict(configs or {})
        self.clients: dict[str, McpClientProtocol] = {}
        self._verbose = verbose
        self._auth_tokens: dict[str, str] = {}
        self._client_factory = client_factory or McpClient  # type: ignore[assignment]

    @classmethod
    def create_from_settings(
        cls,
        settings: Settings,
        mcp_logging_enabled: bool = False,
        *,
        project_root: Path | None = None,
    ) -> McpManager:
        """Create a manager from application settings."""

        manager = cls(settings.mcp_servers, verbose=mcp_logging_enabled)
        auth_service = McpAuthService(project_root)
        for server_name in settings.mcp_servers:
            token = auth_service.get_token(server_name)
            if token:
                manager.set_auth_token(server_name, token)
        return manager

    async def connect_all(self) -> None:
        """Attempt to connect every configured MCP server."""

        for server_name in self.configs:
            try:
                await self.connect_server(server_name)
            except Exception:
                logger.warning("Failed to connect to MCP server %r", server_name, exc_info=True)
                continue

    async def connect_server(self, server_name: str) -> None:
        """Connect one configured MCP server."""

        config = self.configs[server_name]
        client_config = config
        auth_token = self._auth_tokens.get(server_name)
        if auth_token:
            client_config = config.model_copy(
                update={"env": {**config.env, "HMN_MCP_AUTH_TOKEN": auth_token}},
            )

        client = self._client_factory(server_name, client_config, self._verbose)
        await client.connect()
        self.clients[server_name] = client

    async def disconnect_all(self) -> None:
        """Disconnect all active MCP clients."""

        for server_name in list(self.clients):
            await self.disconnect_server(server_name)

    async def disconnect_server(self, server_name: str) -> None:
        """Disconnect one active MCP client."""

        client = self.clients.pop(server_name, None)
        if client is None:
            return
        await client.disconnect()

    def get_all_tools(self) -> list[McpTool]:
        """Return wrapped tools from all connected clients."""

        wrapped: list[McpTool] = []
        for server_name, client in self.clients.items():
            config = self.configs.get(server_name, McpServerConfig(command="true"))
            for tool_definition in client.get_tools():
                wrapped.append(
                    McpTool(
                        mcp_tool=tool_definition,
                        client=client,
                        server_name=server_name,
                        trusted=config.trusted,
                    ),
                )
        return wrapped

    def list_servers(self) -> list[dict[str, object]]:
        """Return status metadata for all configured servers."""

        return [
            {
                "name": server_name,
                "connected": server_name in self.clients,
                "trusted": config.trusted,
                "auth_configured": server_name in self._auth_tokens,
            }
            for server_name, config in self.configs.items()
        ]

    def discover_tools(self, server_name: str | None = None) -> list[McpToolDefinition]:
        """Return discovered tool definitions for one or all servers."""

        if server_name is not None:
            client = self.clients.get(server_name)
            if client is None:
                return []
            return list(client.get_tools())

        discovered: list[McpToolDefinition] = []
        for client in self.clients.values():
            discovered.extend(client.get_tools())
        return discovered

    def set_auth_token(self, server_name: str, token: str) -> None:
        """Store an in-memory auth token for one server."""

        self._auth_tokens[server_name] = token

    def clear_auth_token(self, server_name: str) -> None:
        """Remove an in-memory auth token for one server."""

        self._auth_tokens.pop(server_name, None)
