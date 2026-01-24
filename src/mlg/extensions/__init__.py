"""Extensions module for MLG-CLI.

This module provides the extension system for adding third-party
tools, commands, and context to the CLI.
"""

from mlg.extensions.base import Extension
from mlg.extensions.manager import ExtensionManager

__all__ = [
    "Extension",
    "ExtensionManager",
]
