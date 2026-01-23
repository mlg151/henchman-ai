"""Configuration schema using Pydantic models.

This module defines the settings schema for mlg-cli configuration.
Settings are loaded from YAML/JSON files and environment variables.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ProviderSettings(BaseModel):
    """Settings for model providers.

    Attributes:
        default: The default provider to use.
        deepseek: DeepSeek provider configuration.
        openai: OpenAI provider configuration.
        anthropic: Anthropic provider configuration.
        ollama: Ollama provider configuration.
    """

    default: str = "deepseek"
    deepseek: dict[str, object] = Field(
        default_factory=lambda: dict[str, object]({"model": "deepseek-chat"})
    )
    openai: dict[str, object] = Field(default_factory=dict)
    anthropic: dict[str, object] = Field(default_factory=dict)
    ollama: dict[str, object] = Field(
        default_factory=lambda: dict[str, object]({"base_url": "http://localhost:11434"})
    )


class ToolSettings(BaseModel):
    """Settings for tool behavior.

    Attributes:
        auto_approve_read: Whether to auto-approve read-only tools.
        shell_timeout: Default timeout for shell commands in seconds.
        sandbox: Execution sandbox mode ("none" or "docker").
    """

    auto_approve_read: bool = True
    shell_timeout: int = 60
    sandbox: Literal["none", "docker"] = "none"


class UISettings(BaseModel):
    """Settings for terminal UI.

    Attributes:
        theme: UI color theme name.
        show_line_numbers: Whether to show line numbers in file output.
    """

    theme: str = "dark"
    show_line_numbers: bool = True


class McpServerConfig(BaseModel):
    """Configuration for an MCP server.

    Attributes:
        command: The command to run the MCP server.
        args: Command line arguments.
        env: Environment variables to set.
        trusted: Whether to skip confirmation for this server's tools.
    """

    command: str
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    trusted: bool = False


class Settings(BaseModel):
    """Main settings model for mlg-cli.

    Attributes:
        providers: Provider configuration.
        tools: Tool behavior configuration.
        ui: UI settings.
        mcp_servers: MCP server configurations.
    """

    providers: ProviderSettings = Field(default_factory=ProviderSettings)
    tools: ToolSettings = Field(default_factory=ToolSettings)
    ui: UISettings = Field(default_factory=UISettings)
    mcp_servers: dict[str, McpServerConfig] = Field(default_factory=dict)
