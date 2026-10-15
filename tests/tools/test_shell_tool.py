"""Tests for shell tool."""

import tempfile

from henchman.tools.base import ToolKind
from henchman.tools.builtins.shell import ShellTool


class TestShellTool:
    """Tests for ShellTool."""

    def test_name(self) -> None:
        """Tool has correct name."""
        tool = ShellTool()
        assert tool.name == "shell"

    def test_description(self) -> None:
        """Tool has description."""
        tool = ShellTool()
        assert "shell" in tool.description.lower() or "command" in tool.description.lower()

    def test_kind_is_execute(self) -> None:
        """Tool is an EXECUTE kind (requires confirmation)."""
        tool = ShellTool()
        assert tool.kind == ToolKind.EXECUTE

    def test_parameters_schema(self) -> None:
        """Tool has correct parameters schema."""
        tool = ShellTool()
        params = tool.parameters
        assert "command" in params["properties"]
        assert "command" in params["required"]

    async def test_shell_simple_command(self) -> None:
        """Execute simple shell command."""
        tool = ShellTool()
        result = await tool.execute(background=False, command="echo hello")
        assert result.success is True
        assert "hello" in result.content

    async def test_shell_command_with_exit_code(self) -> None:
        """Capture exit code from command."""
        tool = ShellTool()
        result = await tool.execute(background=False, command="exit 0")
        assert result.success is True

        result = await tool.execute(background=False, command="exit 1")
        assert result.success is False

    async def test_shell_captures_stderr(self) -> None:
        """Capture stderr output."""
        tool = ShellTool()
        result = await tool.execute(background=False, command="echo error >&2")
        assert "error" in result.content

    async def test_shell_captures_stdout_and_stderr(self) -> None:
        """Capture both stdout and stderr."""
        tool = ShellTool()
        result = await tool.execute(background=False, command="echo out && echo err >&2")
        assert "out" in result.content
        assert "err" in result.content

    async def test_shell_sets_henchman_cli_env(self) -> None:
        """HENCHMAN_CLI=1 environment variable is set."""
        tool = ShellTool()
        result = await tool.execute(background=False, command="echo $HENCHMAN_CLI")
        assert result.success is True
        assert "1" in result.content

    async def test_shell_timeout(self) -> None:
        """Command times out after specified duration."""
        tool = ShellTool()
        result = await tool.execute(background=False, command="sleep 10", timeout=1)
        assert result.success is False
        assert "timeout" in result.error.lower()

    async def test_shell_working_directory(self) -> None:
        """Execute command in specified working directory."""
        tool = ShellTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            result = await tool.execute(background=False, command="pwd", cwd=tmpdir)
            assert result.success is True
            assert tmpdir in result.content

    async def test_shell_invalid_command(self) -> None:
        """Handle invalid command."""
        tool = ShellTool()
        result = await tool.execute(background=False, command="nonexistent_command_xyz")
        assert result.success is False

    async def test_shell_multiline_output(self) -> None:
        """Handle multiline output."""
        tool = ShellTool()
        result = await tool.execute(background=False, command="echo line1 && echo line2 && echo line3")
        assert result.success is True
        assert "line1" in result.content
        assert "line2" in result.content
        assert "line3" in result.content

    def test_default_timeout_constructor(self) -> None:
        """Constructor accepts custom default_timeout."""
        tool = ShellTool(default_timeout=120)
        assert tool._default_timeout == 120

    def test_default_timeout_is_3600(self) -> None:
        """Default timeout is 1 hour (3600s)."""
        tool = ShellTool()
        assert tool._default_timeout == 3600

    async def test_timeout_zero_means_no_timeout(self) -> None:
        """Timeout=0 should mean no timeout (wait indefinitely)."""
        tool = ShellTool()
        # Quick command with timeout=0 should still complete
        result = await tool.execute(background=False, command="echo done", timeout=0)
        assert result.success is True
        assert "done" in result.content

    async def test_custom_default_timeout_used_on_timeout(self) -> None:
        """Custom default_timeout is applied when no timeout passed."""
        tool = ShellTool(default_timeout=1)
        result = await tool.execute(background=False, command="sleep 10")
        assert result.success is False
        assert "timeout" in result.error.lower()

    def test_description_mentions_long_running(self) -> None:
        """Description communicates long-running support."""
        tool = ShellTool()
        assert "long-running" in tool.description.lower() or "long" in tool.description.lower()
