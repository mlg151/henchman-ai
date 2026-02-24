"""Tests for interactive shell tool functionality (sudo support)."""

from unittest.mock import AsyncMock, patch

from henchman.tools.builtins.shell import ShellTool


class TestShellToolInteractive:
    """Tests for interactive shell tool features (sudo support)."""

    def test_interactive_parameter_in_schema(self) -> None:
        """Interactive parameter is included in the schema."""
        tool = ShellTool()
        params = tool.parameters
        assert "interactive" in params["properties"]
        assert params["properties"]["interactive"]["type"] == "boolean"
        assert params["properties"]["interactive"]["default"] is False
        assert "sudo" in params["properties"]["interactive"]["description"].lower()

    def test_sudo_command_detection(self) -> None:
        """Tool detects sudo commands."""
        tool = ShellTool()

        # Test sudo command detection
        assert tool._is_sudo_command("sudo apt update") is True
        assert tool._is_sudo_command("  sudo apt update  ") is True
        assert tool._is_sudo_command("echo hello") is False
        assert tool._is_sudo_command("") is False
        assert tool._is_sudo_command("sudo") is False  # "sudo" alone (no space) is not a valid sudo command
        assert tool._is_sudo_command("notsudo command") is False

    async def test_non_interactive_mode_for_non_sudo(self) -> None:
        """Non-interactive mode is used for non-sudo commands."""
        tool = ShellTool()

        # Create a simple mock process
        async def mock_communicate():
            return (b"test output\n", b"")

        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = mock_communicate

        # Mock subprocess creation
        with patch('asyncio.create_subprocess_shell', return_value=mock_process) as mock_create:
            # Execute non-sudo command
            result = await tool.execute(command="echo test")

            # Should use normal subprocess
            mock_create.assert_called_once()
            assert result.success is True
            assert "test output" in result.content

    async def test_sudo_without_tty_falls_back(self) -> None:
        """Sudo command without TTY uses fallback approach."""
        tool = ShellTool()

        # Create a simple mock process
        async def mock_communicate():
            return (b"test output\n", b"")

        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = mock_communicate

        # Mock isatty to return False and subprocess creation
        with (
            patch('sys.stdin.isatty', return_value=False),
            patch('asyncio.create_subprocess_shell', return_value=mock_process) as mock_create,
        ):
                # Execute sudo command without TTY
                result = await tool.execute(command="sudo echo test")

                # Should use modified command with SUDO_ASKPASS
                mock_create.assert_called_once()
                call_args = mock_create.call_args[0][0]
                assert "sudo -A" in call_args or "SUDO_ASKPASS" in str(mock_create.call_args[1].get('env', {}))
                assert result.success is True
