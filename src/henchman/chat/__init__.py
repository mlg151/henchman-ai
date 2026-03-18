"""Chat integration module for Henchman-AI.

This module provides chat bot integrations for remote access to Henchman-AI.

Optional dependency: Install with `pip install henchman-ai[discord]` for Discord support.
"""

from __future__ import annotations

from henchman.chat.base import ChatBot, ChatMessage, ChatPlatform
from henchman.chat.manager import ChatManager

__all__ = [
    "ChatBot",
    "ChatManager",
    "ChatMessage",
    "ChatPlatform",
]


def __getattr__(name: str) -> object:
    """Lazy import for optional Discord integration.

    Args:
        name: Attribute name being accessed.

    Returns:
        The requested attribute.

    Raises:
        ImportError: If discord.py is not installed.
        AttributeError: If attribute does not exist.
    """
    if name == "DiscordBot":
        from henchman.chat.discord_bot import DiscordBot

        return DiscordBot
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
