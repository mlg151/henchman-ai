"""Comprehensive tests for henchman.chat module.

Covers base abstractions, Discord bot (with mocks), chat manager, and CLI command.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from henchman.chat.base import ChatMessage, ChatPlatform

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
            timestamp=datetime.now(UTC),
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
            timestamp=datetime.now(UTC),
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
            timestamp=datetime.now(UTC),
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

        with (
            patch.dict("sys.modules", {"discord": None}),
            pytest.raises(ImportError, match="discord.py is required"),
        ):
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
    async def test_get_or_create_agent_with_missing_provider_settings(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """An unconfigured provider section uses its defaults and selected environment key."""
        from henchman.chat.manager import ChatManager
        from henchman.config.schema import ProviderSettings, Settings

        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")
        monkeypatch.setattr("henchman.cli.tool_manager.ToolManager.register_builtin_tools", lambda _self: None)
        manager = ChatManager(Settings(providers=ProviderSettings(default="anthropic")))
        agent = await manager._get_or_create_agent("test_user")
        assert agent.provider.name == "anthropic"
        assert agent.provider.api_key == "test-anthropic-key"
        assert agent.model == agent.provider.default_model

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
            timestamp=datetime.now(UTC),
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
            timestamp=datetime.now(UTC),
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
            timestamp=datetime.now(UTC),
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
            timestamp=datetime.now(UTC),
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
            timestamp=datetime.now(UTC),
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
            timestamp=datetime.now(UTC),
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
            timestamp=datetime.now(UTC),
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

    def test_get_provider_settings_string_instead_of_dict(self, mock_settings: MagicMock) -> None:
        """Test that _get_provider_settings handles string provider settings gracefully.

        This tests the bug fix: if provider settings in configuration is a string
        (e.g., "deepseek-chat") instead of a dict, the method should handle it
        gracefully instead of raising TypeError.
        """
        import henchman.chat.manager as chat_manager_module
        from henchman.chat.manager import ChatManager

        manager = ChatManager(mock_settings)

        # Mock provider settings to return a string instead of dict
        # This simulates misconfigured YAML: providers.deepseek: "deepseek-chat"
        mock_settings.providers.deepseek = "deepseek-chat"  # String, not dict!

        # Mock logger to capture warning
        mock_logger = MagicMock()
        with patch.object(chat_manager_module, 'logger', mock_logger):
            # This should NOT raise ValueError/TypeError
            # With the bug, dict("deepseek-chat") raises ValueError
            # With the fix, it should log warning and return defaults
            settings = manager._get_provider_settings("deepseek")

            # Should log warning about non-dict settings (only once, not duplicate)
            # Check that warning was called at least once with the right message
            mock_logger.warning.assert_called()
            # Find the call about non-dict settings
            non_dict_warning_called = False
            for call in mock_logger.warning.call_args_list:
                args = call[0]
                if len(args) > 0 and "not a dictionary" in args[0]:
                    non_dict_warning_called = True
                    # Check that provider name is in args (should be second arg)
                    if len(args) > 1:
                        assert args[1] == "deepseek"
                    break
            assert non_dict_warning_called, "Should have logged warning about non-dict settings"

            # Should return defaults (not empty dict)
            assert settings is not None
            # Should include model default for deepseek
            assert "model" in settings
            assert settings["model"] == "deepseek-chat"

    @pytest.mark.anyio
    async def test_tool_error_send_message_failure(self, mock_settings: MagicMock) -> None:
        """Test that agent still receives tool result when error message send fails.

        This tests the bug: when a tool execution fails and sending the error
        message to the user also fails, the agent should still receive the
        tool result via submit_tool_result().
        """
        from henchman.chat.manager import ChatManager
        from henchman.core.events import AgentEvent, EventType

        manager = ChatManager(mock_settings)

        # Create mock agent
        mock_agent = MagicMock()
        mock_agent.tool_registry.execute.side_effect = Exception("Tool execution failed")

        # Create mock bot that succeeds for first message but fails for error message
        mock_bot = AsyncMock()
        # First call succeeds (sending "🔧 Running: `test_tool`")
        # Second call fails (sending error message)
        mock_bot.send_message.side_effect = [None, Exception("Failed to send error message")]

        # Create a mock tool call event
        mock_tool_call = MagicMock()
        mock_tool_call.name = "test_tool"
        mock_tool_call.arguments = {}
        mock_tool_call.id = "tool_123"

        # Create mock stream with a TOOL_CALL_REQUEST event
        async def mock_stream():
            yield AgentEvent(type=EventType.TOOL_CALL_REQUEST, data=mock_tool_call, source_agent=None)

        # Call _process_stream
        response_parts = []
        current_chunk = ""

        # This should not raise an exception (error should be caught)
        await manager._process_stream(
            agent=mock_agent,
            bot=mock_bot,
            user_id="test_user",
            stream=mock_stream(),
            response_parts=response_parts,
            current_chunk=current_chunk,
        )

        # Check that bot.send_message was called twice
        assert mock_bot.send_message.call_count == 2

        # THE BUG: agent.submit_tool_result should still be called even though
        # the second bot.send_message failed. But with the current code, it won't be.
        # This assertion will FAIL with the buggy code:
        mock_agent.submit_tool_result.assert_called_once_with("tool_123", "Error: Tool execution failed")
