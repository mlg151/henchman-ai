"""Input handler for REPL.

This module handles user input processing including prompt sessions,
@file expansion, and shell command detection.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter

from henchman.cli.commands.builtins import get_builtin_commands
from henchman.cli.input import create_session, expand_at_references, is_slash_command

if TYPE_CHECKING:
    from henchman.cli.repl import ReplConfig
    from henchman.tools.registry import ToolRegistry


class InputHandler:
    """Handles user input processing for the REPL.

    Responsibilities:
    - Manage prompt sessions
    - Handle @file expansion
    - Detect shell commands
    - Get user input with proper error handling
    """

    def __init__(
        self,
        config: ReplConfig,
        renderer: object,
        history_file: Path | None = None,
        keybindings: dict[str, str] | None = None,
        tool_registry: ToolRegistry | None = None,
    ) -> None:
        """Initialize the input handler.

        Args:
            config: REPL configuration.
            renderer: UI renderer for output.
            history_file: Path to history file.
            keybindings: Custom keybindings configuration.
            tool_registry: Optional tool registry for tool name completions.
        """
        self.config = config
        self.renderer = renderer
        self.history_file = history_file or Path.home() / ".henchman_history"
        self.keybindings = keybindings
        self.tool_registry = tool_registry
        self.prompt_session: PromptSession[str] | None = None

    def initialize_prompt_session(
        self, bottom_toolbar: Callable[[], list[tuple[str, str]]] | None = None
    ) -> None:
        """Initialize the prompt session.

        Args:
            bottom_toolbar: Function to generate bottom toolbar content.
        """
        # Create completer for commands and tools
        commands = [f"/{cmd.name}" for cmd in get_builtin_commands()]

        # Add tools to completion list when available
        tools = []
        if self.tool_registry and hasattr(self.tool_registry, "list_tools"):
            tools = [f"!{tool}" for tool in self.tool_registry.list_tools()]

        completer = WordCompleter(commands + tools, ignore_case=True)

        self.prompt_session = create_session(
            self.history_file,
            bottom_toolbar=bottom_toolbar,
            keybindings=self.keybindings,
        )
        # Manually set completer since create_session helper might not expose it yet
        # or we need to update create_session to support it.
        # Let's check create_session in input.py... it doesn't support completer arg yet.
        self.prompt_session.completer = completer

    async def get_input(self) -> str:
        """Get input from the user.

        Returns:
            User input string.

        Raises:
            KeyboardInterrupt: If user presses Ctrl+C.
            EOFError: If user presses Ctrl+D.
        """
        if not self.prompt_session:
            raise RuntimeError("Prompt session not initialized")

        # Ensure a fresh line for the prompt
        if hasattr(self.renderer, "print_newline"):
            self.renderer.print_newline()
        return await self.prompt_session.prompt_async(self.config.prompt)

    def is_slash_command(self, input_text: str) -> bool:
        """Check if input is a slash command.

        Args:
            input_text: The input text to check.

        Returns:
            True if input is a slash command.
        """
        return is_slash_command(input_text)

    async def expand_at_references(self, input_text: str) -> str:
        """Expand @file references in input.

        Args:
            input_text: The input text to expand.

        Returns:
            Expanded input text.
        """
        return await expand_at_references(input_text)

    async def process_input(self, user_input: str) -> tuple[str, bool, bool]:
        """Process user input to determine if it's a command or regular input.

        Args:
            user_input: The raw user input.

        Returns:
            Tuple of (processed_input, is_command, should_continue)
            - processed_input: Expanded input text (if not a command)
            - is_command: True if input is a slash command
            - should_continue: True if REPL should continue running (False to exit)
        """
        stripped = user_input.strip()
        if not stripped:
            return "", False, True

        if self.is_slash_command(stripped):
            # For slash commands, return the command text
            # REPL will handle actual command execution
            return stripped, True, True

        # Expand @file references for regular input
        expanded = await self.expand_at_references(stripped)
        return expanded, False, True
