"""MCP manager for multiple servers.

This module provides the McpManager class for managing
connections to multiple MCP servers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from henchman.mcp.client import McpClient, McpToolResult
from henchman.mcp.config import McpServerConfig

if TYPE_CHECKING:
    from henchman.mcp.tool import McpTool


class McpManager:
    """Manages multiple MCP server connections.

    Handles connecting to, disconnecting from, and discovering
    tools across multiple MCP servers.
    """

    def __init__(self, configs: dict[str, McpServerConfig]) -> None:
        """Initialize the manager.

        Args:
            configs: Map of server name to configuration.
        """
        self.configs = configs
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
        from henchman.mcp.tool import McpTool

        for name, config in self.configs.items():
            client = McpClient(name=name, config=config)
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
                        )
                    )
            except Exception:  # pragma: no cover
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
            raise KeyError(f"Unknown MCP server: {server_name}")

        return await self.clients[server_name].call_tool(tool_name, arguments)
