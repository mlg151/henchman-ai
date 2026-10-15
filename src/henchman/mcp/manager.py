"""Compatibility MCP manager with lightweight server lifecycle support."""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from henchman.config.schema import McpServerConfig
from henchman.mcp.auth import McpAuthService
from henchman.mcp.client import McpClient, McpClientProtocol
from henchman.mcp.tool import McpTool

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from henchman.config.schema import Settings
    from henchman.mcp.client import McpToolDefinition


ClientFactory = Callable[[str, McpServerConfig, bool], McpClientProtocol]


def _create_mcp_client(
    name: str,
    config: McpServerConfig,
    verbose: bool,
) -> McpClient:
    """Adapt the concrete client's keyword-only flag to ``ClientFactory``."""
    return McpClient(name, config, verbose=verbose)


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
        self._client_factory = client_factory or _create_mcp_client

    @classmethod
    def create_from_settings(
        cls,
        settings: Settings | None,
        mcp_logging_enabled: bool = False,
        *,
        project_root: Path | None = None,
    ) -> McpManager | None:
        """Create a manager from application settings.

        Args:
            settings: Application settings, or None.
            mcp_logging_enabled: Whether to enable verbose MCP logging.
            project_root: Optional project root for auth token resolution.

        Returns:
            A new McpManager instance, or None when *settings* is None
            or has no MCP servers configured.
        """
        if settings is None or settings.mcp_servers is None:
            return None

        if not settings.mcp_servers:
            return None

        # Clone configs and inject logging-suppression environment variables
        configs: dict[str, McpServerConfig] = {}
        for server_name, config in settings.mcp_servers.items():
            env = dict(config.env)
            if not mcp_logging_enabled:
                env = cls._build_logging_env(server_name, config, env)
            configs[server_name] = config.model_copy(update={"env": env})

        manager = cls(configs, verbose=mcp_logging_enabled)
        auth_service = McpAuthService(project_root)
        for server_name in configs:
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

    def get_server_names(self) -> list[str]:
        """Return names of all configured servers.

        Returns:
            List of server name strings.
        """
        return list(self.configs.keys())

    def is_trusted(self, server_name: str) -> bool:
        """Check whether a configured server is trusted.

        Args:
            server_name: Name of the server to check.

        Returns:
            True if the server config has trusted=True.
        """
        config = self.configs.get(server_name)
        return config.trusted if config else False

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

    async def call_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: dict[str, object],
    ) -> object:
        """Call a tool on one connected server.

        Args:
            server_name: Name of the server to call.
            tool_name: Name of the tool to invoke.
            arguments: Tool arguments dictionary.

        Returns:
            Tool result.

        Raises:
            KeyError: If *server_name* is not connected.
        """
        client = self.clients.get(server_name)
        if client is None:
            msg = f"Unknown MCP server: {server_name}"
            raise KeyError(msg)
        return await client.call_tool(tool_name, arguments)

    @staticmethod
    def _build_logging_env(
        server_name: str,
        config: McpServerConfig,
        env: dict[str, str],
    ) -> dict[str, str]:
        """Build MCP server logging environment variables.

        Args:
            server_name: Name of the server.
            config: Server configuration.
            env: Existing environment variables.

        Returns:
            Enriched environment variables for logging/disabling color.
        """
        result = dict(env)
        result["NO_COLOR"] = "1"
        result["TERM"] = "dumb"

        command = config.command
        is_python = "python" in command or command in ("uvx", "uv")
        is_node = "node" in command or command in ("npx",)

        if is_python:
            result.setdefault("PYTHONWARNINGS", "ignore")
            result.setdefault("LOGLEVEL", "WARNING")
            result.setdefault("PYTHON_LOG_LEVEL", "WARNING")
            if "serena" in server_name.lower() or "serena" in " ".join(
                getattr(config, "args", []) or [],
            ):
                result.setdefault("SERENA_LOG_LEVEL", "WARNING")
        elif is_node:
            result.setdefault("NODE_ENV", "production")

        return result

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
