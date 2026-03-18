"""Discord bot integration for Henchman-AI.

This module requires the 'discord' optional dependency:
    pip install henchman-ai[discord]
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Coroutine
from datetime import datetime, timezone
from typing import Any

from henchman.chat.base import ChatBot, ChatMessage, ChatPlatform

logger = logging.getLogger(__name__)

# Discord message limit
DISCORD_MESSAGE_LIMIT = 2000


def _check_discord_installed() -> None:
    """Check if discord.py is installed.

    Raises:
        ImportError: If discord.py is not installed.
    """
    try:
        import discord  # noqa: F401
    except ImportError:
        msg = (
            "discord.py is required for Discord integration.\n"
            "Install it with: pip install henchman-ai[discord]"
        )
        raise ImportError(msg) from None


class DiscordBot(ChatBot):
    """Discord bot for Henchman-AI remote access.

    This bot connects to Discord and relays messages between
    the user and Henchman-AI's agent system.

    Attributes:
        token: Discord bot token.
        allowed_user_id: Discord user ID authorized to use the bot.
    """

    def __init__(
        self,
        token: str,
        allowed_user_id: str,
    ) -> None:
        """Initialize the Discord bot.

        Args:
            token: Discord bot token from developer portal.
            allowed_user_id: Discord user ID (snowflake) authorized to use the bot.
        """
        _check_discord_installed()

        import discord

        self._token = token
        self._allowed_user_id = allowed_user_id
        self._message_handler: Callable[[ChatMessage], Coroutine[Any, Any, None]] | None = None
        self._is_connected = False

        # Configure intents
        intents = discord.Intents.default()
        intents.message_content = True  # Required to read message content
        intents.dm_messages = True  # Required for DM support

        # Create Discord client
        self._client: Any = discord.Client(intents=intents)
        self._setup_events()

    def _setup_events(self) -> None:
        """Set up Discord event handlers."""
        client = self._client

        @client.event  # type: ignore[untyped-decorator]
        async def on_ready() -> None:
            """Handle bot ready event."""
            self._is_connected = True
            logger.info(
                "Discord bot connected as %s (ID: %s)",
                client.user,
                client.user.id if client.user else "unknown",
            )
            print(f"✅ Discord bot connected as {client.user}")

        @client.event  # type: ignore[untyped-decorator]
        async def on_message(message: Any) -> None:
            """Handle incoming messages.

            Args:
                message: Discord message object.
            """
            import discord

            # Ignore messages from the bot itself
            if message.author == client.user:
                return

            # Check if it's a DM or a mention in a server channel
            is_dm = isinstance(message.channel, discord.DMChannel)
            is_mentioned = client.user in message.mentions if not is_dm else False
            
            # Only process DMs or messages that mention the bot
            if not is_dm and not is_mentioned:
                return

            if str(message.author.id) != self._allowed_user_id:
                logger.warning(
                    "Unauthorized message from user %s (ID: %s)",
                    message.author.name,
                    message.author.id,
                )
                return

            # Clean up message content (strip mention if in server)
            content = message.content
            if is_mentioned and not is_dm:
                # Remove the bot mention from the content
                for mention in message.mentions:
                    if mention == client.user:
                        content = content.replace(f'<@{mention.id}>', '').strip()
                        content = content.replace(f'<@!{mention.id}>', '').strip()
            
            # Convert to ChatMessage
            chat_message = ChatMessage(
                id=str(message.id),
                user_id=str(message.author.id),
                username=message.author.display_name,
                content=content,
                timestamp=message.created_at or datetime.now(timezone.utc),
                platform=ChatPlatform.DISCORD,
                attachments=[{"filename": a.filename, "url": a.url} for a in message.attachments],
                is_dm=is_dm,
            )

            # Call the registered handler
            if self._message_handler:
                try:
                    await self._message_handler(chat_message)
                except Exception:
                    logger.exception("Error handling message")
                    await message.channel.send("❌ An error occurred processing your message.")

        @client.event  # type: ignore[untyped-decorator]
        async def on_disconnect() -> None:
            """Handle disconnect event."""
            self._is_connected = False
            logger.warning("Discord bot disconnected")

        @client.event  # type: ignore[untyped-decorator]
        async def on_resumed() -> None:
            """Handle resume event."""
            self._is_connected = True
            logger.info("Discord bot reconnected")

    @property
    def platform(self) -> ChatPlatform:
        """Return the platform type.

        Returns:
            ChatPlatform.DISCORD
        """
        return ChatPlatform.DISCORD

    @property
    def is_connected(self) -> bool:
        """Check if the bot is connected.

        Returns:
            True if connected, False otherwise.
        """
        return self._is_connected

    async def start(self) -> None:
        """Start the Discord bot.

        Returns:
            None
        """
        logger.info("Starting Discord bot...")
        await self._client.start(self._token)

    async def stop(self) -> None:
        """Stop the Discord bot.

        Returns:
            None
        """
        logger.info("Stopping Discord bot...")
        await self._client.close()
        self._is_connected = False

    async def send_message(
        self,
        user_id: str,
        content: str,
        *,
        split_long: bool = True,
    ) -> None:
        """Send a message to a user via Discord DM.

        Args:
            user_id: Discord user ID (snowflake).
            content: Message content to send.
            split_long: Whether to split messages exceeding 2000 characters.

        Returns:
            None
        """
        try:
            # Get user object
            user = await self._client.fetch_user(int(user_id))
            if not user:
                logger.error("Could not find user with ID %s", user_id)
                return

            if not split_long or len(content) <= DISCORD_MESSAGE_LIMIT:
                await user.send(content)
                return

            # Split long messages intelligently
            chunks = self._split_message(content, DISCORD_MESSAGE_LIMIT)
            for chunk in chunks:
                await user.send(chunk)

        except Exception:
            logger.exception("Failed to send Discord message")

    async def send_typing(self, user_id: str) -> None:
        """Send a typing indicator to a user's DM channel.

        Args:
            user_id: Discord user ID.

        Returns:
            None
        """
        try:
            user = await self._client.fetch_user(int(user_id))
            if user:
                async with user.typing():
                    pass  # Just trigger the indicator
        except Exception:
            logger.exception("Failed to send typing indicator")

    def set_message_handler(
        self,
        handler: Callable[[ChatMessage], Coroutine[Any, Any, None]],
    ) -> None:
        """Set the handler for incoming messages.

        Args:
            handler: Async callable that processes incoming ChatMessages.

        Returns:
            None
        """
        self._message_handler = handler

    @staticmethod
    def _split_message(content: str, limit: int) -> list[str]:
        """Split a message into chunks respecting line breaks.

        Args:
            content: Message content to split.
            limit: Maximum characters per chunk.

        Returns:
            List of message chunks.
        """
        if len(content) <= limit:
            return [content]

        chunks: list[str] = []
        current_chunk = ""

        for line in content.split("\n"):
            # If adding this line would exceed limit
            if len(current_chunk) + len(line) + 1 > limit:
                if current_chunk:
                    chunks.append(current_chunk)
                # If single line exceeds limit, split it
                if len(line) > limit:
                    while len(line) > limit:
                        chunks.append(line[:limit])
                        line = line[limit:]
                    current_chunk = line
                else:
                    current_chunk = line
            else:
                if current_chunk:
                    current_chunk += "\n" + line
                else:
                    current_chunk = line

        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    @property
    def client(self) -> Any:
        """Get the underlying Discord client.

        Returns:
            discord.Client instance.
        """
        return self._client
