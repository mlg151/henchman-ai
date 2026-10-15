"""Tests for BUG-013: Shell Metacharacter Injection via Sudo Command Rewrite.

Verifies that sanitize_command() blocks dangerous command injection patterns
(``$()``, backticks, ``${}`` variable expansions) while allowing standard
shell operators (``;``, ``&&``, ``||``). Standard operators are safe because
the shell tool is already behind user confirmation (ToolKind.EXECUTE).
"""

import pytest

from henchman.tools.security import CommandInjectionError, sanitize_command


class TestShellMetacharacterBlocking:
    """sanitize_command blocks shell metacharacters used for injection."""

    @pytest.mark.parametrize(
        "command",
        [
            "echo $(whoami)",
            "echo `whoami`",
            "echo ${PATH}",
            "echo ${IFS}rm${IFS}-rf${IFS}/",
        ],
    )
    def test_rejects_shell_metacharacters(self, command: str) -> None:
        """Commands with dangerous patterns are rejected."""
        with pytest.raises(CommandInjectionError):
            sanitize_command(command)

    @pytest.mark.parametrize(
        "command",
        [
            "echo hello",
            "ls -la",
            "sudo apt-get update",
            "cat /etc/hostname",
            "grep foo bar.txt",
            # Standard shell operators are allowed (confirmation is the defense)
            "sudo ; echo pwned",
            "sudo ; rm -rf /",
            "sudo && rm -rf /",
            "sudo || echo pwned",
            "ls -la ; id",
            "echo hello && whoami",
            "false || cat /etc/passwd",
        ],
    )
    def test_accepts_safe_commands(self, command: str) -> None:
        """Simple safe commands are accepted."""
        result = sanitize_command(command)
        assert result == command.strip()
