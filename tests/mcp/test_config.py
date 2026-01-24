"""Tests for MCP configuration."""

from __future__ import annotations

from henchman.mcp.config import McpServerConfig


class TestMcpServerConfig:
    """Tests for McpServerConfig dataclass."""

    def test_minimal_config(self) -> None:
        """Test creating a minimal config with just command."""
        config = McpServerConfig(command="npx")
        assert config.command == "npx"
        assert config.args == []
        assert config.env == {}
        assert config.trusted is False

    def test_full_config(self) -> None:
        """Test creating a full config with all fields."""
        config = McpServerConfig(
            command="uvx",
            args=["mcp-github"],
            env={"GITHUB_TOKEN": "abc123"},
            trusted=True,
        )
        assert config.command == "uvx"
        assert config.args == ["mcp-github"]
        assert config.env == {"GITHUB_TOKEN": "abc123"}
        assert config.trusted is True

    def test_to_dict(self) -> None:
        """Test converting config to dict."""
        config = McpServerConfig(
            command="npx",
            args=["@anthropic-ai/mcp-filesystem-server"],
        )
        data = config.to_dict()
        assert data["command"] == "npx"
        assert data["args"] == ["@anthropic-ai/mcp-filesystem-server"]
        assert data["env"] == {}
        assert data["trusted"] is False

    def test_from_dict(self) -> None:
        """Test creating config from dict."""
        data = {
            "command": "uvx",
            "args": ["mcp-github"],
            "env": {"TOKEN": "secret"},
            "trusted": True,
        }
        config = McpServerConfig.from_dict(data)
        assert config.command == "uvx"
        assert config.args == ["mcp-github"]
        assert config.env == {"TOKEN": "secret"}
        assert config.trusted is True

    def test_from_dict_minimal(self) -> None:
        """Test creating config from minimal dict."""
        data = {"command": "python"}
        config = McpServerConfig.from_dict(data)
        assert config.command == "python"
        assert config.args == []
        assert config.env == {}
        assert config.trusted is False
