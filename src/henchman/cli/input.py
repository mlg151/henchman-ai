"""Input handling and special syntax parsing.

This module handles user input including @ file references and ! shell commands.
"""

from __future__ import annotations

import asyncio
import contextlib
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings, KeyPress
from prompt_toolkit.keys import Keys
from rich.prompt import Confirm, IntPrompt, Prompt

if TYPE_CHECKING:
    from rich.console import Console


try:
    from typing import Self
except ImportError:
    from typing_extensions import Self

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
    if len(text) <= 1 or text[1:].isspace():
        return False
    # Check if it's a comment (starts with //)
    return not text.startswith("//")


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

# Maximum file size to read (10 MB)
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024


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

        # Security: Prevent path traversal attacks
        try:
            resolved = path.resolve()  # noqa: ASYNC240
            # For relative paths, always verify they stay within cwd
            # (catches both '..' traversal and symlink escapes)
            if not path.is_absolute() and not resolved.is_relative_to(Path.cwd()):
                continue
        except (ValueError, RuntimeError):
            # If path resolution fails, skip this reference
            continue

        if path.exists() and path.is_file():  # noqa: ASYNC240
            try:
                # Security: Check file size before reading
                file_size = path.stat().st_size  # noqa: ASYNC240
                if file_size > MAX_FILE_SIZE_BYTES:
                    # File too large, skip with warning
                    replacement = f"\n--- File: {filepath} ---\n[File too large ({file_size} bytes > {MAX_FILE_SIZE_BYTES} limit)]\n---\n"  # noqa: E501
                    result = result[: match.start()] + replacement + result[match.end() :]
                    continue

                # Read with explicit encoding and size limit
                content = path.read_text(encoding="utf-8", errors="replace")  # noqa: ASYNC240
                # Format the replacement with context
                replacement = f"\n--- File: {filepath} ---\n{content}\n---\n"
                result = result[: match.start()] + replacement + result[match.end() :]
            except (OSError, PermissionError, UnicodeDecodeError):
                # Keep original reference if can't read
                pass
        # If file doesn't exist, keep the original reference

    return result


def create_session(
    history_file: Path | None = None,
    bottom_toolbar: Any = None,
    keybindings: dict[str, str] | None = None,
    completer: Any = None,
) -> PromptSession[str]:
    """Create a PromptSession with custom key bindings.

    Args:
        history_file: Path to history file.
        bottom_toolbar: Optional callback for bottom toolbar.
        keybindings: Dictionary of keybindings (key -> action).
        completer: Optional completer for tab completion.

    Returns:
        Configured PromptSession.
    """
    bindings = KeyBindings()

    @bindings.add(Keys.ControlC)
    def _(_event: Any) -> None:
        """Handle Ctrl+C: raise KeyboardInterrupt to exit cleanly."""
        raise KeyboardInterrupt

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

    # Custom keybindings
    if keybindings:
        for key, action in keybindings.items():
            # Map simplified key names to prompt_toolkit keys if needed
            # For now, assume key is a valid prompt_toolkit key string (e.g. 'c-t')

            if action == "abort":

                @bindings.add(key)
                def _(event: Any) -> None:
                    event.app.exit(exception=KeyboardInterrupt, style="class:aborting")
            elif action == "exit":

                @bindings.add(key)
                def _(_event: Any) -> None:
                    raise EOFError  # Or _event.app.exit(exception=EOFError)

    history = FileHistory(str(history_file)) if history_file else None

    return PromptSession(
        history=history,
        key_bindings=bindings,
        bottom_toolbar=bottom_toolbar,
        completer=completer,
    )


class InputHandler:
    """Handles user input with history and prompt customization.

    Attributes:
        history_file: Path to command history file.
        prompt: Prompt string to display.
    """

    def __init__(
        self: Self,
        history_file: Path | None = None,
        prompt: str = "❯ ",  # noqa: RUF001
    ) -> None:
        """Initialize the input handler.

        Args:
            history_file: Optional path to history file.
            prompt: Prompt string to display.
        """
        self.history_file = history_file or Path.home() / ".henchman_history"
        self._prompt = prompt

    def get_prompt(self: Self) -> str:
        """Get the prompt string.

        Returns:
            The prompt string.
        """
        return self._prompt


