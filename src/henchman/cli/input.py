"""Input handling and special syntax parsing.

This module handles user input including @ file references and ! shell commands.
"""

from __future__ import annotations

import re
from pathlib import Path


def is_slash_command(text: str) -> bool:
    """Check if input is a slash command.

    Args:
        text: User input text.

    Returns:
        True if input starts with / followed by a command name.
    """
    if not text.startswith("/"):
        return False
    # Must have at least one character after the slash
    return len(text) > 1 and not text[1:].isspace()


def is_shell_command(text: str) -> bool:
    """Check if input is a shell command.

    Args:
        text: User input text.

    Returns:
        True if input starts with ! followed by a command.
    """
    if not text.startswith("!"):
        return False
    # Must have at least one character after the !
    return len(text) > 1 and text[1:].strip() != ""


def parse_shell_command(text: str) -> str:
    """Parse a shell command from input.

    Args:
        text: User input starting with !

    Returns:
        The shell command string, or empty string if invalid.
    """
    if not is_shell_command(text):
        return ""
    return text[1:]


# Pattern to match @filepath references
AT_REFERENCE_PATTERN = re.compile(r"@([\w./\-_]+)")


async def expand_at_references(text: str) -> str:
    """Expand @file references in text with file contents.

    Args:
        text: User input text possibly containing @filepath references.

    Returns:
        Text with @references replaced by file contents.
    """
    matches = list(AT_REFERENCE_PATTERN.finditer(text))
    if not matches:
        return text

    result = text
    # Process in reverse order to preserve positions
    for match in reversed(matches):
        filepath = match.group(1)
        path = Path(filepath)

        if path.exists() and path.is_file():
            try:
                content = path.read_text()
                # Format the replacement with context
                replacement = f"\n--- File: {filepath} ---\n{content}\n---\n"
                result = result[: match.start()] + replacement + result[match.end() :]
            except (OSError, PermissionError):
                # Keep original reference if can't read
                pass
        # If file doesn't exist, keep the original reference

    return result


class InputHandler:
    """Handles user input with history and prompt customization.

    Attributes:
        history_file: Path to command history file.
        prompt: Prompt string to display.
    """

    def __init__(
        self,
        history_file: Path | None = None,
        prompt: str = "❯ ",
    ) -> None:
        """Initialize the input handler.

        Args:
            history_file: Optional path to history file.
            prompt: Prompt string to display.
        """
        self.history_file = history_file or Path.home() / ".henchman_history"
        self._prompt = prompt

    def get_prompt(self) -> str:
        """Get the prompt string.

        Returns:
            The prompt string.
        """
        return self._prompt
