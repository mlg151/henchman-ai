"""Test for BUG-042: Silent message send failures produce incomplete responses.

send_message's exceptions were swallowed silently, so callers assumed
success. The fix makes send_message return bool and updates callers to
only accumulate response_parts on successful delivery.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from henchman.chat.base import ChatMessage, ChatPlatform


@patch("henchman.chat.discord_bot._check_discord_installed")
@pytest.mark.anyio
async def test_send_message_returns_false_on_failure(_mock_check: Any) -> None:
    """send_message must return False when Discord API call fails."""

    fake_user = AsyncMock()
    fake_user.send = AsyncMock(side_effect=Exception("Discord API error"))

    fake_client = MagicMock()
    fake_client.Intents.default.return_value = MagicMock()
    fake_client.fetch_user = AsyncMock(return_value=fake_user)

    # Need to create an actual Client mock for the DiscordBot to work with
    client_instance = MagicMock()
    client_instance.fetch_user = AsyncMock(return_value=fake_user)
    fake_client.Client.return_value = client_instance

    with patch.dict("sys.modules", {"discord": fake_client}):
        from henchman.chat.discord_bot import DiscordBot

        bot = DiscordBot(token="fake-token", allowed_user_id="123")

        result = await bot.send_message("456", "Hello")

        assert result is False, "send_message should return False on failure"


@patch("henchman.chat.discord_bot._check_discord_installed")
@pytest.mark.anyio
async def test_send_message_returns_true_on_success(_mock_check: Any) -> None:
    """send_message must return True when Discord API call succeeds."""
    fake_user = AsyncMock()
    fake_user.send = AsyncMock()

    fake_client = MagicMock()
    fake_client.Intents.default.return_value = MagicMock()
    client_instance = MagicMock()
    client_instance.fetch_user = AsyncMock(return_value=fake_user)
    fake_client.Client.return_value = client_instance

    with patch.dict("sys.modules", {"discord": fake_client}):
        from henchman.chat.discord_bot import DiscordBot

        bot = DiscordBot(token="fake-token", allowed_user_id="123")

        result = await bot.send_message("456", "Hello")

        assert result is True, "send_message should return True on success"


@pytest.mark.anyio
async def test_failed_content_flush_not_appended_to_response_parts() -> None:
    """Failed content flushes must not be added to response_parts."""
    from henchman.chat.manager import ChatManager
    from henchman.core.events import AgentEvent, EventType

    settings = MagicMock()
    settings.providers.default = "deepseek"
    settings.providers.deepseek = {"model": "deepseek-chat"}
    settings.chat.discord.system_prompt = None

    manager = ChatManager(settings)

    # Bot that fails on send_message
    mock_bot = AsyncMock()
    mock_bot.send_message.return_value = False  # Simulate failure
    manager._bots[ChatPlatform.DISCORD] = mock_bot

    mock_agent = MagicMock()
    mock_agent.tool_registry = MagicMock()
    mock_agent.submit_tool_result = MagicMock()

    # Create a stream with a content event followed by FINISHED
    async def mock_stream():
        yield AgentEvent(type=EventType.CONTENT, data="Hello this is content", source_agent=None)
        yield AgentEvent(type=EventType.FINISHED, data=None, source_agent=None)

    mock_agent.run = MagicMock(return_value=mock_stream())
    mock_agent.continue_with_tool_results = MagicMock(
        return_value=AsyncMock(__aiter__=MagicMock(return_value=AsyncMock(__anext__=MagicMock(side_effect=StopAsyncIteration))))
    )

    manager._user_agents["123"] = mock_agent

    message = ChatMessage(
        id="1",
        user_id="123",
        username="testuser",
        content="Hi",
        timestamp=datetime(2025, 1, 1, tzinfo=UTC),
        platform=ChatPlatform.DISCORD,
    )

    await manager._handle_message(message)

    # Verify response_parts is empty (failed message should not be tracked as delivered)
    # We can check by seeing that _user_histories does NOT contain the failed content
    hist = manager._user_histories.get("123", [])
    # The failed content should not be in history
    for entry in hist:
        if isinstance(entry, dict) and entry.get("role") == "assistant":
            assert "Hello this is content" not in entry.get("content", ""), (
                "Failed content should not appear in response history"
            )
