"""MCP (Model Context Protocol) integration."""

from mlg.mcp.client import McpClient, McpToolDefinition, McpToolResult
from mlg.mcp.config import McpServerConfig
from mlg.mcp.manager import McpManager
from mlg.mcp.tool import McpTool

__all__ = [
    "McpClient",
    "McpManager",
    "McpServerConfig",
    "McpTool",
    "McpToolDefinition",
    "McpToolResult",
]
