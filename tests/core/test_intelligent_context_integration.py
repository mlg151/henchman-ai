"""Integration tests for Intelligent Context Management with Agent class.

These tests verify that the intelligent context system works correctly
when integrated with the main Agent workflow.
"""

from unittest.mock import MagicMock, patch

import pytest

from henchman.core.agent import Agent
from henchman.core.events import EventType
from henchman.providers.base import FinishReason, Message, ModelProvider, StreamChunk, ToolCall
from henchman.utils.intelligent_context import IntelligentContextManager, IntelligentContextParams


@pytest.fixture
def mock_provider():
    """Create a mock provider for testing."""
    provider = MagicMock(spec=ModelProvider)
    return provider


@pytest.fixture
def mock_stream_chunk():
    """Create a mock stream chunk."""
    return StreamChunk(content="Hello", finish_reason=FinishReason.STOP)


@pytest.fixture
def sample_messages():
    """Create sample messages for testing."""
    return [
        Message(role="system", content="You are a helpful assistant"),
        Message(role="user", content="Hello, how are you?"),
        Message(role="assistant", content="I'm doing well, thank you!"),
        Message(role="user", content="What's the weather like today?"),
        Message(role="assistant", content="I don't have access to weather data."),
        Message(role="user", content="Can you help me with a task?"),
        Message(role="assistant", content="Yes, I can help you with that."),
    ]


@pytest.fixture
def sample_messages_with_tools():
    """Create sample messages with tool calls for testing."""
    tool_call = ToolCall(id="test-tool-call-123", name="test_tool", arguments={"param": "value"})
    return [
        Message(role="system", content="You are a helpful assistant"),
        Message(role="user", content="Please execute this tool"),
        Message(role="assistant", content="I'll use the tool", tool_calls=[tool_call]),
        Message(role="tool", content="Tool result: success", tool_call_id="test-tool-call-123"),
        Message(role="user", content="Thank you!"),
    ]


