"""Tests for unlimited command."""

from unittest.mock import Mock

import pytest

from henchman.cli.commands import CommandContext
from henchman.cli.commands.unlimited import UnlimitedCommand


class TestUnlimitedCommand:
    """Tests for UnlimitedCommand class."""

    def test_command_properties(self) -> None:
        """Test command name, description, and usage."""
        cmd = UnlimitedCommand()

        assert cmd.name == "unlimited"
        assert cmd.description == "Toggle unlimited mode (bypass loop protection)"
        assert cmd.usage == "/unlimited [on|off]"

    @pytest.mark.asyncio
    async def test_execute_no_agent(self) -> None:
        """Test execute when no agent is available."""
        cmd = UnlimitedCommand()

        # Create mock context with no agent
        mock_console = Mock()
        mock_console.print = Mock()

        ctx = CommandContext(args=[], console=mock_console, agent=None, tool_registry=Mock())

        await cmd.execute(ctx)

        # Should print error message
        mock_console.print.assert_called_once_with("[red]Error: No agent available[/red]")

    @pytest.mark.asyncio
    async def test_execute_toggle_on_to_off(self) -> None:
        """Test toggle from on to off."""
        cmd = UnlimitedCommand()

        # Create mock agent with unlimited_mode=True
        mock_agent = Mock()
        mock_agent.unlimited_mode = True

        mock_console = Mock()
        mock_console.print = Mock()

        ctx = CommandContext(args=[], console=mock_console, agent=mock_agent, tool_registry=Mock())

        await cmd.execute(ctx)

        # Should toggle to False
        assert mock_agent.unlimited_mode is False
        # Should print success message
        assert mock_console.print.call_count == 1
        call_args = mock_console.print.call_args[0][0]
        assert "Unlimited mode: OFF" in call_args

    @pytest.mark.asyncio
    async def test_execute_toggle_off_to_on(self) -> None:
        """Test toggle from off to on."""
        cmd = UnlimitedCommand()

        # Create mock agent with unlimited_mode=False
        mock_agent = Mock()
        mock_agent.unlimited_mode = False

        mock_console = Mock()
        mock_console.print = Mock()

        ctx = CommandContext(args=[], console=mock_console, agent=mock_agent, tool_registry=Mock())

        await cmd.execute(ctx)

        # Should toggle to True
        assert mock_agent.unlimited_mode is True
        # Should print warning message
        assert mock_console.print.call_count == 1
        call_args = mock_console.print.call_args[0][0]
        assert "Unlimited mode: ON" in call_args

    @pytest.mark.asyncio
    async def test_execute_set_on_explicitly(self) -> None:
        """Test setting unlimited mode on explicitly."""
        cmd = UnlimitedCommand()

        # Create mock agent
        mock_agent = Mock()
        mock_agent.unlimited_mode = False

        mock_console = Mock()
        mock_console.print = Mock()

        ctx = CommandContext(
            args=["on"], console=mock_console, agent=mock_agent, tool_registry=Mock()
        )

        await cmd.execute(ctx)

        # Should set to True
        assert mock_agent.unlimited_mode is True
        # Should print warning message
        call_args = mock_console.print.call_args[0][0]
        assert "Unlimited mode: ON" in call_args

    @pytest.mark.asyncio
    async def test_execute_set_off_explicitly(self) -> None:
        """Test setting unlimited mode off explicitly."""
        cmd = UnlimitedCommand()

        # Create mock agent
        mock_agent = Mock()
        mock_agent.unlimited_mode = True

        mock_console = Mock()
        mock_console.print = Mock()

        ctx = CommandContext(
            args=["off"], console=mock_console, agent=mock_agent, tool_registry=Mock()
        )

        await cmd.execute(ctx)

        # Should set to False
        assert mock_agent.unlimited_mode is False
        # Should print success message
        call_args = mock_console.print.call_args[0][0]
        assert "Unlimited mode: OFF" in call_args

    @pytest.mark.asyncio
    async def test_execute_set_true_explicitly(self) -> None:
        """Test setting unlimited mode with 'true'."""
        cmd = UnlimitedCommand()

        mock_agent = Mock()
        mock_agent.unlimited_mode = False

        mock_console = Mock()
        mock_console.print = Mock()

        ctx = CommandContext(
            args=["true"], console=mock_console, agent=mock_agent, tool_registry=Mock()
        )

        await cmd.execute(ctx)

        assert mock_agent.unlimited_mode is True

    @pytest.mark.asyncio
    async def test_execute_set_false_explicitly(self) -> None:
        """Test setting unlimited mode with 'false'."""
        cmd = UnlimitedCommand()

        mock_agent = Mock()
        mock_agent.unlimited_mode = True

        mock_console = Mock()
        mock_console.print = Mock()

        ctx = CommandContext(
            args=["false"], console=mock_console, agent=mock_agent, tool_registry=Mock()
        )

        await cmd.execute(ctx)

        assert mock_agent.unlimited_mode is False

    @pytest.mark.asyncio
    async def test_execute_set_1_explicitly(self) -> None:
        """Test setting unlimited mode with '1'."""
        cmd = UnlimitedCommand()

        mock_agent = Mock()
        mock_agent.unlimited_mode = False

        mock_console = Mock()
        mock_console.print = Mock()

        ctx = CommandContext(
            args=["1"], console=mock_console, agent=mock_agent, tool_registry=Mock()
        )

        await cmd.execute(ctx)

        assert mock_agent.unlimited_mode is True

    @pytest.mark.asyncio
    async def test_execute_set_0_explicitly(self) -> None:
        """Test setting unlimited mode with '0'."""
        cmd = UnlimitedCommand()

        mock_agent = Mock()
        mock_agent.unlimited_mode = True

        mock_console = Mock()
        mock_console.print = Mock()

        ctx = CommandContext(
            args=["0"], console=mock_console, agent=mock_agent, tool_registry=Mock()
        )

        await cmd.execute(ctx)

        assert mock_agent.unlimited_mode is False

    @pytest.mark.asyncio
    async def test_execute_set_yes_explicitly(self) -> None:
        """Test setting unlimited mode with 'yes'."""
        cmd = UnlimitedCommand()

        mock_agent = Mock()
        mock_agent.unlimited_mode = False

        mock_console = Mock()
        mock_console.print = Mock()

        ctx = CommandContext(
            args=["yes"], console=mock_console, agent=mock_agent, tool_registry=Mock()
        )

        await cmd.execute(ctx)

        assert mock_agent.unlimited_mode is True

    @pytest.mark.asyncio
    async def test_execute_set_no_explicitly(self) -> None:
        """Test setting unlimited mode with 'no'."""
        cmd = UnlimitedCommand()

        mock_agent = Mock()
        mock_agent.unlimited_mode = True

        mock_console = Mock()
        mock_console.print = Mock()

        ctx = CommandContext(
            args=["no"], console=mock_console, agent=mock_agent, tool_registry=Mock()
        )

        await cmd.execute(ctx)

        assert mock_agent.unlimited_mode is False

    @pytest.mark.asyncio
    async def test_execute_invalid_argument(self) -> None:
        """Test with invalid argument."""
        cmd = UnlimitedCommand()

        mock_agent = Mock()
        mock_agent.unlimited_mode = False

        mock_console = Mock()
        mock_console.print = Mock()

        ctx = CommandContext(
            args=["invalid"], console=mock_console, agent=mock_agent, tool_registry=Mock()
        )

        await cmd.execute(ctx)

        # Should not change mode
        assert mock_agent.unlimited_mode is False
        # Should print usage
        mock_console.print.assert_called_once()
        call_args = mock_console.print.call_args[0][0]
        assert "Usage:" in call_args
        assert "/unlimited [on|off]" in call_args

    @pytest.mark.asyncio
    async def test_execute_case_insensitive(self) -> None:
        """Test that arguments are case-insensitive."""
        cmd = UnlimitedCommand()

        mock_agent = Mock()
        mock_agent.unlimited_mode = False

        mock_console = Mock()
        mock_console.print = Mock()

        # Test uppercase
        ctx = CommandContext(
            args=["ON"], console=mock_console, agent=mock_agent, tool_registry=Mock()
        )

        await cmd.execute(ctx)
        assert mock_agent.unlimited_mode is True

        # Reset and test mixed case
        mock_agent.unlimited_mode = False
        ctx = CommandContext(
            args=["TrUe"], console=mock_console, agent=mock_agent, tool_registry=Mock()
        )

        await cmd.execute(ctx)
        assert mock_agent.unlimited_mode is True
