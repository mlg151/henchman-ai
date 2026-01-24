"""Extensions module for Henchman-AI.

This module provides the extension system for adding third-party
tools, commands, and context to the CLI.
"""

from henchman.extensions.base import Extension
from henchman.extensions.manager import ExtensionManager

__all__ = [
    "Extension",
    "ExtensionManager",
]
