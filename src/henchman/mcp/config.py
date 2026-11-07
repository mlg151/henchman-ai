"""MCP server configuration.

This module provides configuration dataclasses for MCP servers.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


@dataclass
class McpServerConfig:
    """Configuration for an MCP server.

    Attributes:
        command: The command to run the server.
        args: Command line arguments.
        env: Environment variables to set.
        trusted: If True, tools from this server skip confirmation.
    """

    command: str | None = None
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    trusted: bool = False
    transport: Literal["stdio", "streamable_http"] = "stdio"
    url: str | None = None
    request_timeout_seconds: float = 30.0
    negotiation_timeout_seconds: float = 40.0
    catalog_timeout_seconds: float = 60.0

    def __post_init__(self) -> None:
        """Apply the shared typed settings contract to the compatibility adapter."""
        from henchman.config.schema import McpServerConfig as SettingsMcpServerConfig

        validated = SettingsMcpServerConfig.model_validate(asdict(self))
        for name, value in validated.model_dump().items():
            setattr(self, name, value)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation.
        """
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> McpServerConfig:
        """Create from dictionary.

        Args:
            data: Dictionary with config data.

        Returns:
            McpServerConfig instance.
        """
        from henchman.config.schema import McpServerConfig as SettingsMcpServerConfig

        validated = SettingsMcpServerConfig.model_validate(data)
        return cls(**validated.model_dump())
