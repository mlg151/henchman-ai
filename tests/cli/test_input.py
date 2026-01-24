"""Tests for input handling and special syntax parsing."""

from __future__ import annotations

from pathlib import Path

import pytest

from henchman.cli.input import (
    InputHandler,
    expand_at_references,
    is_shell_command,
    is_slash_command,
    parse_shell_command,
)


class TestIsSlashCommand:
    """Tests for is_slash_command function."""

    def test_slash_command(self) -> None:
        """Test recognizing slash commands."""
        assert is_slash_command("/help") is True
        assert is_slash_command("/quit") is True
        assert is_slash_command("/model gpt-4") is True

    def test_not_slash_command(self) -> None:
        """Test non-slash command input."""
        assert is_slash_command("hello") is False
        assert is_slash_command("") is False
        assert is_slash_command(" /help") is False  # Leading space

    def test_just_slash(self) -> None:
        """Test just a slash is not a valid command."""
        assert is_slash_command("/") is False


class TestIsShellCommand:
    """Tests for is_shell_command function."""

    def test_shell_command(self) -> None:
        """Test recognizing shell commands."""
        assert is_shell_command("!ls") is True
        assert is_shell_command("!git status") is True
        assert is_shell_command("!echo hello") is True

    def test_not_shell_command(self) -> None:
        """Test non-shell command input."""
        assert is_shell_command("hello") is False
        assert is_shell_command("") is False
        assert is_shell_command(" !ls") is False  # Leading space

    def test_just_exclamation(self) -> None:
        """Test just an exclamation is not a valid command."""
        assert is_shell_command("!") is False


class TestParseShellCommand:
    """Tests for parse_shell_command function."""

    def test_simple_command(self) -> None:
        """Test parsing a simple shell command."""
        cmd = parse_shell_command("!ls")
        assert cmd == "ls"

    def test_command_with_args(self) -> None:
        """Test parsing a command with arguments."""
        cmd = parse_shell_command("!git status --short")
        assert cmd == "git status --short"

    def test_preserves_whitespace(self) -> None:
        """Test that internal whitespace is preserved."""
        cmd = parse_shell_command("!echo 'hello   world'")
        assert cmd == "echo 'hello   world'"

    def test_invalid_command_returns_empty(self) -> None:
        """Test that invalid input returns empty string."""
        assert parse_shell_command("not a shell command") == ""
        assert parse_shell_command("!") == ""


class TestExpandAtReferences:
    """Tests for expand_at_references function."""

    @pytest.fixture
    def temp_file(self, tmp_path: Path) -> Path:
        """Create a temporary file."""
        file = tmp_path / "test.txt"
        file.write_text("file content here")
        return file

    @pytest.mark.anyio
    async def test_no_references(self) -> None:
        """Test input with no @ references."""
        result = await expand_at_references("hello world")
        assert result == "hello world"

    @pytest.mark.anyio
    async def test_single_reference(self, temp_file: Path) -> None:
        """Test expanding a single @ reference."""
        result = await expand_at_references(f"Check @{temp_file}")
        assert "file content here" in result

    @pytest.mark.anyio
    async def test_multiple_references(self, tmp_path: Path) -> None:
        """Test expanding multiple @ references."""
        file1 = tmp_path / "file1.txt"
        file1.write_text("content1")
        file2 = tmp_path / "file2.txt"
        file2.write_text("content2")

        result = await expand_at_references(f"Compare @{file1} and @{file2}")
        assert "content1" in result
        assert "content2" in result

    @pytest.mark.anyio
    async def test_nonexistent_file(self) -> None:
        """Test that nonexistent file reference is preserved."""
        result = await expand_at_references("Check @nonexistent.txt")
        # Should keep the reference or indicate error
        assert "@nonexistent.txt" in result or "not found" in result.lower()

    @pytest.mark.anyio
    async def test_reference_in_middle(self, temp_file: Path) -> None:
        """Test @ reference in the middle of text."""
        result = await expand_at_references(f"Before @{temp_file} after")
        assert "file content here" in result
        assert "Before" in result
        assert "after" in result

    @pytest.mark.anyio
    async def test_unreadable_file(self, tmp_path: Path) -> None:
        """Test that unreadable file reference is preserved."""
        import stat

        file = tmp_path / "unreadable.txt"
        file.write_text("secret")
        # Make file unreadable
        file.chmod(0o000)
        try:
            result = await expand_at_references(f"Check @{file}")
            # Should keep the reference since file can't be read
            assert f"@{file}" in result or "unreadable.txt" in result
        finally:
            # Restore permissions for cleanup
            file.chmod(stat.S_IRUSR | stat.S_IWUSR)


class TestInputHandler:
    """Tests for InputHandler class."""

    def test_create_handler(self) -> None:
        """Test creating an input handler."""
        handler = InputHandler()
        assert handler is not None

    def test_handler_with_history_file(self, tmp_path: Path) -> None:
        """Test handler with custom history file."""
        history_path = tmp_path / ".henchman_history"
        handler = InputHandler(history_file=history_path)
        assert handler.history_file == history_path

    def test_get_prompt(self) -> None:
        """Test getting the prompt string."""
        handler = InputHandler()
        prompt = handler.get_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_custom_prompt(self) -> None:
        """Test custom prompt string."""
        handler = InputHandler(prompt=">>> ")
        assert handler.get_prompt() == ">>> "
