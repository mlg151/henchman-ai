"""MCP manager for multiple servers.

This module provides the McpManager class for managing
connections to multiple MCP servers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from henchman.mcp.client import McpClient, McpToolResult

if TYPE_CHECKING:
    from typing import Self

    from henchman.config.schema import Settings
    from henchman.mcp.config import McpServerConfig
    from henchman.mcp.tool import McpTool

# Log-suppression environment variable sets applied per server type.
_PYTHON_LOG_SUPPRESSION: dict[str, str] = {
    "PYTHONWARNINGS": "ignore",
    "LOGLEVEL": "WARNING",
    "PYTHON_LOG_LEVEL": "WARNING",
}
_SERENA_LOG_SUPPRESSION: dict[str, str] = {
    "SERENA_LOG_LEVEL": "WARNING",
    **_PYTHON_LOG_SUPPRESSION,
}
_TERMINAL_SUPPRESSION: dict[str, str] = {
    "NO_COLOR": "1",
    "TERM": "dumb",
}


def _detect_server_type(name: str, command: str, args: list[str]) -> str:
    """Detect the runtime type of a server from its name, command, and args.

    Returns one of: 'serena', 'python', 'node', or 'unknown'.
    """
    if "serena" in name.lower() or any("serena" in arg.lower() for arg in args):
        return "serena"
    if (
        "python" in command.lower()
        or "uvx" in command.lower()
        or any(".py" in arg.lower() for arg in args)
    ):
        return "python"
    if "node" in command.lower() or "npx" in command.lower() or "npm" in command.lower():
        return "node"
    return "unknown"


def _build_logging_env(
    name: str,
    server_config: object,
    base_env: dict[str, str],
) -> dict[str, str]:
    """Build an environment dict with logging suppression applied for *server_config*.

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
    server_type = _detect_server_type(name, command, args)

    if server_type == "serena":
        env.update(_SERENA_LOG_SUPPRESSION)
    elif server_type == "python":
        env.update(_PYTHON_LOG_SUPPRESSION)
    elif server_type == "node":
        env["NODE_ENV"] = "production"

    env.update(_TERMINAL_SUPPRESSION)
    return env


def _build_mcp_server_config(
    name: str,
    server_config: Any,
    mcp_logging_enabled: bool,
) -> McpServerConfig:
    """Build a McpServerConfig from raw settings, optionally suppressing logs.

    Args:
        name: Server name.
        server_config: Raw settings object with command, args, env, trusted attrs.
        mcp_logging_enabled: When False, logging suppression env vars are injected.

    Returns:
        Configured McpServerConfig instance.
    """
    from henchman.mcp.config import McpServerConfig

    env = dict(server_config.env)
    if not mcp_logging_enabled:
        env = _build_logging_env(name, server_config, env)

    return McpServerConfig(
        command=server_config.command,
        args=server_config.args,
        env=env,
        trusted=server_config.trusted,
    )


class McpManager:
    """Manages multiple MCP server connections.

    Handles connecting to, disconnecting from, and discovering
    tools across multiple MCP servers.
    """

    def __init__(
        self: Self,
        configs: dict[str, McpServerConfig],
        *,
        verbose: bool = False,
    ) -> None:
        """Initialize the manager.

        Args:
            configs: Map of server name to configuration.
            verbose: If True, show MCP server logs. If False, suppress INFO/DEBUG logs.
        """
        self.configs = configs
        self.verbose = verbose
        self.clients: dict[str, McpClient] = {}
        self._tools: list[McpTool] = []

    def get_server_names(self: Self) -> list[str]:
        """Get names of configured servers.

        Returns:
            List of server names.
        """
        return list(self.configs.keys())

    def is_trusted(self: Self, server_name: str) -> bool:
        """Check if a server is trusted.

        Args:
            server_name: Name of the server.

        Returns:
            True if server is trusted.
        """
        if server_name not in self.configs:
            return False
        return self.configs[server_name].trusted

    async def connect_all(self: Self) -> None:
        """Connect to all configured servers."""
        from henchman.mcp.tool import McpTool

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
            except Exception:  # pragma: no cover
                # Log error but continue with other servers
                pass

    async def disconnect_all(self: Self) -> None:
        """Disconnect from all servers."""
        for client in self.clients.values():
            await client.disconnect()
        self.clients.clear()
        self._tools.clear()

    def get_all_tools(self: Self) -> list[McpTool]:
        """Get all tools from all connected servers.

        Returns:
            List of McpTool wrappers.
        """
        return self._tools

    async def call_tool(
        self: Self,
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

        Delegates to the module-level :func:`_build_logging_env`.

        Args:
            name: Server name, used to detect Serena.
            server_config: Server configuration with command and args attributes.
            base_env: Starting environment variables from config.

        Returns:
            Updated environment dict with logging suppression applied.
        """
        return _build_logging_env(name, server_config, base_env)

    @staticmethod
    def create_from_settings(
        settings: Settings | None,
        *,
        mcp_logging_enabled: bool = False,
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

        mcp_configs: dict[str, McpServerConfig] = {
            name: _build_mcp_server_config(name, server_config, mcp_logging_enabled)
            for name, server_config in settings.mcp_servers.items()
        }

        return McpManager(mcp_configs, verbose=mcp_logging_enabled)
