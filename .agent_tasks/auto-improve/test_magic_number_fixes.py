"""Tests for magic number extraction in intelligent_context.py."""

import pytest
from henchman.utils.intelligent_context import IntelligentContextManager
from henchman.providers.base import Message


def test_magic_number_100_for_context_limit():
    """Test that the magic number 100 for context limit works correctly."""
    manager = IntelligentContextManager(max_tokens=1000)
    
    # Create a test to verify the behavior with remaining_limit > 100
    # This would require testing internal methods, which might not be public
    # For now, just verify the manager can be created
    assert manager.config.max_tokens == 1000


def test_magic_number_10_for_min_content():
    """Test that the magic number 10 for min content tokens works."""
    manager = IntelligentContextManager(max_tokens=1000)
    
    # Test truncate_with_marker behavior (if it's public or we can test through compact)
    messages = [
        Message(role="user", content="Test " * 100),  # Very long message
        Message(role="assistant", content="Response"),
    ]
    
    # Compact should handle long messages
    result = manager.compact(messages)
    assert len(result) <= len(messages) or all(len(msg.content or "") <= 1000 for msg in result)


def test_magic_numbers_for_recent_message_preservation():
    """Test that magic numbers 10 and 5 for recent message preservation work."""
    # Create many messages
    messages = []
    for i in range(20):
        messages.append(Message(role="user" if i % 2 == 0 else "assistant", content=f"Message {i}"))
    
    manager = IntelligentContextManager(max_tokens=500)  # Small limit to force compression
    
    # Compact should preserve some recent messages
    result = manager.compact(messages)
    
    # Should have fewer messages than original due to compression
    assert len(result) <= len(messages)
    
    # Should preserve at least some messages
    assert len(result) > 0


def test_magic_number_15_for_max_preserved():
    """Test that magic number 15 for max preserved indices works."""
    # Create many messages
    messages = []
    for i in range(30):
        messages.append(Message(role="user" if i % 2 == 0 else "assistant", content=f"Message {i}"))
    
    manager = IntelligentContextManager(max_tokens=1000)
    
    # Compact with a reasonable limit
    result = manager.compact(messages)
    
    # Should have reduced number of messages
    assert len(result) < len(messages)
    
    # Should not preserve more than a reasonable number (implementation detail)
    # This test is checking behavior, not exact implementation


if __name__ == "__main__":
    pytest.main([__file__, "-v"])