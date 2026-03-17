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
except ImportError:  # pragma: no cover
    from typing_extensions import Self

# Timing constants for key monitoring loops
_KEY_POLL_INTERVAL_SECS: float = 0.01
_SUSPEND_WAIT_SECS: float = 0.1


def is_slash_command(text: str) -> bool:
    """Check if input is a slash command.

    Args:
        text: User input text.

    Returns:
        True if input starts with / followed by a command name.
    """
    if not text.startswith("/"):
        return False
    if len(text) <= 1 or text[1:].isspace():
        return False
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


def _is_path_within_cwd(path: Path) -> bool:
    """Check that a path stays within the current working directory.

    Args:
        path: The path to validate.

    Returns:
        True if the path is safe (absolute or within cwd), False otherwise.
    """
    try:
        resolved = path.resolve()
        return path.is_absolute() or resolved.is_relative_to(Path.cwd())
    except (ValueError, RuntimeError):
        return False


def _read_file_as_replacement(filepath: str, path: Path) -> str | None:
    """Read a file and format it as an inline replacement string.

    Args:
        filepath: Original filepath string (used in the formatted output).
        path: Resolved Path object to read.

    Returns:
        Formatted replacement string, or None if file is too large or unreadable.
    """
    try:
        file_size = path.stat().st_size
        if file_size > MAX_FILE_SIZE_BYTES:
            return (
                f"\n--- File: {filepath} ---\n"
                f"[File too large ({file_size} bytes > {MAX_FILE_SIZE_BYTES} limit)]\n---\n"
            )
        content = path.read_text(encoding="utf-8", errors="replace")
    except (OSError, PermissionError, UnicodeDecodeError):
        return None
    else:
        return f"\n--- File: {filepath} ---\n{content}\n---\n"


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
    for match in reversed(matches):
        filepath = match.group(1)
        path = Path(filepath)

        if not _is_path_within_cwd(path):
            continue
        if not path.exists() or not path.is_file():
            continue

        replacement = _read_file_as_replacement(filepath, path)
        if replacement is not None:
            result = result[: match.start()] + replacement + result[match.end() :]

    return result


def _register_custom_keybindings(bindings: KeyBindings, keybindings: dict[str, str]) -> None:
    """Register custom key-to-action bindings.

    Args:
        bindings: KeyBindings instance to register into.
        keybindings: Dictionary mapping key strings to action names.
    """
    for key, action in keybindings.items():
        if action == "abort":

            @bindings.add(key)
            def _(event: Any) -> None:
                event.app.exit(exception=KeyboardInterrupt, style="class:aborting")

        elif action == "exit":

            @bindings.add(key)
            def _(_event: Any) -> None:
                raise EOFError


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
            buffer.text = ""
        else:
            with contextlib.suppress(Exception):
                event.app.exit(result="")

    if keybindings:
        _register_custom_keybindings(bindings, keybindings)

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
        prompt: str = "\u276f ",
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


def _ask_parameter_value(
    console: Any,
    param_name: str,
    param_schema: dict[str, Any],
) -> Any:
    """Prompt the user for a single parameter value.

    Args:
        console: Rich console for input/output.
        param_name: Name of the parameter.
        param_schema: JSON schema describing the parameter.

    Returns:
        The user-provided value, cast to the appropriate type.
    """
    param_type = param_schema.get("type", "string")
    description = param_schema.get("description", "")
    default = param_schema.get("default")

    prompt_text = f"[cyan]{param_name}[/]"
    if description:
        prompt_text += f" ({description})"

    if param_type == "boolean":
        return Confirm.ask(
            prompt_text,
            default=default if default is not None else False,
            console=console,
        )
    if param_type == "integer":
        return IntPrompt.ask(prompt_text, default=default, console=console)
    return Prompt.ask(prompt_text, default=default, console=console)


class ToolForm:
    """Interactive form for tool parameter input."""

    def __init__(self: Self, console: Console) -> None:
        """Initialize the tool form.

        Args:
            console: Rich console for input/output.
        """
        self.console = console

    def prompt_for_parameters(
        self: Self,
        tool_name: str,
        parameters: dict[str, Any],
    ) -> dict[str, Any]:
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
            results[param_name] = _ask_parameter_value(self.console, param_name, param_schema)

        return results


class KeyMonitor:
    """Monitors for specific keys while an async task is running.

    This is used to detect Escape or Ctrl+C while the agent is generating output.
    """

    def __init__(self: Self) -> None:
        """Initialize the key monitor."""
        from prompt_toolkit.input import create_input

        self.input = create_input()
        self._stop_event = asyncio.Event()
        self._exit_event = asyncio.Event()
        self._suspended = asyncio.Event()
        self._suspended.set()  # Not suspended initially
        self._in_raw_mode = False

    async def suspend(self: Self) -> None:
        """Suspend monitoring to allow other input reading.

        Returns:
            None
        """
        self._suspended.clear()
        while self._in_raw_mode:
            await asyncio.sleep(_KEY_POLL_INTERVAL_SECS)

    def resume(self: Self) -> None:
        """Resume monitoring.

        Returns:
            None
        """
        self._suspended.set()

    async def monitor(self: Self) -> None:
        """Monitor input for keys. Run this in a background task.

        Returns:
            None
        """
        while not self._should_stop_monitoring():
            if not self._suspended.is_set():
                await asyncio.sleep(_SUSPEND_WAIT_SECS)
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
            if not self._suspended.is_set():
                await asyncio.sleep(_SUSPEND_WAIT_SECS)

    async def _active_monitoring_loop(self: Self) -> None:
        """Active monitoring loop that reads and processes keys."""
        while self._should_continue_monitoring():
            keys = self.input.read_keys()
            self._process_keys(keys)
            await asyncio.sleep(_KEY_POLL_INTERVAL_SECS)

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
