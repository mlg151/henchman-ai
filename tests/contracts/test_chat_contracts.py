"""Contract tests for chat integrations and boundaries."""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime

import pytest

from henchman.chat.base import ChatBot, ChatMessage, ChatPlatform
from henchman.testing.contract import ContractSuite
from tests.contracts.helpers import (
    assert_contract_matches,
    serialize_contract_value,
)

# ===========================================================================
# ChatPlatform enum contract
# ===========================================================================


class TestChatPlatformContract:
    """ChatPlatform enum must provide the expected platform values."""

    def test_platform_values(self) -> None:
        """ChatPlatform must have the expected platform values."""
        assert ChatPlatform.TELEGRAM.value == "telegram"
        assert ChatPlatform.DISCORD.value == "discord"
        assert ChatPlatform.SLACK.value == "slack"

    def test_platform_lookup_by_value(self) -> None:
        """ChatPlatform must be constructable from string values."""
        assert ChatPlatform("telegram") is ChatPlatform.TELEGRAM
        assert ChatPlatform("discord") is ChatPlatform.DISCORD
        assert ChatPlatform("slack") is ChatPlatform.SLACK


# ===========================================================================
# ChatMessage dataclass contract
# ===========================================================================


class TestChatMessageDataclassContract:
    """ChatMessage must conform to the expected data shape."""

    def test_required_fields(self) -> None:
        """ChatMessage must require all core fields."""
        msg = ChatMessage(
            id="msg-001",
            user_id="user-42",
            username="testuser",
            content="Hello, world!",
            timestamp=datetime(2024, 1, 15, 10, 30, tzinfo=UTC),
            platform=ChatPlatform.DISCORD,
        )
        assert msg.id == "msg-001"
        assert msg.user_id == "user-42"
        assert msg.username == "testuser"
        assert msg.content == "Hello, world!"
        assert msg.platform == ChatPlatform.DISCORD
        assert msg.attachments == []
        assert msg.is_dm is True

    def test_optional_fields(self) -> None:
        """ChatMessage optional fields should accept provided values."""
        msg = ChatMessage(
            id="msg-002",
            user_id="user-42",
            username="testuser",
            content="Here is a file",
            timestamp=datetime(2024, 1, 15, 10, 30, tzinfo=UTC),
            platform=ChatPlatform.SLACK,
            attachments=[{"name": "report.pdf", "size": 1024}],
            is_dm=False,
        )
        assert msg.attachments == [{"name": "report.pdf", "size": 1024}]
        assert msg.is_dm is False

    def test_chat_message_matches_contract(
        self,
        contract_suite: ContractSuite,
    ) -> None:
        """A ChatMessage payload must match the expected contract schema."""
        msg = ChatMessage(
            id="msg-003",
            user_id="user-99",
            username="alice",
            content="Test message",
            timestamp=datetime(2024, 1, 15, 12, 0, tzinfo=UTC),
            platform=ChatPlatform.TELEGRAM,
            attachments=[],
            is_dm=True,
        )
        schema = {
            "id": str,
            "user_id": str,
            "username": str,
            "content": str,
            "timestamp": datetime,
            "platform": ChatPlatform,
            "attachments": list,
            "is_dm": bool,
        }
        errors = contract_suite.validate(asdict(msg), schema)
        assert errors == [], f"Contract validation failed: {errors}"


# ===========================================================================
# ChatBot ABC protocol contract
# ===========================================================================


class TestChatBotProtocolContract:
    """ChatBot ABC must enforce the required abstract interface."""

    def test_chatbot_cannot_be_instantiated_directly(self) -> None:
        """ChatBot should be an abstract base class."""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            ChatBot()  # type: ignore[abstract]

    def test_incomplete_bot_raises_type_error(self) -> None:
        """Subclasses missing abstract methods should not instantiate."""

        class IncompleteBot(ChatBot):
            pass

        with pytest.raises(TypeError):
            IncompleteBot()  # type: ignore[abstract]

    def test_minimal_valid_bot_satisfies_contract(self) -> None:
        """A minimal valid ChatBot should provide all required properties/methods."""

        class MinimalBot(ChatBot):
            @property
            def platform(self) -> ChatPlatform:
                return ChatPlatform.DISCORD

            @property
            def is_connected(self) -> bool:
                return False

            async def start(self) -> None:
                pass

            async def stop(self) -> None:
                pass

            async def send_message(
                self,
                user_id: str,
                content: str,
                *,
                split_long: bool = True,
            ) -> None:
                pass

            async def send_typing(self, user_id: str) -> None:
                pass

            def set_message_handler(self, handler: object) -> None:
                pass

        bot = MinimalBot()
        assert bot.platform == ChatPlatform.DISCORD
        assert bot.is_connected is False

    def test_bot_platform_property_contract(self) -> None:
        """A ChatBot must report its platform correctly."""

        class TelegramBot(ChatBot):
            @property
            def platform(self) -> ChatPlatform:
                return ChatPlatform.TELEGRAM

            @property
            def is_connected(self) -> bool:
                return False

            async def start(self) -> None:
                pass

            async def stop(self) -> None:
                pass

            async def send_message(
                self,
                user_id: str,
                content: str,
                *,
                split_long: bool = True,
            ) -> None:
                pass

            async def send_typing(self, user_id: str) -> None:
                pass

            def set_message_handler(self, handler: object) -> None:
                pass

        bot = TelegramBot()
        assert bot.platform == ChatPlatform.TELEGRAM


def test_chat_message_payload_matches_contract(contract_suite) -> None:
    """The serialized ChatMessage should satisfy the contract schema."""
    message = ChatMessage(
        id="msg-1",
        user_id="user-1",
        username="testuser",
        content="hello bot",
        timestamp=datetime.now(UTC),
        platform=ChatPlatform.DISCORD,
        attachments=[{"url": "http://example.com/img.png"}],
        is_dm=True,
    )

    payload = serialize_contract_value(message)

    assert_contract_matches(
        payload=payload,
        schema_name="chat/chat_message",
        contract_suite=contract_suite,
    )


class _ChatBotDouble(ChatBot):
    """Runtime double for the ChatBot provider contract."""

    @property
    def platform(self) -> ChatPlatform:
        return ChatPlatform.SLACK

    @property
    def is_connected(self) -> bool:
        return True

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def send_message(self, user_id: str, content: str, *, split_long: bool = True) -> None:
        pass

    async def send_typing(self, user_id: str) -> None:
        pass

    def set_message_handler(self, handler) -> None:
        pass


def test_chat_bot_provider_satisfies_contract() -> None:
    """A ChatBot implementation must satisfy all interface requirements."""
    # Instantiating the double ensures the ABC constraints are met.
    # If the signature is incomplete, it will fail to instantiate or type-check.
    bot = _ChatBotDouble()

    assert bot.platform == ChatPlatform.SLACK
    assert bot.is_connected is True
    assert callable(bot.start)
    assert callable(bot.stop)
    assert callable(bot.send_message)
    assert callable(bot.send_typing)
    assert callable(bot.set_message_handler)

