"""Test for BUG-041: Redundant fetch_user calls on every send_message.

Every call to `send_message` and `send_typing` calls `fetch_user`, even
for repeated calls to the same user within a single interaction. The fix
caches the User object keyed by user_id.

Tests verify:
1. fetch_user is called only once for multiple send_message calls to same user
2. fetch_user is called separately for different users
3. Cache is invalidated on on_ready event
4. send_typing also benefits from the cache
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@dataclass
class _FakeClient:
    """Small fake Discord client."""

    user: Any = field(default_factory=lambda: SimpleNamespace(id=999, name="Henchman"))
    events: dict[str, Any] = field(default_factory=dict)
    fetch_user: Any = field(default_factory=AsyncMock)

    def event(self, func: Any) -> Any:
        """Register an event callback."""
        self.events[func.__name__] = func
        return func

    def get_user(self, user_id: int) -> Any | None:
        """Return cached user if available (simulates internal cache)."""
        return None


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
    )


@patch("henchman.chat.discord_bot._check_discord_installed")
@pytest.mark.anyio
async def test_fetch_user_called_once_for_multiple_sends(_mock_check: Any) -> None:
    """fetch_user must be called only once when sending multiple messages to the same user."""
    fake_client = _FakeClient()
    fake_discord = _make_discord_module(fake_client)

    fake_user = MagicMock()
    fake_user.send = AsyncMock()
    fake_client.fetch_user.return_value = fake_user

    with patch.dict("sys.modules", {"discord": fake_discord}):
        from henchman.chat.discord_bot import DiscordBot

        bot = DiscordBot(
            token="fake-token",
            allowed_user_id="123",
        )

        # Send multiple messages to the same user
        await bot.send_message("456", "Message 1")
        await bot.send_message("456", "Message 2")
        await bot.send_message("456", "Message 3")

        # fetch_user should have been called exactly once (cached after first call)
        assert fake_client.fetch_user.call_count == 1, (
            f"Expected 1 fetch_user call, got {fake_client.fetch_user.call_count}"
        )
        # User.send should have been called 3 times
        assert fake_user.send.call_count == 3


@patch("henchman.chat.discord_bot._check_discord_installed")
@pytest.mark.anyio
async def test_fetch_user_called_for_different_users(_mock_check: Any) -> None:
    """Different users must each get their own fetch_user call."""
    fake_client = _FakeClient()
    fake_discord = _make_discord_module(fake_client)

    fake_user_a = MagicMock()
    fake_user_a.send = AsyncMock()
    fake_user_b = MagicMock()
    fake_user_b.send = AsyncMock()

    async def _fetch_user_side_effect(user_id: int) -> Any:
        if user_id == 456:
            return fake_user_a
        return fake_user_b

    fake_client.fetch_user.side_effect = _fetch_user_side_effect

    def _reset_call_counts() -> None:
        fake_client.fetch_user.reset_mock()

    _reset_call_counts()

    with patch.dict("sys.modules", {"discord": fake_discord}):
        from henchman.chat.discord_bot import DiscordBot

        bot = DiscordBot(
            token="fake-token",
            allowed_user_id="123",
        )

        await bot.send_message("456", "Hello A")
        await bot.send_message("789", "Hello B")

        # fetch_user should have been called twice (two different users)
        assert fake_client.fetch_user.call_count == 2


@patch("henchman.chat.discord_bot._check_discord_installed")
@pytest.mark.anyio
async def test_cache_invalidated_on_ready(_mock_check: Any) -> None:
    """Cache must be cleared on on_ready event."""
    fake_client = _FakeClient()
    fake_discord = _make_discord_module(fake_client)

    fake_user = MagicMock()
    fake_user.send = AsyncMock()
    fake_client.fetch_user.return_value = fake_user

    with patch.dict("sys.modules", {"discord": fake_discord}):
        from henchman.chat.discord_bot import DiscordBot

        bot = DiscordBot(
            token="fake-token",
            allowed_user_id="123",
        )

        # First call populates cache
        await bot.send_message("456", "Message 1")
        assert fake_client.fetch_user.call_count == 1

        # Simulate on_ready event
        await fake_client.events["on_ready"]()

        # After on_ready, fetch_user should be called again
        await bot.send_message("456", "Message 2")
        assert fake_client.fetch_user.call_count == 2, (
            "Cache should be invalidated on on_ready"
        )


@patch("henchman.chat.discord_bot._check_discord_installed")
@pytest.mark.anyio
async def test_send_typing_uses_cache(_mock_check: Any) -> None:
    """send_typing must also benefit from the fetch_user cache."""
    fake_client = _FakeClient()
    fake_discord = _make_discord_module(fake_client)

    fake_user = MagicMock()
    fake_user.send = AsyncMock()
    fake_client.fetch_user.return_value = fake_user

    with patch.dict("sys.modules", {"discord": fake_discord}):
        from henchman.chat.discord_bot import DiscordBot

        bot = DiscordBot(
            token="fake-token",
            allowed_user_id="123",
        )

        # Call send_typing first
        await bot.send_typing("456")
        assert fake_client.fetch_user.call_count == 1

        # call send_message — should use cached user, not fetch again
        await bot.send_message("456", "Hello")
        assert fake_client.fetch_user.call_count == 1, (
            "send_message should use cached user from send_typing"
        )
