"""Tests for /mcp command."""

from __future__ import annotations

from io import StringIO
from unittest.mock import MagicMock

import pytest
from rich.console import Console

from henchman.cli.commands import CommandContext
from henchman.cli.commands.mcp import McpCommand


class TestMcpCommand:
    """Tests for /mcp command."""

    @pytest.fixture
    def console(self) -> Console:
        """Create a test console."""
        return Console(file=StringIO(), force_terminal=True, width=80)

    @pytest.fixture
    def ctx(self, console: Console) -> CommandContext:
        """Create a command context."""
        return CommandContext(console=console, args=[])

    def test_name(self) -> None:
        """Test command name."""
        cmd = McpCommand()
        assert cmd.name == "mcp"

    def test_description(self) -> None:
        """Test command description."""
        cmd = McpCommand()
        assert "mcp" in cmd.description.lower() or "server" in cmd.description.lower()

    def test_usage(self) -> None:
        """Test command usage."""
        cmd = McpCommand()
        assert "/mcp" in cmd.usage

    @pytest.mark.anyio
    async def test_mcp_no_args_shows_help(self, ctx: CommandContext) -> None:
        """Test /mcp with no args shows help."""
        cmd = McpCommand()
        await cmd.execute(ctx)
        output = ctx.console.file.getvalue()  # type: ignore[union-attr]
        assert "list" in output.lower() or "status" in output.lower()

    @pytest.mark.anyio
    async def test_mcp_list_no_manager(self, ctx: CommandContext) -> None:
        """Test /mcp list without manager."""
        ctx.args = ["list"]
        cmd = McpCommand()
        await cmd.execute(ctx)
        output = ctx.console.file.getvalue()  # type: ignore[union-attr]
        assert "no" in output.lower() or len(output) > 0

    @pytest.mark.anyio
    async def test_mcp_list_with_servers(self, ctx: CommandContext) -> None:
        """Test /mcp list with servers configured."""
        mock_manager = MagicMock()
        mock_manager.get_server_names.return_value = ["filesystem", "github"]
        mock_manager.is_trusted.side_effect = lambda n: n == "github"
        mock_manager.clients = {
            "filesystem": MagicMock(is_connected=True),
            "github": MagicMock(is_connected=False),
        }
        ctx.mcp_manager = mock_manager  # type: ignore[attr-defined]

        ctx.args = ["list"]
        cmd = McpCommand()
        await cmd.execute(ctx)

        output = ctx.console.file.getvalue()  # type: ignore[union-attr]
        assert "filesystem" in output or "github" in output

    @pytest.mark.anyio
    async def test_mcp_status(self, ctx: CommandContext) -> None:
        """Test /mcp status shows connection info."""
        mock_manager = MagicMock()
        mock_manager.get_server_names.return_value = ["test"]
        mock_manager.clients = {"test": MagicMock(is_connected=True)}
        mock_manager.get_all_tools.return_value = [MagicMock(name="tool1")]
        ctx.mcp_manager = mock_manager  # type: ignore[attr-defined]

        ctx.args = ["status"]
        cmd = McpCommand()
        await cmd.execute(ctx)

        output = ctx.console.file.getvalue()  # type: ignore[union-attr]
        assert len(output) > 0

    @pytest.mark.anyio
    async def test_mcp_unknown_subcommand(self, ctx: CommandContext) -> None:
        """Test /mcp with unknown subcommand."""
        ctx.args = ["unknown"]
        cmd = McpCommand()
        await cmd.execute(ctx)
        output = ctx.console.file.getvalue()  # type: ignore[union-attr]
        assert len(output) > 0

    @pytest.mark.anyio
    async def test_mcp_list_empty_servers(self, ctx: CommandContext) -> None:
        """Test /mcp list with manager but no servers configured."""
        mock_manager = MagicMock()
        mock_manager.get_server_names.return_value = []
        ctx.mcp_manager = mock_manager  # type: ignore[attr-defined]

        ctx.args = ["list"]
        cmd = McpCommand()
        await cmd.execute(ctx)

        output = ctx.console.file.getvalue()  # type: ignore[union-attr]
        assert "no" in output.lower()

    @pytest.mark.anyio
    async def test_mcp_status_no_manager(self, ctx: CommandContext) -> None:
        """Test /mcp status without manager."""
        ctx.args = ["status"]
        cmd = McpCommand()
        await cmd.execute(ctx)

        output = ctx.console.file.getvalue()  # type: ignore[union-attr]
        assert "no" in output.lower()

    @pytest.mark.anyio
    async def test_mcp_status_many_tools(self, ctx: CommandContext) -> None:
        """Test /mcp status with more than 10 tools."""
        mock_manager = MagicMock()
        mock_manager.get_server_names.return_value = ["test"]
        mock_manager.clients = {"test": MagicMock(is_connected=True)}
        # Create 15 mock tools
        mock_tools = [MagicMock(name=f"tool_{i}") for i in range(15)]
        for i, t in enumerate(mock_tools):
            t.name = f"tool_{i}"
        mock_manager.get_all_tools.return_value = mock_tools
        ctx.mcp_manager = mock_manager  # type: ignore[attr-defined]

        ctx.args = ["status"]
        cmd = McpCommand()
        await cmd.execute(ctx)

        output = ctx.console.file.getvalue()  # type: ignore[union-attr]
        assert "more" in output

    @pytest.mark.anyio
    async def test_mcp_status_no_tools(self, ctx: CommandContext) -> None:
        """Test /mcp status with no tools available."""
        mock_manager = MagicMock()
        mock_manager.get_server_names.return_value = ["test"]
        mock_manager.clients = {"test": MagicMock(is_connected=True)}
        mock_manager.get_all_tools.return_value = []  # No tools
        ctx.mcp_manager = mock_manager  # type: ignore[attr-defined]

        ctx.args = ["status"]
        cmd = McpCommand()
        await cmd.execute(ctx)

        output = ctx.console.file.getvalue()  # type: ignore[union-attr]
        assert "0" in output  # Should show 0 tools available
