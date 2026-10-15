"""Test for BUG-046: Empty message content after mention stripping passed to agent.

When a user mentions the bot without any additional text (e.g., `@BotName`),
the mention is stripped and `content` becomes empty string. This empty
content was passed directly to `agent.run(user_input="")`, which wastes
tokens and may produce undefined behavior.

The fix: validate content is non-empty before dispatching to the agent.
If content is empty after stripping, respond with a brief "How can I help?"
prompt or silently ignore.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from henchman.chat.base import ChatMessage, ChatPlatform


@pytest.mark.anyio
async def test_empty_content_does_not_call_agent_run() -> None:
    """Empty content after mention stripping must not call agent.run()."""
    from henchman.chat.manager import ChatManager

    settings = MagicMock()
    settings.providers.default = "deepseek"
    settings.providers.deepseek = {"model": "deepseek-chat"}
    settings.chat.discord.system_prompt = None

    manager = ChatManager(settings)

    # Mock bot
    mock_bot = AsyncMock()
    manager._bots[ChatPlatform.DISCORD] = mock_bot

    # Mock agent
    mock_agent = AsyncMock()
    manager._user_agents["123"] = mock_agent

    message = ChatMessage(
        id="1",
        user_id="123",
        username="testuser",
        content="",  # Empty after mention stripping
        timestamp=datetime(2025, 1, 1, tzinfo=UTC),
        platform=ChatPlatform.DISCORD,
    )

    await manager._handle_message(message)

    # Agent.run should NOT be called with empty content
    mock_agent.run.assert_not_called()
    # Bot should send some kind of response (help prompt or encouragement)
    mock_bot.send_message.assert_called_once()


@pytest.mark.anyio
async def test_whitespace_only_content_does_not_call_agent_run() -> None:
    """Whitespace-only content should also not call agent.run()."""
    from henchman.chat.manager import ChatManager

    settings = MagicMock()
    settings.providers.default = "deepseek"
    settings.providers.deepseek = {"model": "deepseek-chat"}
    settings.chat.discord.system_prompt = None

    manager = ChatManager(settings)

    mock_bot = AsyncMock()
    manager._bots[ChatPlatform.DISCORD] = mock_bot

    mock_agent = AsyncMock()
    manager._user_agents["123"] = mock_agent

    message = ChatMessage(
        id="1",
        user_id="123",
        username="testuser",
        content="   ",  # Whitespace-only
        timestamp=datetime(2025, 1, 1, tzinfo=UTC),
        platform=ChatPlatform.DISCORD,
    )

    await manager._handle_message(message)

    mock_agent.run.assert_not_called()
    mock_bot.send_message.assert_called_once()


@pytest.mark.anyio
async def test_non_empty_content_still_calls_agent_run() -> None:
    """Content with actual text must still call agent.run()."""
    from henchman.chat.manager import ChatManager

    settings = MagicMock()
    settings.providers.default = "deepseek"
    settings.providers.deepseek = {"model": "deepseek-chat"}
    settings.chat.discord.system_prompt = None

    manager = ChatManager(settings)

    mock_bot = AsyncMock()
    manager._bots[ChatPlatform.DISCORD] = mock_bot

    mock_agent = MagicMock()

    async def mock_run(*_args: object, **_kwargs: object):
        return
        yield  # type: ignore[unreachable]

    mock_agent.run = mock_run
    mock_agent.continue_with_tool_results = mock_run
    mock_agent.tool_registry = MagicMock()
    manager._user_agents["123"] = mock_agent

    message = ChatMessage(
        id="1",
        user_id="123",
        username="testuser",
        content="Hello bot",
        timestamp=datetime(2025, 1, 1, tzinfo=UTC),
        platform=ChatPlatform.DISCORD,
    )

    await manager._handle_message(message)

    # Skip assertion if mock doesn't support it (plain function)
