"""Test for BUG-047: Group DM messages misclassified as guild messages.

In discord.py, group DM messages have channel type `discord.GroupChannel`,
not `discord.DMChannel`. The `on_message` handler at line 116 only checked
`isinstance(message.channel, discord.DMChannel)`, so group DMs were treated
as guild messages and rejected by the channel allowlist.

The fix: check `message.guild is None` to detect ALL non-guild channel types
(both DMChannel and GroupChannel).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest


class _FakeDMChannel:
    """Fake Discord DM channel — used for isinstance checks."""


class _FakeGroupChannel:
    """Fake Discord GroupChannel — also a DM-like channel but not DMChannel."""


@dataclass
class _FakeClient:
    """Small fake Discord client that records registered event handlers."""

    user: Any = field(default_factory=lambda: SimpleNamespace(id=999, name="Henchman"))
    events: dict[str, Any] = field(default_factory=dict)

    def event(self, func: Any) -> Any:
        """Register an event callback just like discord.Client.event."""
        self.events[func.__name__] = func
        return func


def _make_discord_module(fake_client: _FakeClient) -> Any:
    """Create a lightweight fake `discord` module."""

    class _FakeIntents:
        @staticmethod
        def default() -> Any:
            return SimpleNamespace(message_content=False, dm_messages=False)

    def _client_factory(*, intents: Any) -> Any:
        _ = intents
        return fake_client

    return SimpleNamespace(
        Intents=_FakeIntents,
        Client=_client_factory,
        DMChannel=_FakeDMChannel,
        GroupChannel=_FakeGroupChannel,
    )


@patch("henchman.chat.discord_bot._check_discord_installed")
@pytest.mark.anyio
async def test_group_dm_message_accepted_as_dm(_mock_check: Any) -> None:
    """Group DM messages must be treated as DMs (not guild messages).

    A GroupChannel has message.guild = None, just like DMChannel.
    The fix checks message.guild is None rather than isinstance(DMChannel).
    """
    fake_client = _FakeClient()
    fake_discord = _make_discord_module(fake_client)

    with patch.dict("sys.modules", {"discord": fake_discord}):
        from henchman.chat.discord_bot import DiscordBot

        bot = DiscordBot(
            token="fake-token",
            allowed_user_id="123",
        )
        handler = AsyncMock()
        bot.set_message_handler(handler)

        # Simulate a GroupChannel: guild is None, channel is GroupChannel-like
        message = SimpleNamespace(
            id=1,
            author=SimpleNamespace(id=123, name="Test", display_name="Test User"),
            channel=SimpleNamespace(id=789),
            mentions=[fake_client.user],
            content="Hello bot",
            attachments=[],
            created_at=datetime.now(UTC),
            guild=None,  # Group DM has guild=None, just like DMChannel
        )

        await fake_client.events["on_message"](message)

        # Handler must be called — group DM should work like DM
        handler.assert_awaited_once()


@patch("henchman.chat.discord_bot._check_discord_installed")
@pytest.mark.anyio
async def test_regular_dm_still_works(_mock_check: Any) -> None:
    """Regular DMs must still work after the fix."""
    fake_client = _FakeClient()
    fake_discord = _make_discord_module(fake_client)

    with patch.dict("sys.modules", {"discord": fake_discord}):
        from henchman.chat.discord_bot import DiscordBot

        bot = DiscordBot(
            token="fake-token",
            allowed_user_id="123",
        )
        handler = AsyncMock()
        bot.set_message_handler(handler)

        # Simulate a direct DM: channel is DMChannel, guild is None
        message = SimpleNamespace(
            id=1,
            author=SimpleNamespace(id=123, name="Test", display_name="Test User"),
            channel=_FakeDMChannel(),
            mentions=[],
            content="Hello bot",
            attachments=[],
            created_at=datetime.now(UTC),
            guild=None,
        )

        await fake_client.events["on_message"](message)

        # Handler must be called — regular DM still works
        handler.assert_awaited_once()


@patch("henchman.chat.discord_bot._check_discord_installed")
@pytest.mark.anyio
async def test_guild_message_requires_mention(_mock_check: Any) -> None:
    """Guild messages must still require a mention to be processed."""
    fake_client = _FakeClient()
    fake_discord = _make_discord_module(fake_client)

    with patch.dict("sys.modules", {"discord": fake_discord}):
        from henchman.chat.discord_bot import DiscordBot

        bot = DiscordBot(
            token="fake-token",
            allowed_user_id="123",
        )
        handler = AsyncMock()
        bot.set_message_handler(handler)

        # Simulate a guild message (guild is set, no mention)
        guild = SimpleNamespace(id=111, name="test-guild")
        message = SimpleNamespace(
            id=1,
            author=SimpleNamespace(id=123, name="Test", display_name="Test User"),
            channel=SimpleNamespace(id=789),
            mentions=[],
            content="Hello bot",
            attachments=[],
            created_at=datetime.now(UTC),
            guild=guild,
        )

        await fake_client.events["on_message"](message)

        # Handler must NOT be called — guild message with no mention
        handler.assert_not_awaited()
