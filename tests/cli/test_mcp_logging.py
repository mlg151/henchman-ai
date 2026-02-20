"""Tests for MCP logging control feature."""

from __future__ import annotations

from io import StringIO
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console

from henchman.cli.commands import CommandContext
from henchman.cli.commands.mcp import McpCommand
from henchman.config.schema import Settings


class TestMcpLogging:
    """Tests for MCP logging control."""

    @pytest.fixture
    def console(self) -> Console:
        """Create a test console."""
        return Console(file=StringIO(), force_terminal=True, width=80)

    @pytest.fixture
    def ctx(self, console: Console) -> CommandContext:
        """Create a command context."""
        return CommandContext(console=console, args=[])

    def test_mcp_logging_command_exists(self) -> None:
        """Test that /mcp logging command is recognized."""
        # Just verify we can instantiate the command
        McpCommand()
        # The execute method should handle "logging" subcommand
        # We'll test this in the async test below

    @pytest.mark.anyio
    async def test_mcp_logging_on_enables_logging(self, ctx: CommandContext) -> None:
        """Test /mcp logging on enables logging."""
        # Create a mock manager
        mock_manager = MagicMock()
        ctx.mcp_manager = mock_manager  # type: ignore[attr-defined]

        # Create a real Settings instance with mcp_logging=False (default)
        settings = Settings()
        # The default should be False
        assert settings.ui.mcp_logging is False

        ctx.args = ["logging", "on"]
        cmd = McpCommand()

        # Mock the load_settings function to return our settings
        with patch("henchman.cli.commands.mcp.load_settings", return_value=settings):
            await cmd.execute(ctx)

        output = ctx.console.file.getvalue()  # type: ignore[union-attr]
        assert "logging enabled" in output.lower() or "on" in output.lower()
        # The setting should now be True
        assert settings.ui.mcp_logging is True

    @pytest.mark.anyio
    async def test_mcp_logging_off_disables_logging(self, ctx: CommandContext) -> None:
        """Test /mcp logging off disables logging."""
        mock_manager = MagicMock()
        ctx.mcp_manager = mock_manager  # type: ignore[attr-defined]

        # Create a real Settings instance with mcp_logging=True
        settings = Settings()
        settings.ui.mcp_logging = True

        ctx.args = ["logging", "off"]
        cmd = McpCommand()

        with patch("henchman.cli.commands.mcp.load_settings", return_value=settings):
            await cmd.execute(ctx)

        output = ctx.console.file.getvalue()  # type: ignore[union-attr]
        assert "logging disabled" in output.lower() or "off" in output.lower()
        # The setting should now be False
        assert settings.ui.mcp_logging is False

    @pytest.mark.anyio
    async def test_mcp_logging_status_shows_current_setting(self, ctx: CommandContext) -> None:
        """Test /mcp logging status shows current setting."""
        mock_manager = MagicMock()
        ctx.mcp_manager = mock_manager  # type: ignore[attr-defined]

        # Create a real Settings instance with mcp_logging=True
        settings = Settings()
        settings.ui.mcp_logging = True

        ctx.args = ["logging", "status"]
        cmd = McpCommand()

        with patch("henchman.cli.commands.mcp.load_settings", return_value=settings):
            await cmd.execute(ctx)

        output = ctx.console.file.getvalue()  # type: ignore[union-attr]
        assert "enabled" in output.lower() or "on" in output.lower()

    @pytest.mark.anyio
    async def test_mcp_logging_invalid_argument(self, ctx: CommandContext) -> None:
        """Test /mcp logging with invalid argument shows error."""
        mock_manager = MagicMock()
        ctx.mcp_manager = mock_manager  # type: ignore[attr-defined]

        ctx.args = ["logging", "invalid"]
        cmd = McpCommand()

        await cmd.execute(ctx)

        output = ctx.console.file.getvalue()  # type: ignore[union-attr]
        assert "error" in output.lower() or "invalid" in output.lower()

    @pytest.mark.anyio
    async def test_mcp_logging_no_argument_shows_help(self, ctx: CommandContext) -> None:
        """Test /mcp logging with no argument shows help."""
        mock_manager = MagicMock()
        ctx.mcp_manager = mock_manager  # type: ignore[attr-defined]

        ctx.args = ["logging"]
        cmd = McpCommand()

        await cmd.execute(ctx)

        output = ctx.console.file.getvalue()  # type: ignore[union-attr]
        # Should show MCP logging control help
        assert "logging" in output.lower() and "control" in output.lower()
