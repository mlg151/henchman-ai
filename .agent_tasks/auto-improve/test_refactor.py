"""Test to verify intelligent_context.py refactoring doesn't break functionality."""

import pytest
from henchman.providers.base import Message
from henchman.utils.intelligent_context import IntelligentContextManager


def test_basic_functionality():
    """Test basic functionality of IntelligentContextManager."""
    manager = IntelligentContextManager(max_tokens=1000)
    
    # Create some test messages
    messages = [
        Message(role="system", content="You are a helpful assistant."),
        Message(role="user", content="Hello, how are you?"),
        Message(role="assistant", content="I'm doing well, thank you!"),
    ]
    
    # Test importance scoring
    scores = manager._calculate_importance_scores(messages)
    assert len(scores) == 3
    assert all(0.0 <= score <= 1.0 for score in scores.values())
    
    # Test clustering
    clusters = manager._cluster_messages(messages)
    assert isinstance(clusters, list)
    
    # Test compaction
    compacted = manager.compact(messages, protect_from_index=0)
    assert isinstance(compacted, list)
    assert len(compacted) <= len(messages)
    
    # Test validation
    is_valid = manager.validate_compacted_sequence(messages)
    assert isinstance(is_valid, bool)


def test_edge_cases():
    """Test edge cases."""
    manager = IntelligentContextManager(max_tokens=100)
    
    # Empty messages
    scores = manager._calculate_importance_scores([])
    assert scores == {}
    
    clusters = manager._cluster_messages([])
    assert clusters == []
    
    compacted = manager.compact([], protect_from_index=0)
    assert compacted == []
    
    # Single message
    messages = [Message(role="user", content="Test")]
    scores = manager._calculate_importance_scores(messages)
    assert len(scores) == 1
    
    # Test with tool calls
    from henchman.providers.base import ToolCall
    tool_call = ToolCall(id="test", name="test_tool", arguments={})
    messages_with_tools = [
        Message(role="assistant", content="I'll use a tool", tool_calls=[tool_call]),
        Message(role="tool", content="Tool result", tool_call_id="test"),
    ]
    
    is_valid = manager.validate_compacted_sequence(messages_with_tools)
    assert isinstance(is_valid, bool)


if __name__ == "__main__":
    test_basic_functionality()
    test_edge_cases()
    print("All tests passed!")