"""Tests for configuration schema."""

from __future__ import annotations

import pytest

from henchman.config.schema import (
    McpServerConfig,
    ProviderSettings,
    Settings,
    ToolSettings,
    UISettings,
)


class TestProviderSettings:
    """Tests for ProviderSettings model."""

    def test_default_values(self) -> None:
        """Test default provider settings."""
        settings = ProviderSettings()
        assert settings.default == "deepseek"
        assert settings.deepseek == {"model": "deepseek-chat"}
        assert settings.openai == {}
        assert settings.anthropic == {}
        assert settings.ollama == {"base_url": "http://localhost:11434"}

    def test_custom_values(self) -> None:
        """Test custom provider settings."""
        settings = ProviderSettings(
            default="openai",
            deepseek={"model": "deepseek-reasoner"},
            openai={"model": "gpt-4o"},
        )
        assert settings.default == "openai"
        assert settings.deepseek == {"model": "deepseek-reasoner"}
        assert settings.openai == {"model": "gpt-4o"}

    def test_model_dump(self) -> None:
        """Test serialization to dict."""
        settings = ProviderSettings()
        data = settings.model_dump()
        assert data["default"] == "deepseek"
        assert "deepseek" in data
        assert "ollama" in data


class TestToolSettings:
    """Tests for ToolSettings model."""

    def test_default_values(self) -> None:
        """Test default tool settings."""
        settings = ToolSettings()
        assert settings.auto_approve_read is True
        assert settings.shell_timeout == 60
        assert settings.sandbox == "none"

    def test_custom_values(self) -> None:
        """Test custom tool settings."""
        settings = ToolSettings(
            auto_approve_read=False,
            shell_timeout=120,
            sandbox="docker",
        )
        assert settings.auto_approve_read is False
        assert settings.shell_timeout == 120
        assert settings.sandbox == "docker"

    def test_sandbox_literal_validation(self) -> None:
        """Test sandbox only accepts valid values."""
        with pytest.raises(ValueError):
            ToolSettings(sandbox="invalid")  # type: ignore[arg-type]


class TestUISettings:
    """Tests for UISettings model."""

    def test_default_values(self) -> None:
        """Test default UI settings."""
        settings = UISettings()
        assert settings.theme == "dark"
        assert settings.show_line_numbers is True

    def test_custom_values(self) -> None:
        """Test custom UI settings."""
        settings = UISettings(theme="light", show_line_numbers=False)
        assert settings.theme == "light"
        assert settings.show_line_numbers is False


class TestMcpServerConfig:
    """Tests for McpServerConfig model."""

    def test_minimal_config(self) -> None:
        """Test minimal MCP server config."""
        config = McpServerConfig(command="npx")
        assert config.command == "npx"
        assert config.args == []
        assert config.env == {}
        assert config.trusted is False

    def test_full_config(self) -> None:
        """Test full MCP server config."""
        config = McpServerConfig(
            command="uvx",
            args=["mcp-github"],
            env={"GITHUB_TOKEN": "secret"},
            trusted=True,
        )
        assert config.command == "uvx"
        assert config.args == ["mcp-github"]
        assert config.env == {"GITHUB_TOKEN": "secret"}
        assert config.trusted is True


class TestSettings:
    """Tests for main Settings model."""

    def test_default_values(self) -> None:
        """Test default settings."""
        settings = Settings()
        assert isinstance(settings.providers, ProviderSettings)
        assert isinstance(settings.tools, ToolSettings)
        assert isinstance(settings.ui, UISettings)
        assert settings.mcp_servers == {}

    def test_nested_settings(self) -> None:
        """Test nested settings customization."""
        settings = Settings(
            providers=ProviderSettings(default="openai"),
            tools=ToolSettings(shell_timeout=300),
        )
        assert settings.providers.default == "openai"
        assert settings.tools.shell_timeout == 300

    def test_mcp_servers(self) -> None:
        """Test MCP servers configuration."""
        settings = Settings(
            mcp_servers={
                "github": McpServerConfig(command="uvx", args=["mcp-github"])
            }
        )
        assert "github" in settings.mcp_servers
        assert settings.mcp_servers["github"].command == "uvx"

    def test_from_dict(self) -> None:
        """Test creating settings from dictionary."""
        data = {
            "providers": {"default": "anthropic"},
            "tools": {"shell_timeout": 90},
            "ui": {"theme": "light"},
        }
        settings = Settings(**data)
        assert settings.providers.default == "anthropic"
        assert settings.tools.shell_timeout == 90
        assert settings.ui.theme == "light"

    def test_model_dump(self) -> None:
        """Test serialization to dict."""
        settings = Settings()
        data = settings.model_dump()
        assert "providers" in data
        assert "tools" in data
        assert "ui" in data
        assert "mcp_servers" in data
