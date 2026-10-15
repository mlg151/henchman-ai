"""Base abstractions for chat integrations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class ChatPlatform(Enum):
    """Supported chat platforms."""

    TELEGRAM = "telegram"
    DISCORD = "discord"
    SLACK = "slack"


@dataclass
class ChatMessage:
    """Represents a message from a chat platform.

    Attributes:
        id: Unique message identifier from the platform.
        user_id: User identifier from the platform.
        username: Display name of the user.
        content: Text content of the message.
        timestamp: When the message was sent.
        platform: Which platform sent the message.
        attachments: List of file attachments (if any).
        is_dm: Whether this is a direct message.
    """

    id: str
    user_id: str
    username: str
    content: str
    timestamp: datetime
    platform: ChatPlatform
    attachments: list[dict[str, Any]] = field(default_factory=list)
    is_dm: bool = True


class ChatBot(ABC):
    """Abstract base class for chat platform integrations.

    This class defines the interface that all chat bot implementations
    must follow to integrate with Henchman-AI.
    """

    @property
    @abstractmethod
    def platform(self) -> ChatPlatform:
        """Return the platform type.

        Returns:
            ChatPlatform enum value.
        """
        ...  # pragma: no cover

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Check if the bot is connected to the platform.

        Returns:
            True if connected, False otherwise.
        """
        ...  # pragma: no cover

    @abstractmethod
    async def start(self) -> None:
        """Start the bot and connect to the platform.

        Returns:
            None
        """
        ...  # pragma: no cover

    @abstractmethod
    async def stop(self) -> None:
        """Stop the bot and disconnect from the platform.

        Returns:
            None
        """
        ...  # pragma: no cover

    @abstractmethod
    async def send_message(
        self,
        user_id: str,
        content: str,
        *,
        split_long: bool = True,
    ) -> bool:
        """Send a message to a user.

        Args:
            user_id: Platform-specific user identifier.
            content: Message content to send.
            split_long: Whether to split messages exceeding platform limits.

        Returns:
            True when the message was sent, otherwise False.
        """
        ...  # pragma: no cover

    @abstractmethod
    async def send_typing(self, user_id: str) -> None:
        """Send a typing indicator to a user.

        Args:
            user_id: Platform-specific user identifier.

        Returns:
            None
        """
        ...  # pragma: no cover

    @abstractmethod
    def set_message_handler(
        self,
        handler: Any,
    ) -> None:
        """Set the handler for incoming messages.

        Args:
            handler: Async callable that processes incoming ChatMessages.

        Returns:
            None
        """
        ...  # pragma: no cover
