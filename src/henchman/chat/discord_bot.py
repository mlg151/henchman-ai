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
    def _split_message(content: str, limit: int = 2000) -> list[str]:
        """Split a message into chunks respecting line breaks and code blocks."""
        if len(content) <= limit:
            return [content]

        chunks = []
        current_chunk = ""
        code_block_lang: str | None = None

        lines = content.split('\n')
        
        for i, line in enumerate(lines):
            # Check for code block markers
            stripped = line.strip()
            # Check if line toggles code block
            is_code_block_toggle = stripped.startswith("```")
            
            # Determine state change
            next_lang = code_block_lang
            if is_code_block_toggle:
                if code_block_lang is not None:
                    if stripped == "```":
                        next_lang = None
                else:
                    if len(stripped) > 3:
                        next_lang = stripped[3:].strip()
                    else:
                        next_lang = ""

            # Calculate overhead
            # We need to close the current block if we split: "\n```"
            close_overhead = 4 if code_block_lang is not None else 0
            
            # We need to open the next block if we split: "```{lang}\n"
            open_overhead = 0
            if code_block_lang is not None:
                open_overhead = len(f"```{code_block_lang}\n")

            # Check if line fits
            prefix = "\n" if current_chunk else ""
            
            # If we add this line, we must ensure we still have room to close the block if needed
            # So the check is: current + prefix + line + close_overhead <= limit
            if len(current_chunk) + len(prefix) + len(line) + close_overhead > limit:
                # Must split
                if code_block_lang is not None:
                    # Close current block
                    current_chunk += "\n```"
                
                if current_chunk:
                    chunks.append(current_chunk)
                
                # Start new chunk
                if code_block_lang is not None:
                    current_chunk = f"```{code_block_lang}\n{line}"
                else:
                    current_chunk = line
                
                # Handle case where line itself is too long for the new chunk
                # Recalculate reserve for the *end* of this new line (needs closing)
                while len(current_chunk) + close_overhead > limit:
                    # We need to hard-split the line
                    # Max allowed content in this chunk
                    allowed_len = limit - close_overhead
                    
                    if len(current_chunk) > allowed_len:
                        # Take what fits
                        part = current_chunk[:allowed_len]
                        remainder = current_chunk[allowed_len:]
                        
                        # Close this part
                        if code_block_lang is not None:
                            part += "\n```"
                        
                        chunks.append(part)
                        
                        # Start next part
                        if code_block_lang is not None:
                            current_chunk = f"```{code_block_lang}\n{remainder}"
                        else:
                            current_chunk = remainder
                    else:
                        break
            else:
                current_chunk += prefix + line

            code_block_lang = next_lang

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
