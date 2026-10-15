"""Tests for BUG-017: McpServerConfig.command lacks non-empty validation.

Empty string "" or whitespace passes validation but cannot be executed,
causing confusing subprocess errors at connection time.
"""

from __future__ import annotations

import pytest

from henchman.config.schema import McpServerConfig


class TestBug017McpCommandNonEmpty:
    """McpServerConfig.command should reject empty/whitespace-only strings."""

    def test_empty_command_raises(self) -> None:
        """Empty string command should be rejected."""
        with pytest.raises(ValueError):
            McpServerConfig(command="")

    def test_whitespace_command_raises(self) -> None:
        """Whitespace-only command should be rejected."""
        with pytest.raises(ValueError):
            McpServerConfig(command="   ")

    def test_valid_command_passes(self) -> None:
        """Valid command string should pass."""
        config = McpServerConfig(command="npx")
        assert config.command == "npx"

    def test_valid_command_with_args(self) -> None:
        """Valid command with args should pass."""
        config = McpServerConfig(command="uvx", args=["mcp-github"])
        assert config.command == "uvx"
