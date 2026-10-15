"""Test for BUG-044: Typing indicator never refreshed during long-running processing.

Discord's typing indicator expires after ~10 seconds. The bot sends it once
at the start but never refreshes it during long agent processing.

The fix: periodically refresh the typing indicator (every ~8 seconds) via a
background task during the processing loop.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from henchman.chat.base import ChatMessage, ChatPlatform


@pytest.mark.anyio
async def test_send_typing_called_periodically_during_long_processing() -> None:
    """Typing indicator must be refreshed periodically during long processing."""
    from henchman.chat.manager import ChatManager

    settings = MagicMock()
    settings.providers.default = "deepseek"
    settings.providers.deepseek = {"model": "deepseek-chat"}
    settings.chat.discord.system_prompt = None

    manager = ChatManager(settings)

    # Patch the typing refresh interval to 1 second so it fires within the
    # 2-second mock agent processing window.
    import henchman.chat.manager as mgr
    mgr.TYPING_REFRESH_INTERVAL = 1

    mock_bot = AsyncMock()
    # send_typing succeeds
    mock_bot.send_typing = AsyncMock()
    mock_bot.send_message = AsyncMock()
    manager._bots[ChatPlatform.DISCORD] = mock_bot

    # Create an agent mock that yields FINISHED after a delay
    mock_agent = MagicMock()
    mock_agent.tool_registry = MagicMock()

    from henchman.core.events import AgentEvent, EventType

    async def slow_stream():
        import asyncio
        # Simulate processing that takes 2 seconds
        await asyncio.sleep(2)
        yield AgentEvent(type=EventType.CONTENT, data="Done processing", source_agent=None)
        yield AgentEvent(type=EventType.FINISHED, data=None, source_agent=None)

    mock_agent.run = MagicMock(return_value=slow_stream())
    mock_agent.continue_with_tool_results = MagicMock(
        return_value=AsyncMock(
            __aiter__=MagicMock(
                return_value=AsyncMock(__anext__=MagicMock(side_effect=StopAsyncIteration))
            )
        )
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

    # send_typing should have been called multiple times (initial + refreshes)
    assert mock_bot.send_typing.call_count >= 2, (
        f"Expected multiple send_typing calls (initial + refreshes), "
        f"got {mock_bot.send_typing.call_count}"
    )


