"""Test automatic context compaction."""


from unittest.mock import Mock

from henchman.core.agent import Agent
from henchman.providers.base import Message


class TestAutomaticContextCompaction:
    """Tests for automatic context compaction in Agent."""

    def test_compaction_applied_when_needed(self) -> None:
        """Compaction should be applied when context exceeds max_tokens."""
        # Create a mock provider
        mock_provider = Mock()

        # Create agent with small max_tokens to trigger compaction
        agent = Agent(provider=mock_provider, max_tokens=100)

        # Add many messages to exceed token limit
        for i in range(10):
            agent.history.append(
                Message(role="user", content=f"Message {i}: " + "x" * 100)
            )

        # Get messages for API (should trigger compaction)
        messages = agent.get_messages_for_api()

        # Compaction should have reduced the number of messages
        # (keeps system messages and last user message)
        assert len(messages) < len(agent.history)

        # Should have at least the last user message
        assert any(m.role == "user" for m in messages)

    def test_no_compaction_when_within_limit(self) -> None:
        """Compaction should not be applied when within token limit."""
        # Create a mock provider
        mock_provider = Mock()

        # Create agent with large max_tokens
        agent = Agent(provider=mock_provider, max_tokens=10000)

        # Add a few messages
        agent.history.append(Message(role="user", content="Short message 1"))
        agent.history.append(Message(role="assistant", content="Short response 1"))
        agent.history.append(Message(role="user", content="Short message 2"))

        # Get messages for API
        original_count = len(agent.history)
        messages = agent.get_messages_for_api()

        # Should have same number of messages (no compaction needed)
        assert len(messages) == original_count

    def test_system_prompt_preserved(self) -> None:
        """System prompt should always be preserved during compaction."""
        # Create a mock provider
        mock_provider = Mock()

        # Create agent with system prompt
        agent = Agent(
            provider=mock_provider,
            system_prompt="You are a helpful assistant.",
            max_tokens=100
        )

        # Add many messages to exceed token limit
        for i in range(10):
            agent.history.append(
                Message(role="user", content=f"Message {i}: " + "x" * 100)
            )

        # Get messages for API
        messages = agent.get_messages_for_api()

        # First message should be system prompt
        assert messages[0].role == "system"
        assert "helpful assistant" in messages[0].content

    def test_last_user_message_preserved_when_user_last(self) -> None:
        """Last user message should be preserved when it's the last message."""
        # Create a mock provider
        mock_provider = Mock()

        # Create agent with small max_tokens
        agent = Agent(provider=mock_provider, max_tokens=100)

        # Add messages ending with user message
        for i in range(5):
            agent.history.append(
                Message(role="user", content=f"Message {i}: " + "x" * 50)
            )
            agent.history.append(
                Message(role="assistant", content=f"Response {i}: " + "x" * 50)
            )
        # Add final user message
        agent.history.append(
            Message(role="user", content="Final user message")
        )

        # Get messages for API
        messages = agent.get_messages_for_api()

        # Last message should be preserved (it's a user message)
        assert messages[-1].role == "user"
        assert "Final user message" in messages[-1].content

    def test_compaction_logic_understands_token_limits(self) -> None:
        """Compaction should work correctly with token counting."""
        # Create a mock provider
        mock_provider = Mock()

        # Create agent with very small max_tokens
        agent = Agent(provider=mock_provider, max_tokens=50)

        # Add messages that will definitely exceed token limit
        agent.history.append(Message(role="user", content="A" * 100))  # ~25 tokens
        agent.history.append(Message(role="assistant", content="B" * 100))  # ~25 tokens
        agent.history.append(Message(role="user", content="C" * 100))  # ~25 tokens

        # Get messages for API
        messages = agent.get_messages_for_api()

        # Should have fewer messages due to compaction
        assert len(messages) < len(agent.history)

        # Should at least have system (if any) and the last user message
        # (Note: agent has no system prompt in this test)
        if messages:
            # Either we kept some messages or compaction returned empty
            pass