class TestAgentIntelligentContextIntegration:
    """Integration tests for Agent with intelligent context management."""

    def test_agent_initialization_with_intelligent_context(self, mock_provider):
        """Test Agent initialization with intelligent context parameters."""
        agent = Agent(
            provider=mock_provider,
            intelligent_context=True,
            importance_threshold=0.6,
            cluster_similarity_threshold=0.8,
            adaptive_compression=False,
        )

        assert agent.intelligent_context is True
        assert agent.importance_threshold == 0.6
        assert agent.cluster_similarity_threshold == 0.8
        assert agent.adaptive_compression is False

    def test_agent_initialization_without_intelligent_context(self, mock_provider):
        """Test Agent initialization without intelligent context (default)."""
        agent = Agent(provider=mock_provider)

        assert agent.intelligent_context is False
        # Default values should be set
        assert agent.importance_threshold == 0.5
        assert agent.cluster_similarity_threshold == 0.7
        assert agent.adaptive_compression is True

    def test_get_messages_for_api_with_intelligent_context_enabled(
        self, mock_provider, sample_messages
    ):
        """Test get_messages_for_api() with intelligent context enabled."""
        agent = Agent(
            provider=mock_provider,
            intelligent_context=True,
            max_tokens=100,  # Low limit to force compaction
        )
        agent.messages = sample_messages

        # Mock the IntelligentContextManager to verify it's used
        with patch(
            "henchman.utils.intelligent_context.IntelligentContextManager"
        ) as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager.compact.return_value = sample_messages[:3]  # Return compacted version
            mock_manager_class.return_value = mock_manager

            result = agent.get_messages_for_api()

            # Verify IntelligentContextManager was instantiated with correct params
            mock_manager_class.assert_called_once_with(
                params=IntelligentContextParams(
                    max_tokens=100,
                    max_protected_ratio=0.3,
                    importance_threshold=0.5,  # Default
                    cluster_similarity_threshold=0.7,  # Default
                    adaptive_compression=True,  # Default
                )
            )
            mock_manager.compact.assert_called_once_with(
                sample_messages,
                protect_from_index=-1,  # No turn started (default -1)
            )
            assert result == sample_messages[:3]

    def test_get_messages_for_api_with_intelligent_context_disabled(
        self, mock_provider, sample_messages
    ):
        """Test get_messages_for_api() with intelligent context disabled."""
        agent = Agent(
            provider=mock_provider,
            intelligent_context=False,
            max_tokens=100,  # Low limit to force compaction
        )
        agent.messages = sample_messages

        # Mock the ContextCompactor to verify it's used
        with patch("henchman.utils.compaction.ContextCompactor") as mock_compactor_class:
            mock_compactor = MagicMock()
            mock_compactor.compact.return_value = sample_messages[:3]  # Return compacted version
            mock_compactor_class.return_value = mock_compactor

            result = agent.get_messages_for_api()

            # Verify ContextCompactor was instantiated with correct params
            mock_compactor_class.assert_called_once_with(
                max_tokens=100,
                max_protected_ratio=0.3,
            )
            mock_compactor.compact.assert_called_once_with(
                sample_messages,
                protect_from_index=-1,  # No turn started (default -1)
            )
            assert result == sample_messages[:3]

    def test_get_messages_for_api_with_turn_protection(self, mock_provider, sample_messages):
        """Test get_messages_for_api() protects messages from current turn."""
        agent = Agent(
            provider=mock_provider,
            intelligent_context=True,
            max_tokens=100,  # Low limit to force compaction
        )
        agent.messages = sample_messages
        agent.turn.start_index = 4  # Protect last 3 messages (indices 4, 5, 6)

        with patch(
            "henchman.utils.intelligent_context.IntelligentContextManager"
        ) as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager.compact.return_value = sample_messages  # Return same for simplicity
            mock_manager_class.return_value = mock_manager

            agent.get_messages_for_api()

            mock_manager.compact.assert_called_once_with(
                sample_messages,
                protect_from_index=4,  # Should protect from turn start index
            )

    @pytest.mark.asyncio
    async def test_apply_simple_compaction_with_intelligent_context(
        self, mock_provider, sample_messages
    ):
        """Test _apply_simple_compaction() uses intelligent context when enabled."""
        agent = Agent(
            provider=mock_provider,
            intelligent_context=True,
            max_tokens=50,  # Low limit to force compaction
            summarize_dropped=False,
        )
        agent.messages = sample_messages
        agent.turn.start_index = 0

        with patch(
            "henchman.utils.intelligent_context.IntelligentContextManager"
        ) as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager.compact.return_value = sample_messages[:3]
            mock_manager_class.return_value = mock_manager

            # Mock repair_message_sequence to return same messages
            with patch("henchman.core.agent.repair_message_sequence", side_effect=lambda x: x):
                await agent._apply_simple_compaction(protected_count=0)

                # Verify IntelligentContextManager was used
                mock_manager_class.assert_called_once_with(
                    params=IntelligentContextParams(
                        max_tokens=50,
                        max_protected_ratio=0.3,
                        importance_threshold=0.5,
                        cluster_similarity_threshold=0.7,
                        adaptive_compression=True,
                    )
                )
                mock_manager.compact.assert_called_once_with(
                    sample_messages,
                    protect_from_index=0,
                )
                assert agent.messages == sample_messages[:3]

    @pytest.mark.asyncio
    async def test_apply_simple_compaction_without_intelligent_context(
        self, mock_provider, sample_messages
    ):
        """Test _apply_simple_compaction() uses ContextCompactor when intelligent context disabled."""
        agent = Agent(
            provider=mock_provider,
            intelligent_context=False,
            max_tokens=50,  # Low limit to force compaction
            summarize_dropped=False,
        )
        agent.messages = sample_messages
        agent.turn.start_index = 0

        with patch("henchman.utils.compaction.ContextCompactor") as mock_compactor_class:
            mock_compactor = MagicMock()
            mock_compactor.compact.return_value = sample_messages[:3]
            mock_compactor_class.return_value = mock_compactor

            # Mock repair_message_sequence to return same messages
            with patch("henchman.core.agent.repair_message_sequence", side_effect=lambda x: x):
                await agent._apply_simple_compaction(protected_count=0)

                # Verify ContextCompactor was used
                mock_compactor_class.assert_called_once_with(
                    max_tokens=50,
                    max_protected_ratio=0.3,
                )
                mock_compactor.compact.assert_called_once_with(
                    sample_messages,
                    protect_from_index=0,
                )
                assert agent.messages == sample_messages[:3]

    def test_token_reduction_metrics_with_intelligent_context(self, mock_provider):
        """Test that intelligent context provides token reduction metrics.

        Note: The compact() method returns list[Message], not IntelligentCompactionResult.
        The IntelligentCompactionResult is returned by compact_with_result() method.
        """
        # Create a mock IntelligentContextManager
        mock_manager = MagicMock(spec=IntelligentContextManager)

        compacted_messages = [
            Message(role="system", content="You are a helpful assistant"),
            Message(role="user", content="Hello, how are you?"),
        ]

        # The compact() method should return just the messages
        mock_manager.compact.return_value = compacted_messages

        agent = Agent(
            provider=mock_provider,
            intelligent_context=True,
            max_tokens=100,
        )

        # Replace the manager creation with our mock
        with patch(
            "henchman.utils.intelligent_context.IntelligentContextManager",
            return_value=mock_manager,
        ):
            # The get_messages_for_api should return just the messages
            result = agent.get_messages_for_api()
            assert result == compacted_messages

            # Verify compact was called
            mock_manager.compact.assert_called_once()

    @pytest.mark.asyncio
    async def test_agent_run_with_intelligent_context(self, mock_provider):
        """Test Agent.run() works with intelligent context enabled."""
        agent = Agent(
            provider=mock_provider,
            intelligent_context=True,
        )

        # Mock provider to return a simple chunk
        chunk = StreamChunk(content="Hello", finish_reason=FinishReason.STOP)

        async def async_gen(*_args, **_kwargs):  # noqa: ARG001
            yield chunk

        mock_provider.chat_completion_stream = async_gen

        events = []
        async for event in agent.run("Hi"):
            events.append(event)

        # Should have at least FINISHED event
        assert len(events) > 0
        assert any(event.type == EventType.FINISHED for event in events)

    def test_configuration_integration(self, mock_provider):
        """Test that Agent configuration integrates with intelligent context settings."""
        # Test with custom configuration
        agent = Agent(
            provider=mock_provider,
            intelligent_context=True,
            importance_threshold=0.8,
            cluster_similarity_threshold=0.9,
            adaptive_compression=False,
            max_protected_ratio=0.4,
        )

        assert agent.intelligent_context is True
        assert agent.importance_threshold == 0.8
        assert agent.cluster_similarity_threshold == 0.9
        assert agent.adaptive_compression is False
        assert agent.max_protected_ratio == 0.4

        # Verify these settings are passed to IntelligentContextManager
        with patch(
            "henchman.utils.intelligent_context.IntelligentContextManager"
        ) as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager.compact.return_value = []
            mock_manager_class.return_value = mock_manager

            agent.get_messages_for_api()

            mock_manager_class.assert_called_once_with(
                params=IntelligentContextParams(
                    max_tokens=agent.max_tokens,
                    max_protected_ratio=0.4,  # From agent config
                    importance_threshold=0.8,  # From agent config
                    cluster_similarity_threshold=0.9,  # From agent config
                    adaptive_compression=False,  # From agent config
                )
            )

    def test_message_compaction_integration_with_tool_sequences(
        self, mock_provider, sample_messages_with_tools
    ):
        """Test that intelligent context preserves tool call sequences."""
        agent = Agent(
            provider=mock_provider,
            intelligent_context=True,
            max_tokens=100,  # Low limit to force compaction
        )
        agent.messages = sample_messages_with_tools

        # Mock the IntelligentContextManager
        with patch(
            "henchman.utils.intelligent_context.IntelligentContextManager"
        ) as mock_manager_class:
            mock_manager = MagicMock()
            # Return compacted version that should preserve tool sequence
            compacted = [
                sample_messages_with_tools[0],  # system
                sample_messages_with_tools[2],  # assistant with tool call
                sample_messages_with_tools[3],  # tool result
            ]
            mock_manager.compact.return_value = compacted
            mock_manager_class.return_value = mock_manager

            result = agent.get_messages_for_api()

            # Verify the manager was called
            mock_manager.compact.assert_called_once()
            # Result should preserve tool sequence
            assert len(result) == 3
            # Check that tool call and result are together
            assert result[1].tool_calls is not None
            assert result[2].role == "tool"

    def test_backward_compatibility(self, mock_provider):
        """Test that Agent works the same with intelligent context disabled."""
        # Create two agents with same settings except intelligent_context
        agent_with_intel = Agent(
            provider=mock_provider,
            intelligent_context=True,
            max_tokens=1000,
        )

        agent_without_intel = Agent(
            provider=mock_provider,
            intelligent_context=False,
            max_tokens=1000,
        )

        # Both should have same basic properties
        assert agent_with_intel.max_tokens == agent_without_intel.max_tokens
        assert agent_with_intel.max_protected_ratio == agent_without_intel.max_protected_ratio
        assert agent_with_intel.summarize_dropped == agent_without_intel.summarize_dropped

        # Only difference should be intelligent_context flag
        assert agent_with_intel.intelligent_context is True
        assert agent_without_intel.intelligent_context is False
