"""Edge case tests for intelligent_context.py to improve coverage."""

from henchman.providers.base import Message, ToolCall
from henchman.utils.intelligent_context import (
    IntelligentContextManager,
    ContentExtractor,
    MessageSafetyEnforcer,
    SequenceValidator,
)


def test_content_extractor_empty_patterns():
    """Test ContentExtractor with empty patterns."""
    content = "Some content with errors: ValueError"
    result = ContentExtractor._extract_by_patterns(content, [])
    assert result == []


def test_content_extractor_none_content():
    """Test ContentExtractor with None content."""
    result = ContentExtractor._extract_by_patterns(None, [r"error"])
    assert result == []


def test_message_safety_enforcer_none_message():
    """Test MessageSafetyEnforcer with None message."""
    enforcer = MessageSafetyEnforcer(safety_limit_ratio=0.8, max_tokens=1000)
    try:
        enforcer._enforce_message_safety_limit(None)
        assert False, "Should have raised TypeError"
    except TypeError as e:
        assert "Message cannot be None" in str(e)


def test_message_safety_enforcer_none_content():
    """Test MessageSafetyEnforcer with message having None content."""
    enforcer = MessageSafetyEnforcer(safety_limit_ratio=0.8, max_tokens=1000)
    message = Message(role="user", content=None)
    result = enforcer._enforce_message_safety_limit(message)
    assert result == message


def test_sequence_validator_empty_messages():
    """Test SequenceValidator with empty message list."""
    result = SequenceValidator.validate_compacted_sequence([])
    assert result is True


def test_intelligent_context_manager_empty_messages():
    """Test IntelligentContextManager with empty message list."""
    manager = IntelligentContextManager()
    result = manager.compact([])
    assert result == []


def test_intelligent_context_manager_none_config():
    """Test IntelligentContextManager with None config."""
    manager = IntelligentContextManager(config=None)
    assert manager.config is not None


if __name__ == "__main__":
    test_content_extractor_empty_patterns()
    print("✓ test_content_extractor_empty_patterns")
    
    test_content_extractor_none_content()
    print("✓ test_content_extractor_none_content")
    
    test_message_safety_enforcer_none_message()
    print("✓ test_message_safety_enforcer_none_message")
    
    test_message_safety_enforcer_none_content()
    print("✓ test_message_safety_enforcer_none_content")
    
    test_sequence_validator_empty_messages()
    print("✓ test_sequence_validator_empty_messages")
    
    test_intelligent_context_manager_empty_messages()
    print("✓ test_intelligent_context_manager_empty_messages")
    
    test_intelligent_context_manager_none_config()
    print("✓ test_intelligent_context_manager_none_config")
    
    print("\nAll edge case tests passed!")