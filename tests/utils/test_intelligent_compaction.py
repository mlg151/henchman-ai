"""Tests for intelligent compaction functionality."""

from henchman.providers.base import Message, ToolCall
from henchman.utils.intelligent_context import IntelligentContextManager
from henchman.utils.intelligent_context_config import IntelligentContextParams


def test_compact_empty_messages():
    """Test compact with empty message list."""
    manager = IntelligentContextManager(params=IntelligentContextParams(max_tokens=1000))
    result = manager.compact([])
    assert result == []


def test_compact_with_result_empty_messages():
    """Test compact_with_result with empty message list."""
    manager = IntelligentContextManager(params=IntelligentContextParams(max_tokens=1000))
    result = manager.compact_with_result([])
    assert result.messages == []
    assert result.was_compacted is False
    assert result.dropped_count == 0
    assert result.summary is None
    assert result.importance_scores == {}
    assert result.clusters == []
    assert result.compression_ratio == 0.0


def test_compact_small_conversation_fits():
    """Test compact when conversation fits within token limit."""
    manager = IntelligentContextManager(params=IntelligentContextParams(max_tokens=1000))

    messages = [
        Message(role="user", content="Hello, how are you?"),
        Message(role="assistant", content="I'm doing well, thank you!"),
        Message(role="user", content="Can you help me with a coding problem?"),
    ]

    result = manager.compact(messages)
    assert len(result) == 3
    # Should preserve all messages since they fit
    assert result[0].content == "Hello, how are you?"
    assert result[1].content == "I'm doing well, thank you!"
    assert result[2].content == "Can you help me with a coding problem?"


def test_compact_with_result_small_conversation():
    """Test compact_with_result for small conversation."""
    manager = IntelligentContextManager(params=IntelligentContextParams(max_tokens=1000))

    messages = [
        Message(role="user", content="Hello"),
        Message(role="assistant", content="Hi there"),
    ]

    result = manager.compact_with_result(messages)
    assert len(result.messages) == 2
    assert result.was_compacted is False  # No compaction needed
    assert result.dropped_count == 0
    assert result.compression_ratio == 0.0
    assert result.importance_scores is not None
    assert result.clusters is not None


def test_compact_preserves_tool_sequences():
    """Test that tool call sequences are preserved during compaction."""
    manager = IntelligentContextManager(params=IntelligentContextParams(max_tokens=1000))

    tool_call = ToolCall(id="tool_1", name="test_tool", arguments={"param": "value"})

    messages = [
        Message(role="user", content="Please use a tool"),
        Message(role="assistant", content="I'll use the tool", tool_calls=[tool_call]),
        Message(role="tool", content="Tool result", tool_call_id="tool_1"),
        Message(role="user", content="Thank you"),
    ]

    result = manager.compact(messages)
    assert len(result) == 4
    # Tool sequence should be preserved
    assert result[1].tool_calls == [tool_call]
    assert result[2].tool_call_id == "tool_1"


def test_compact_with_high_importance_messages():
    """Test that high-importance messages are preserved."""
    # Use a very small token limit to force compaction
    manager = IntelligentContextManager(params=IntelligentContextParams(max_tokens=30))  # Very small limit

    # Create messages with varying importance
    messages = [
        Message(role="system", content="You are a helpful assistant."),  # High importance
        Message(role="user", content="There's an error in the code."),  # High importance (error keyword)
        Message(role="assistant", content="Let me check the error."),  # High importance (error keyword)
        Message(role="user", content="The function is not working."),  # High importance (error keyword)
        Message(role="assistant", content="I found the issue."),  # High importance (error keyword)
        Message(role="user", content="Can you fix it?"),  # Medium importance
        Message(role="assistant", content="Yes, I fixed it."),  # Medium importance
        Message(role="user", content="Great, thanks!"),  # Low importance
    ]

    result = manager.compact(messages)
    # Should preserve high-importance messages (error-related)
    assert len(result) < len(messages)  # Some compaction should occur
    # System message and error messages should be preserved
    assert any("error" in msg.content.lower() for msg in result if msg.content)
    assert any(msg.role == "system" for msg in result)


def test_compact_with_protected_index():
    """Test compact with protected messages."""
    manager = IntelligentContextManager(params=IntelligentContextParams(max_tokens=300))  # Very small limit

    messages = [
        Message(role="user", content="Message 1"),
        Message(role="assistant", content="Response 1"),
        Message(role="user", content="Message 2"),
        Message(role="assistant", content="Response 2"),
        Message(role="user", content="Message 3"),  # This and later should be protected
        Message(role="assistant", content="Response 3"),
    ]

    # Protect from index 4 (message 3 and response 3)
    result = manager.compact(messages, protect_from_index=4)

    # Should preserve protected messages (last 2)
    assert len(result) >= 2
    assert result[-2].content == "Message 3"
    assert result[-1].content == "Response 3"


def test_compact_with_result_metrics():
    """Test that compact_with_result returns proper metrics."""
    manager = IntelligentContextManager(params=IntelligentContextParams(max_tokens=1000))

    messages = [
        Message(role="user", content="Test message 1"),
        Message(role="assistant", content="Test response 1"),
        Message(role="user", content="Test message 2"),
        Message(role="assistant", content="Test response 2"),
    ]

    result = manager.compact_with_result(messages)

    # Check all metrics are present
    assert result.messages is not None
    assert isinstance(result.was_compacted, bool)
    assert isinstance(result.dropped_count, int)
    assert result.importance_scores is not None
    assert isinstance(result.importance_scores, dict)
    assert result.clusters is not None
    assert isinstance(result.clusters, list)
    assert result.compression_ratio is not None
    assert 0.0 <= result.compression_ratio <= 1.0


def test_compact_enforces_safety_limits():
    """Test that safety limits are enforced on individual messages."""
    # Create manager with default config, then modify safety limit
    manager = IntelligentContextManager(params=IntelligentContextParams(max_tokens=1000))
    manager.config.safety_limit_ratio = 0.1  # 10% limit

    # Create a very long message
    long_content = "word " * 1000  # Very long content
    messages = [
        Message(role="user", content="Short message"),
        Message(role="assistant", content=long_content),
    ]

    result = manager.compact(messages)
    assert len(result) == 2
    # Long message should be truncated
    assert "truncated" in result[1].content
    assert len(result[1].content) < len(long_content)


def test_compact_clusters_related_messages():
    """Test that related messages are clustered together."""
    manager = IntelligentContextManager(params=IntelligentContextParams(max_tokens=1000, cluster_similarity_threshold=0.5))

    # Create a conversation about a specific topic
    messages = [
        Message(role="user", content="I need help with Python programming."),
        Message(role="assistant", content="I can help with Python. What do you need?"),
        Message(role="user", content="How do I write a function in Python?"),
        Message(role="assistant", content="Here's how to write a function: def my_function(): ..."),

        # Different topic
        Message(role="user", content="Now let's talk about JavaScript."),
        Message(role="assistant", content="Sure, what about JavaScript?"),
    ]

    result = manager.compact_with_result(messages)

    # Should detect clusters
    assert result.clusters is not None
    assert len(result.clusters) > 0

    # Python-related messages should be in same or adjacent clusters
    python_messages = [0, 1, 2, 3]
    in_same_cluster = False
    for cluster in result.clusters:
        if all(idx in cluster for idx in python_messages[:2]):
            in_same_cluster = True
            break
    assert in_same_cluster, "Related Python messages should be clustered together"
