"""Tool system for Henchman-AI.

This module provides the tool framework that allows the LLM to perform
actions like reading files, executing commands, and making web requests.
"""

from henchman.tools.base import (
    ConfirmationRequest,
    Tool,
    ToolKind,
    ToolResult,
)
from henchman.tools.registry import ToolRegistry

__all__ = [
    "ConfirmationRequest",
    "Tool",
    "ToolKind",
    "ToolRegistry",
    "ToolResult",
]