class ToolForm:
    """Interactive form for tool parameter input."""

    def __init__(self: Self, console: Console):
        """Initialize the tool form.

        Args:
            console: Rich console for input/output.
        """
        self.console = console

    def prompt_for_parameters(self: Self, tool_name: str, parameters: dict[str, Any]) -> dict[str, Any]:  # noqa: E501
        """Prompt user for tool parameters.

        Args:
            tool_name: Name of the tool.
            parameters: JSON schema of parameters.

        Returns:
            Dictionary of parameter values.
        """
        results: dict[str, Any] = {}
        properties = parameters.get("properties", {})

        self.console.print(f"\n[bold blue]Configure {tool_name}[/]")

        for param_name, param_schema in properties.items():
            param_type = param_schema.get("type", "string")
            description = param_schema.get("description", "")
            # is_required = param_name in required  # Not currently used
            default = param_schema.get("default")

            prompt_text = f"[cyan]{param_name}[/]"
            if description:
                prompt_text += f" ({description})"

            # Helper to run rich prompt in thread to avoid blocking asyncio loop if needed
            # But here we assume this is running in a context where blocking is okay or handled
            # For strict asyncio compatibility, we might need anyio.to_thread.run_sync
            # However, prompt_toolkit/rich input is blocking.
            # Given existing code uses prompt_toolkit async, we should be careful.
            # But rich.prompt is blocking.

            # Let's use basic blocking calls for now as this is likely invoked from start_tool_form
            # which might be run in a thread or handled.

            if param_type == "boolean":
                value = Confirm.ask(
                    prompt_text,
                    default=default if default is not None else False,
                    console=self.console,
                )
            elif param_type == "integer":
                value = IntPrompt.ask(prompt_text, default=default, console=self.console)
            else:  # string
                value = Prompt.ask(prompt_text, default=default, console=self.console)

            results[param_name] = value

        return results


class KeyMonitor:
    """Monitors for specific keys while an async task is running.

    This is used to detect Escape or Ctrl+C while the agent is generating output.
    """

    def __init__(self: Self) -> None:
        """Initialize the key monitor."""
        from prompt_toolkit.input import create_input  # noqa: PLC0415

        self.input = create_input()
        self._stop_event = asyncio.Event()
        self._exit_event = asyncio.Event()
        self._suspended = asyncio.Event()
        self._suspended.set()  # Not suspended initially
        self._in_raw_mode = False

    async def suspend(self: Self) -> None:
        """Suspend monitoring to allow other input reading."""
        self._suspended.clear()
        # Wait for the monitor loop to exit the raw mode block
        while self._in_raw_mode:  # noqa: ASYNC110
            await asyncio.sleep(0.01)

    def resume(self: Self) -> None:
        """Resume monitoring."""
        self._suspended.set()

    async def monitor(self: Self) -> None:
        """Monitor input for keys. Run this in a background task."""
        while not self._should_stop_monitoring():
            if not self._suspended.is_set():
                await asyncio.sleep(0.1)
                continue

            await self._monitor_in_raw_mode()

    def _should_stop_monitoring(self: Self) -> bool:
        """Check if monitoring should stop.

        Returns:
            True if either stop or exit event is set.
        """
        return self._stop_event.is_set() or self._exit_event.is_set()

    async def _monitor_in_raw_mode(self: Self) -> None:
        """Monitor keys while in raw mode."""
        try:
            with self.input.raw_mode():
                self._in_raw_mode = True
                with self.input.attach(lambda: None):
                    await self._active_monitoring_loop()
        finally:
            self._in_raw_mode = False
            # If we were suspended, wait a bit before potentially re-entering raw mode
            if not self._suspended.is_set():
                await asyncio.sleep(0.1)

    async def _active_monitoring_loop(self: Self) -> None:
        """Active monitoring loop that reads and processes keys."""
        while self._should_continue_monitoring():
            keys = self.input.read_keys()
            self._process_keys(keys)
            await asyncio.sleep(0.01)

    def _should_continue_monitoring(self: Self) -> bool:
        """Check if active monitoring should continue.

        Returns:
            True if not stopped, not exited, and not suspended.
        """
        return (
            not self._stop_event.is_set()
            and not self._exit_event.is_set()
            and self._suspended.is_set()
        )

    def _process_keys(self: Self, keys: list[KeyPress]) -> None:
        """Process a list of keys.

        Args:
            keys: List of key events to process.
        """
        for key in keys:
            if key.key == Keys.Escape:
                self._stop_event.set()
            elif key.key == Keys.ControlC:
                self._exit_event.set()

    @property
    def stop_requested(self: Self) -> bool:
        """Check if Escape was pressed."""
        return self._stop_event.is_set()

    @property
    def exit_requested(self: Self) -> bool:
        """Check if Ctrl+C was pressed."""
        return self._exit_event.is_set()
