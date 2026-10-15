"""Tests for shared tool security helpers."""

import pytest

from henchman.tools.security import (
    CommandInjectionError,
    sanitize_command,
    sanitize_error_message,
)


class TestSanitizeCommand:
    """Tests for command sanitization."""

    def test_strips_safe_command(self) -> None:
        """Returns a trimmed command when input is safe."""
        assert sanitize_command("  echo 'hello'  ") == "echo 'hello'"

    @pytest.mark.parametrize(
        ("command", "pattern"),
        [
            pytest.param("", "empty", id="empty"),
            pytest.param("echo ok\nrm -rf /", "control characters", id="newline"),
            pytest.param("echo ${payload@P}", "@P", id="parameter-transformation"),
            pytest.param("echo ${!payload}", "indirect expansion", id="indirect-expansion"),
            pytest.param("echo $(whoami)", "command substitution", id="command-substitution"),
        ],
    )
    def test_rejects_unsafe_command(self, command: str, pattern: str) -> None:
        """Rejects prompt-injection primitives and malformed commands."""
        with pytest.raises((CommandInjectionError, ValueError), match=pattern):
            sanitize_command(command)


class TestSanitizeErrorMessage:
    """Tests for error message sanitization."""

    def test_normalizes_control_characters(self) -> None:
        """Flattens control characters into a single-line message."""
        error = RuntimeError("unsafe\nmessage\twith\x00controls")
        assert sanitize_error_message(error) == "unsafe message with controls"
