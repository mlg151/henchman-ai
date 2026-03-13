"""Tests for interactive shell tool functionality (sudo support)."""

from unittest.mock import AsyncMock, MagicMock, patch

from henchman.tools.builtins.shell import ShellTool


def _make_mock_process(
    stdout_data: bytes = b"test output\n", stderr_data: bytes = b"", returncode: int = 0
) -> AsyncMock:
    """Create a mock process with properly terminating stdout/stderr streams."""
    mock_process = AsyncMock()
    mock_process.returncode = returncode
    mock_process.pid = 12345

    # Create mock streams that return data once then EOF
    stdout_stream = MagicMock()
    stdout_stream.read = AsyncMock(side_effect=[stdout_data, b""])
    stderr_stream = MagicMock()
    stderr_stream.read = AsyncMock(side_effect=[stderr_data, b""])

    mock_process.stdout = stdout_stream
    mock_process.stderr = stderr_stream

    # wait() should return the returncode
    mock_process.wait = AsyncMock(return_value=returncode)

    return mock_process


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
        assert (
            tool._is_sudo_command("sudo") is False
        )  # "sudo" alone (no space) is not a valid sudo command
        assert tool._is_sudo_command("notsudo command") is False

    async def test_non_interactive_mode_for_non_sudo(self) -> None:
        """Non-interactive mode is used for non-sudo commands."""
        tool = ShellTool()
        mock_process = _make_mock_process()

        with patch("asyncio.create_subprocess_shell", return_value=mock_process) as mock_create:
            result = await tool.execute(command="echo test")

            mock_create.assert_called_once()
            assert result.success is True
            assert "test output" in result.content

    async def test_sudo_without_tty_falls_back(self) -> None:
        """Sudo command without TTY uses fallback approach."""
        tool = ShellTool()
        mock_process = _make_mock_process()

        with (
            patch("sys.stdin") as mock_stdin,
            patch("asyncio.create_subprocess_shell", return_value=mock_process) as mock_create,
        ):
            mock_stdin.isatty.return_value = False
            result = await tool.execute(command="sudo echo test")

            mock_create.assert_called_once()
            call_args = mock_create.call_args[0][0]
            assert "sudo -A" in call_args or "SUDO_ASKPASS" in str(
                mock_create.call_args[1].get("env", {})
            )
            assert result.success is True
