"""CLI package for MLG.

This module provides the terminal UI with Rich console output,
prompt_toolkit input, and slash command support.
"""

from henchman.cli.console import OutputRenderer, Theme, ThemeManager, get_default_theme
from henchman.cli.input import (
    InputHandler,
    expand_at_references,
    is_shell_command,
    is_slash_command,
    parse_shell_command,
)
from henchman.cli.repl import Repl, ReplConfig

__all__ = [
    "InputHandler",
    "OutputRenderer",
    "Repl",
    "ReplConfig",
    "Theme",
    "ThemeManager",
    "expand_at_references",
    "get_default_theme",
    "is_shell_command",
    "is_slash_command",
    "parse_shell_command",
]
