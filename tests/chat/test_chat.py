"""Comprehensive tests for henchman.chat module.

Covers base abstractions, Discord bot (with mocks), chat manager, and CLI command.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from henchman.chat.base import ChatBot, ChatMessage, ChatPlatform


# ---------------------------------------------------------------------------
# Tests for ChatMessage
# ---------------------------------------------------------------------------


class TestChatMessage:
    """Tests for ChatMessage dataclass."""

    def test_create_basic_message(self) -> None:
        """Test creating a basic chat message."""
        msg = ChatMessage(
            id="123",
            user_id="456",
            username="testuser",
            content="Hello, Henchman!",
            timestamp=datetime.now(timezone.utc),
            platform=ChatPlatform.DISCORD,
        )
        assert msg.id == "123"
        assert msg.user_id == "456"
        assert msg.username == "testuser"
        assert msg.content == "Hello, Henchman!"
        assert msg.platform == ChatPlatform.DISCORD
        assert msg.is_dm is True
        assert msg.attachments == []

    def test_message_with_attachments(self) -> None:
        """Test message with attachments."""
        msg = ChatMessage(
            id="789",
            user_id="456",
            username="testuser",
            content="Check this file",
            timestamp=datetime.now(timezone.utc),
            platform=ChatPlatform.DISCORD,
            attachments=[{"filename": "test.py", "url": "https://example.com/test.py"}],
        )
        assert len(msg.attachments) == 1
        assert msg.attachments[0]["filename"] == "test.py"

    def test_message_not_dm(self) -> None:
        """Test message in a server channel."""
        msg = ChatMessage(
            id="100",
            user_id="456",
            username="testuser",
            content="Hello in channel",
            timestamp=datetime.now(timezone.utc),
            platform=ChatPlatform.DISCORD,
            is_dm=False,
        )
        assert msg.is_dm is False


# ---------------------------------------------------------------------------
# Tests for ChatPlatform
# ---------------------------------------------------------------------------


class TestChatPlatform:
    """Tests for ChatPlatform enum."""

    def test_platform_values(self) -> None:
        """Test platform enum values."""
        assert ChatPlatform.DISCORD.value == "discord"
        assert ChatPlatform.TELEGRAM.value == "telegram"
        assert ChatPlatform.SLACK.value == "slack"

    def test_platform_from_string(self) -> None:
        """Test creating platform from string."""
        assert ChatPlatform("discord") == ChatPlatform.DISCORD
        assert ChatPlatform("telegram") == ChatPlatform.TELEGRAM


# ---------------------------------------------------------------------------
# Tests for DiscordBot (mocked)
# ---------------------------------------------------------------------------


class TestDiscordBot:
    """Tests for DiscordBot with mocked discord.py."""

    def test_split_message_short(self) -> None:
        """Test splitting a short message."""
        from henchman.chat.discord_bot import DiscordBot

        content = "Short message"
        chunks = DiscordBot._split_message(content, 2000)
        assert chunks == ["Short message"]

    def test_split_message_long(self) -> None:
        """Test splitting a long message."""
        from henchman.chat.discord_bot import DiscordBot

        # Create a message longer than 2000 chars
        lines = [f"Line {i}: {'x' * 100}" for i in range(30)]
        content = "\n".join(lines)
        chunks = DiscordBot._split_message(content, 2000)

        # Should be split into multiple chunks
        assert len(chunks) > 1
        # Each chunk should be <= 2000 chars
        for chunk in chunks:
            assert len(chunk) <= 2000

    def test_split_message_single_long_line(self) -> None:
        """Test splitting a single line that exceeds limit."""
        from henchman.chat.discord_bot import DiscordBot

        content = "x" * 5000
        chunks = DiscordBot._split_message(content, 2000)
        assert len(chunks) >= 3
        for chunk in chunks:
            assert len(chunk) <= 2000

    def test_split_message_with_newlines(self) -> None:
        """Test splitting preserves line boundaries."""
        from henchman.chat.discord_bot import DiscordBot

        content = "Line 1\nLine 2\nLine 3"
        chunks = DiscordBot._split_message(content, 100)
        assert chunks == ["Line 1\nLine 2\nLine 3"]

    @patch("henchman.chat.discord_bot._check_discord_installed")
    def test_platform_property(self, mock_check: MagicMock) -> None:
        """Test platform property returns DISCORD."""
        mock_discord = MagicMock()
        mock_discord.Intents.default.return_value = MagicMock()
        mock_discord.Client.return_value = MagicMock()
        with patch.dict("sys.modules", {"discord": mock_discord}):
            from henchman.chat.discord_bot import DiscordBot

            bot = DiscordBot(token="fake-token", allowed_user_id="123456")
            assert bot.platform == ChatPlatform.DISCORD

    @patch("henchman.chat.discord_bot._check_discord_installed")
    def test_is_connected_initially_false(self, mock_check: MagicMock) -> None:
        """Test is_connected is False initially."""
        mock_discord = MagicMock()
        mock_discord.Intents.default.return_value = MagicMock()
        mock_discord.Client.return_value = MagicMock()
        with patch.dict("sys.modules", {"discord": mock_discord}):
            from henchman.chat.discord_bot import DiscordBot

            bot = DiscordBot(token="fake-token", allowed_user_id="123456")
            assert bot.is_connected is False

    @patch("henchman.chat.discord_bot._check_discord_installed")
    def test_set_message_handler(self, mock_check: MagicMock) -> None:
        """Test setting message handler."""
        mock_discord = MagicMock()
        mock_discord.Intents.default.return_value = MagicMock()
        mock_discord.Client.return_value = MagicMock()
        with patch.dict("sys.modules", {"discord": mock_discord}):
            from henchman.chat.discord_bot import DiscordBot

            bot = DiscordBot(token="fake-token", allowed_user_id="123456")

            async def handler(msg: ChatMessage) -> None:
                pass

            bot.set_message_handler(handler)
            assert bot._message_handler is handler


class TestDiscordBotImportError:
    """Test Discord bot behavior when discord.py is not installed."""

    def test_check_discord_installed_raises(self) -> None:
        """Test that missing discord.py raises ImportError."""
        from henchman.chat.discord_bot import _check_discord_installed

        with patch.dict("sys.modules", {"discord": None}):
            with pytest.raises(ImportError, match="discord.py is required"):
                _check_discord_installed()


# ---------------------------------------------------------------------------
# Tests for ChatManager
# ---------------------------------------------------------------------------


class TestChatManager:
    """Tests for ChatManager."""

    @pytest.fixture
    def mock_settings(self) -> MagicMock:
        """Create mock settings."""
        settings = MagicMock()
        settings.providers.default = "deepseek"
        settings.providers.deepseek = {"model": "deepseek-chat"}
        settings.chat.discord.system_prompt = None
        return settings

    def test_create_manager(self, mock_settings: MagicMock) -> None:
        """Test creating a chat manager."""
        from henchman.chat.manager import ChatManager

        manager = ChatManager(mock_settings)
        assert manager.bots == {}
        assert manager.active_users == []

    def test_get_provider_settings(self, mock_settings: MagicMock) -> None:
        """Test getting provider settings."""
        from henchman.chat.manager import ChatManager

        manager = ChatManager(mock_settings)
        settings = manager._get_provider_settings("deepseek")
        assert settings == {"model": "deepseek-chat"}

    def test_get_provider_settings_unknown(self, mock_settings: MagicMock) -> None:
        """Test getting settings for unknown provider."""
        from henchman.chat.manager import ChatManager

        manager = ChatManager(mock_settings)
        settings = manager._get_provider_settings("unknown_provider")
        assert settings == {}

    def test_get_provider_settings_missing_attr(self, mock_settings: MagicMock) -> None:
        """Test getting settings for valid provider but missing settings attribute.
        
        This test demonstrates the bug fix: when a provider is in the map but the
        settings attribute doesn't exist, the method now returns reasonable defaults
        instead of an empty dict {}.
        """
        from henchman.chat.manager import ChatManager

        manager = ChatManager(mock_settings)
        
        # Mock settings to have no 'anthropic' attribute
        # Remove the anthropic attribute from mock
        delattr(mock_settings.providers, 'anthropic')
        
        # Mock get_api_key_for_provider to return None (no API key in env)
        with patch('henchman.chat.manager.get_api_key_for_provider', return_value=None):
            # Now test getting settings for 'anthropic' which is a valid provider name
            # but doesn't have settings configured
            settings = manager._get_provider_settings("anthropic")
            
            # The fix: this now returns defaults instead of empty dict
            # Should include at least a model default
            assert "model" in settings
            assert settings["model"] == "claude-3-5-sonnet-20241022"

    @pytest.mark.anyio
    async def test_get_or_create_agent_with_missing_provider_settings(self, mock_settings: MagicMock) -> None:
        """Test that creating an agent works when provider settings are missing.
        
        This demonstrates the bug fix: if a provider is configured as default
        but its settings are missing, agent creation now works because
        _get_provider_settings returns reasonable defaults instead of {}.
        """
        from henchman.chat.manager import ChatManager
        from henchman.providers import get_default_registry

        manager = ChatManager(mock_settings)
        
        # Set default provider to 'anthropic' but don't configure anthropic settings
        mock_settings.providers.default = "anthropic"
        # Ensure anthropic attribute doesn't exist or returns None
        if hasattr(mock_settings.providers, 'anthropic'):
            delattr(mock_settings.providers, 'anthropic')
        
        # Mock the registry to capture what parameters are passed
        mock_registry = MagicMock()
        mock_provider = MagicMock()
        mock_registry.create.return_value = mock_provider
        
        with patch('henchman.chat.manager.get_default_registry', return_value=mock_registry):
            # Mock get_api_key_for_provider to return None (no API key in env)
            with patch('henchman.chat.manager.get_api_key_for_provider', return_value=None):
                # This should now work with default kwargs
                agent = await manager._get_or_create_agent("test_user")
                
                # Check what was passed to registry.create
                mock_registry.create.assert_called_once()
                call_args = mock_registry.create.call_args
                assert call_args[0][0] == "anthropic"  # provider name
                # The fix: kwargs should contain defaults, not be empty
                assert call_args[1] != {}  # Should not be empty!
                assert "model" in call_args[1]  # Should have model default

    @patch("henchman.chat.discord_bot._check_discord_installed")
    def test_create_discord_bot(
        self, mock_check: MagicMock, mock_settings: MagicMock
    ) -> None:
        """Test creating a Discord bot."""
        mock_discord = MagicMock()
        mock_discord.Intents.default.return_value = MagicMock()
        mock_discord.Client.return_value = MagicMock()
        with patch.dict("sys.modules", {"discord": mock_discord}):
            from henchman.chat.manager import ChatManager

            manager = ChatManager(mock_settings)
            bot = manager.create_discord_bot(
                token="fake-token",
                allowed_user_id="123456",
            )
            assert bot is not None
            assert ChatPlatform.DISCORD in manager.bots

    @pytest.mark.anyio
    async def test_handle_command_help(self, mock_settings: MagicMock) -> None:
        """Test /help command handler."""
        from henchman.chat.manager import ChatManager

        manager = ChatManager(mock_settings)

        # Mock bot
        mock_bot = AsyncMock()
        manager._bots[ChatPlatform.DISCORD] = mock_bot

        message = ChatMessage(
            id="1",
            user_id="123",
            username="testuser",
            content="/help",
            timestamp=datetime.now(timezone.utc),
            platform=ChatPlatform.DISCORD,
        )

        await manager._handle_command(message)
        mock_bot.send_message.assert_called_once()
        call_args = mock_bot.send_message.call_args
        assert "Henchman-AI Commands" in call_args[0][1]

    @pytest.mark.anyio
    async def test_handle_command_clear(self, mock_settings: MagicMock) -> None:
        """Test /clear command handler."""
        from henchman.chat.manager import ChatManager

        manager = ChatManager(mock_settings)

        # Add some history
        manager._user_histories["123"] = [{"role": "user", "content": "hi"}]

        # Mock bot
        mock_bot = AsyncMock()
        manager._bots[ChatPlatform.DISCORD] = mock_bot

        message = ChatMessage(
            id="1",
            user_id="123",
            username="testuser",
            content="/clear",
            timestamp=datetime.now(timezone.utc),
            platform=ChatPlatform.DISCORD,
        )

        await manager._handle_command(message)
        assert manager._user_histories["123"] == []
        mock_bot.send_message.assert_called_once()

    @pytest.mark.anyio
    async def test_handle_command_status(self, mock_settings: MagicMock) -> None:
        """Test /status command handler."""
        from henchman.chat.manager import ChatManager

        manager = ChatManager(mock_settings)

        # Mock bot
        mock_bot = AsyncMock()
        manager._bots[ChatPlatform.DISCORD] = mock_bot

        message = ChatMessage(
            id="1",
            user_id="123",
            username="testuser",
            content="/status",
            timestamp=datetime.now(timezone.utc),
            platform=ChatPlatform.DISCORD,
        )

        await manager._handle_command(message)
        call_args = mock_bot.send_message.call_args
        assert "Henchman-AI Status" in call_args[0][1]
        assert "deepseek" in call_args[0][1]

    @pytest.mark.anyio
    async def test_handle_command_unknown(self, mock_settings: MagicMock) -> None:
        """Test unknown command handler."""
        from henchman.chat.manager import ChatManager

        manager = ChatManager(mock_settings)

        # Mock bot
        mock_bot = AsyncMock()
        manager._bots[ChatPlatform.DISCORD] = mock_bot

        message = ChatMessage(
            id="1",
            user_id="123",
            username="testuser",
            content="/unknown",
            timestamp=datetime.now(timezone.utc),
            platform=ChatPlatform.DISCORD,
        )

        await manager._handle_command(message)
        call_args = mock_bot.send_message.call_args
        assert "Unknown command" in call_args[0][1]

    @pytest.mark.anyio
    async def test_handle_command_history_empty(self, mock_settings: MagicMock) -> None:
        """Test /history command with no history."""
        from henchman.chat.manager import ChatManager

        manager = ChatManager(mock_settings)

        # Mock bot
        mock_bot = AsyncMock()
        manager._bots[ChatPlatform.DISCORD] = mock_bot

        message = ChatMessage(
            id="1",
            user_id="123",
            username="testuser",
            content="/history",
            timestamp=datetime.now(timezone.utc),
            platform=ChatPlatform.DISCORD,
        )

        await manager._handle_command(message)
        call_args = mock_bot.send_message.call_args
        assert "No conversation history" in call_args[0][1]

    @pytest.mark.anyio
    async def test_handle_command_history_with_data(self, mock_settings: MagicMock) -> None:
        """Test /history command with existing history."""
        from henchman.chat.manager import ChatManager

        manager = ChatManager(mock_settings)
        manager._user_histories["123"] = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]

        # Mock bot
        mock_bot = AsyncMock()
        manager._bots[ChatPlatform.DISCORD] = mock_bot

        message = ChatMessage(
            id="1",
            user_id="123",
            username="testuser",
            content="/history",
            timestamp=datetime.now(timezone.utc),
            platform=ChatPlatform.DISCORD,
        )

        await manager._handle_command(message)
        call_args = mock_bot.send_message.call_args
        assert "Recent Conversation" in call_args[0][1]

    @pytest.mark.anyio
    async def test_handle_message_no_bot(self, mock_settings: MagicMock) -> None:
        """Test handling message when no bot is registered."""
        from henchman.chat.manager import ChatManager

        manager = ChatManager(mock_settings)

        message = ChatMessage(
            id="1",
            user_id="123",
            username="testuser",
            content="Hello",
            timestamp=datetime.now(timezone.utc),
            platform=ChatPlatform.DISCORD,
        )

        # Should not raise, just log error
        await manager._handle_message(message)

    @pytest.mark.anyio
    async def test_stop_all(self, mock_settings: MagicMock) -> None:
        """Test stopping all bots."""
        from henchman.chat.manager import ChatManager

        manager = ChatManager(mock_settings)

        # Create mock bot
        mock_bot = AsyncMock()
        mock_bot.is_connected = True
        mock_bot.platform = ChatPlatform.DISCORD
        manager._bots[ChatPlatform.DISCORD] = mock_bot

        await manager.stop_all()
        mock_bot.stop.assert_called_once()
