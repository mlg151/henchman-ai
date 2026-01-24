"""MCP server configuration.

This module provides configuration dataclasses for MCP servers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class McpServerConfig:
    """Configuration for an MCP server.

    Attributes:
        command: The command to run the server.
        args: Command line arguments.
        env: Environment variables to set.
        trusted: If True, tools from this server skip confirmation.
    """

    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    trusted: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation.
        """
        return {
            "command": self.command,
            "args": self.args,
            "env": self.env,
            "trusted": self.trusted,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> McpServerConfig:
        """Create from dictionary.

        Args:
            data: Dictionary with config data.

        Returns:
            McpServerConfig instance.
        """
        return cls(
            command=data["command"],
            args=data.get("args", []),
            env=data.get("env", {}),
            trusted=data.get("trusted", False),
        )
