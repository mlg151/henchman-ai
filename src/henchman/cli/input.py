"""Input handling and special syntax parsing.

This module handles user input including @ file references and ! shell commands.
"""

from __future__ import annotations

import asyncio
import contextlib
import re
from pathlib import Path
from typing import Any

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys


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


def create_session(
    history_file: Path | None = None,
    bottom_toolbar: Any = None,
) -> PromptSession[str]:
    """Create a PromptSession with custom key bindings.

    Args:
        history_file: Path to history file.
        bottom_toolbar: Optional callback for bottom toolbar.

    Returns:
        Configured PromptSession.
    """
    bindings = KeyBindings()

    @bindings.add(Keys.ControlC)
    def _(_event: Any) -> None:
        """Handle Ctrl+C: raise KeyboardInterrupt to exit cleanly."""
        raise KeyboardInterrupt()

    @bindings.add(Keys.Escape)
    def _(event: Any) -> None:
        """Handle Escape key: cancel input or clear buffer."""
        buffer = event.current_buffer
        if buffer.text:
            # Clear buffer if there is text
            buffer.text = ""
        else:
            # If buffer is empty, return to prompt with empty result
            # Use suppress to handle case where result is already set
            with contextlib.suppress(Exception):
                event.app.exit(result="")

    history = FileHistory(str(history_file)) if history_file else None

    return PromptSession(
        history=history,
        key_bindings=bindings,
        bottom_toolbar=bottom_toolbar,
    )


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


class KeyMonitor:
    """Monitors for specific keys while an async task is running.

    This is used to detect Escape or Ctrl+C while the agent is generating output.
    """

    def __init__(self) -> None:
        """Initialize the key monitor."""
        from prompt_toolkit.input import create_input

        self.input = create_input()
        self._stop_event = asyncio.Event()
        self._exit_event = asyncio.Event()
        self._suspended = asyncio.Event()
        self._suspended.set()  # Not suspended initially
        self._in_raw_mode = False

    async def suspend(self) -> None:
        """Suspend monitoring to allow other input reading."""
        self._suspended.clear()
        # Wait for the monitor loop to exit the raw mode block
        while self._in_raw_mode:
            await asyncio.sleep(0.01)

    def resume(self) -> None:
        """Resume monitoring."""
        self._suspended.set()

    async def monitor(self) -> None:
        """Monitor input for keys. Run this in a background task."""
        while not self._stop_event.is_set() and not self._exit_event.is_set():
            if not self._suspended.is_set():
                await asyncio.sleep(0.1)
                continue

            try:
                with self.input.raw_mode():
                    self._in_raw_mode = True
                    with self.input.attach(lambda: None):
                        while (
                            not self._stop_event.is_set()
                            and not self._exit_event.is_set()
                            and self._suspended.is_set()
                        ):
                            # Check for keys every 10ms
                            keys = self.input.read_keys()
                            for key in keys:
                                if key.key == Keys.Escape:
                                    self._stop_event.set()
                                elif key.key == Keys.ControlC:
                                    self._exit_event.set()
                            await asyncio.sleep(0.01)
            finally:
                self._in_raw_mode = False
                # If we were suspended, wait a bit before potentially re-entering raw mode
                if not self._suspended.is_set():
                    await asyncio.sleep(0.1)

    @property
    def stop_requested(self) -> bool:
        """Check if Escape was pressed."""
        return self._stop_event.is_set()

    @property
    def exit_requested(self) -> bool:
        """Check if Ctrl+C was pressed."""
        return self._exit_event.is_set()
