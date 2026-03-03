"""MCP manager for multiple servers.

This module provides the McpManager class for managing
connections to multiple MCP servers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from henchman.mcp.client import McpClient, McpToolResult

if TYPE_CHECKING:
    from henchman.config.schema import Settings
    from henchman.mcp.config import McpServerConfig
    from henchman.mcp.tool import McpTool


class McpManager:
    """Manages multiple MCP server connections.

    Handles connecting to, disconnecting from, and discovering
    tools across multiple MCP servers.
    """

    def __init__(self, configs: dict[str, McpServerConfig], *, verbose: bool = False) -> None:
        """Initialize the manager.

        Args:
            configs: Map of server name to configuration.
            verbose: If True, show MCP server logs. If False, suppress INFO/DEBUG logs.
        """
        self.configs = configs
        self.verbose = verbose
        self.clients: dict[str, McpClient] = {}
        self._tools: list[McpTool] = []

    def get_server_names(self) -> list[str]:
        """Get names of configured servers.

        Returns:
            List of server names.
        """
        return list(self.configs.keys())

    def is_trusted(self, server_name: str) -> bool:
        """Check if a server is trusted.

        Args:
            server_name: Name of the server.

        Returns:
            True if server is trusted.
        """
        if server_name not in self.configs:
            return False
        return self.configs[server_name].trusted

    async def connect_all(self) -> None:
        """Connect to all configured servers."""
        from henchman.mcp.tool import McpTool  # noqa: PLC0415

        for name, config in self.configs.items():
            client = McpClient(name=name, config=config, verbose=self.verbose)
            try:
                await client.connect()
                self.clients[name] = client

                # Create tool wrappers
                for tool_def in client.get_tools():
                    self._tools.append(
                        McpTool(
                            mcp_tool=tool_def,
                            client=client,
                            server_name=name,
                            trusted=config.trusted,
                        ),
                    )
            except Exception:  # pragma: no cover  # noqa: BLE001
                # Log error but continue with other servers
                pass

    async def disconnect_all(self) -> None:
        """Disconnect from all servers."""
        for client in self.clients.values():
            await client.disconnect()
        self.clients.clear()
        self._tools.clear()

    def get_all_tools(self) -> list[McpTool]:
        """Get all tools from all connected servers.

        Returns:
            List of McpTool wrappers.
        """
        return self._tools

    async def call_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> McpToolResult:
        """Call a tool on a specific server.

        Args:
            server_name: Name of the server.
            tool_name: Name of the tool.
            arguments: Tool arguments.

        Returns:
            Tool execution result.

        Raises:
            KeyError: If server not found.
        """
        if server_name not in self.clients:
            msg = f"Unknown MCP server: {server_name}"
            raise KeyError(msg)

        return await self.clients[server_name].call_tool(tool_name, arguments)

    @staticmethod
    def _build_logging_env(
        name: str,
        server_config: object,
        base_env: dict[str, str],
    ) -> dict[str, str]:
        """Build environment dict with logging suppression for a server.

        Args:
            name: Server name, used to detect Serena.
            server_config: Server configuration with command and args attributes.
            base_env: Starting environment variables from config.

        Returns:
            Updated environment dict with logging suppression applied.
        """
        env = dict(base_env)
        command: str = getattr(server_config, "command", "")
        args: list[str] = getattr(server_config, "args", [])

        is_python = (
            "python" in command.lower()
            or "uvx" in command.lower()
            or any(".py" in arg.lower() for arg in args)
        )
        is_node = (
            "node" in command.lower()
            or "npx" in command.lower()
            or "npm" in command.lower()
        )
        is_serena = "serena" in name.lower() or any("serena" in arg.lower() for arg in args)

        if is_serena:
            env.update({
                "SERENA_LOG_LEVEL": "WARNING",
                "PYTHONWARNINGS": "ignore",
                "LOGLEVEL": "WARNING",
                "PYTHON_LOG_LEVEL": "WARNING",
            })
        elif is_python:
            env.update({
                "PYTHONWARNINGS": "ignore",
                "LOGLEVEL": "WARNING",
                "PYTHON_LOG_LEVEL": "WARNING",
            })
        elif is_node:
            env["NODE_ENV"] = "production"

        env["NO_COLOR"] = "1"
        env["TERM"] = "dumb"
        return env

    @staticmethod
    def create_from_settings(
        settings: Settings | None, *, mcp_logging_enabled: bool = False,
    ) -> McpManager | None:
        """Create McpManager from application settings.

        Args:
            settings: Application settings with mcp_servers.
            mcp_logging_enabled: Whether MCP logging is enabled.

        Returns:
            McpManager instance or None if no servers configured.
        """
        if not settings or not hasattr(settings, "mcp_servers") or not settings.mcp_servers:
            return None

        from henchman.mcp.config import McpServerConfig  # noqa: PLC0415

        mcp_configs: dict[str, McpServerConfig] = {}
        for name, server_config in settings.mcp_servers.items():
            env = dict(server_config.env)

            if not mcp_logging_enabled:
                env = McpManager._build_logging_env(name, server_config, env)

            mcp_configs[name] = McpServerConfig(
                command=server_config.command,
                args=server_config.args,
                env=env,
                trusted=server_config.trusted,
            )

        return McpManager(mcp_configs, verbose=mcp_logging_enabled)
