"""Test sudo command logic without actual execution."""

from unittest.mock import patch

from henchman.tools.base import ToolResult
from henchman.tools.builtins.shell import ShellTool


def test_sudo_detection_logic():
    """Test the logic for detecting sudo commands."""
    tool = ShellTool()

    # Test cases
    test_cases = [
        ("sudo apt update", True),
        ("  sudo apt update  ", True),
        ("sudo -S apt update", True),
        ("echo hello", False),
        ("", False),
        ("sudo", False),  # No space after sudo
        ("notsudo command", False),
    ]

    for command, expected in test_cases:
        result = tool._is_sudo_command(command)
        assert result == expected, (
            f"Failed for command: '{command}' - expected {expected}, got {result}"
        )

    print("✓ All sudo detection tests passed")


def test_parameter_schema():
    """Test that interactive parameter is in schema."""
    tool = ShellTool()
    params = tool.parameters

    assert "interactive" in params["properties"], "Interactive parameter missing from schema"
    assert params["properties"]["interactive"]["type"] == "boolean", (
        "Interactive parameter should be boolean"
    )
    assert params["properties"]["interactive"]["default"] is False, (
        "Interactive should default to False"
    )

    desc = params["properties"]["interactive"]["description"].lower()
    assert "sudo" in desc or "interactive" in desc, "Description should mention sudo or interactive"

    print("✓ Parameter schema tests passed")


def test_execution_path_logic():
    """Test the logic for choosing execution path."""
    tool = ShellTool()

    # Mock scenarios
    scenarios = [
        # (command, is_tty, interactive_param, should_use_interactive, should_use_sudo_fallback)
        ("sudo apt update", True, False, True, False),
        ("sudo apt update", False, False, False, True),
        ("echo hello", True, False, False, False),
        ("echo hello", False, False, False, False),
        ("echo hello", True, True, True, False),  # Explicit interactive
        ("sudo apt update", True, True, True, False),  # Explicit interactive for sudo
    ]

    for (
        command,
        is_tty,
        interactive_param,
        should_use_interactive,
        should_use_sudo_fallback,
    ) in scenarios:
        is_sudo = tool._is_sudo_command(command)

        # Logic from execute method
        use_interactive = (interactive_param or is_sudo) and is_tty
        use_sudo_fallback = is_sudo and not is_tty

        assert use_interactive == should_use_interactive, (
            f"Failed for command='{command}', is_tty={is_tty}, interactive={interactive_param}: "
            f"expected interactive={should_use_interactive}, got {use_interactive}"
        )

        assert use_sudo_fallback == should_use_sudo_fallback, (
            f"Failed for command='{command}', is_tty={is_tty}: "
            f"expected sudo_fallback={should_use_sudo_fallback}, got {use_sudo_fallback}"
        )

    print("✓ Execution path logic tests passed")


async def test_mocked_execution():
    """Test execution with mocked subprocess."""
    tool = ShellTool()

    # Mock a successful command execution
    mock_result = ToolResult(content="test output", success=True, error=None)

    # Patch the actual execution to return our mock result and simulate TTY
    with (
        patch.object(tool, "_execute_interactive_sudo", return_value=mock_result),
        patch("sys.stdin") as mock_stdin,
    ):
        mock_stdin.isatty.return_value = True
        # This should use interactive mode since we're in a TTY and it's sudo
        result = await tool.execute(background=False, command="sudo echo test")
        assert result.success is True
        assert result.content == "test output"

    print("✓ Mocked execution test passed")


if __name__ == "__main__":
    print("Running shell tool sudo logic tests...")
    print("=" * 50)

    test_sudo_detection_logic()
    print()

    test_parameter_schema()
    print()

    test_execution_path_logic()
    print()

    # Run async test
    import asyncio

    asyncio.run(test_mocked_execution())

    print("=" * 50)
    print("All tests passed! ✓")
