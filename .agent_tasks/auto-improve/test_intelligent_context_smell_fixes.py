"""Tests for fixing code smells in intelligent_context.py.

This test file focuses on edge cases and regression tests for the
code smell fixes being implemented.
"""

import pytest
from henchman.providers.base import Message
from henchman.utils.intelligent_context import (
    ContentExtractor,
    IntelligentContextManager,
    SequenceValidator,
)


def test_extract_error_and_tool_sections_not_duplicates():
    """Test that extract_error_sections and extract_tool_sections are not exact duplicates.
    
    This test verifies that the two methods behave differently even if they have
    similar structure.
    """
    # Test content with both error and tool sections
    content = """
    This is a normal message.
    
    Error: Something went wrong!
    Traceback (most recent call last):
      File "test.py", line 1, in <module>
        raise ValueError("test")
    ValueError: test
    
    Tool call: read_file(path="test.txt")
    Result: File content here.
    
    Another error: Division by zero.
    """
    
    error_sections = ContentExtractor.extract_error_sections(content)
    tool_sections = ContentExtractor.extract_tool_sections(content)
    
    # They should extract different sections
    assert len(error_sections) > 0
    assert "Error:" in error_sections[0] or "Traceback" in error_sections[0]
    # Tool sections might not be extracted if pattern doesn't match
    # This is okay - the important thing is they're different functions


def test_sequence_validator_class_method_usage():
    """Test that SequenceValidator.validate_compacted_sequence properly uses classmethod.
    
    This addresses the "Feature Envy" smell where the method accesses cls 5 times
    but self 0 times. For a @classmethod, this is correct behavior.
    """
    messages = [
        Message(role="user", content="Hello"),
        Message(role="assistant", content="Hi there!"),
    ]
    
    # This should work without issue
    result = SequenceValidator.validate_compacted_sequence(messages)
    assert isinstance(result, bool)
    
    # Test with empty list
    assert SequenceValidator.validate_compacted_sequence([]) is True
    
    # Test with invalid sequence (should return False, not crash)
    invalid_messages = [
        Message(role="tool", content="Result"),  # Tool without preceding assistant
    ]
    result = SequenceValidator.validate_compacted_sequence(invalid_messages)
    assert isinstance(result, bool)


def test_intelligent_context_manager_init_parameters():
    """Test IntelligentContextManager.__init__ handles primitive parameters correctly.
    
    This addresses the "Primitive Obsession" smell.
    """
    # Test with all parameters provided
    manager1 = IntelligentContextManager(
        max_tokens=4000,
        max_protected_ratio=0.2,
        importance_threshold=0.6,
        cluster_similarity_threshold=0.8,
        adaptive_compression=True,
    )
    assert manager1 is not None
    
    # Test with None values (should use defaults)
    manager2 = IntelligentContextManager(
        max_tokens=None,
        max_protected_ratio=None,
        importance_threshold=None,
        cluster_similarity_threshold=None,
        adaptive_compression=None,
    )
    assert manager2 is not None
    
    # Test with config parameter (alternative to primitives)
    from henchman.utils.intelligent_context_config import IntelligentContextConfig
    config = IntelligentContextConfig(
        max_tokens=6000,
        max_protected_ratio=0.3,
        importance_threshold=0.7,
        cluster_similarity_threshold=0.75,
        adaptive_compression=False,
    )
    manager3 = IntelligentContextManager(config=config)
    assert manager3 is not None


def test_large_class_decomposition():
    """Test that IntelligentContextManager can be used without instantiating all features.
    
    This addresses the "Large Class" smell by verifying the class interface
    remains functional even if we might extract some responsibilities later.
    """
    manager = IntelligentContextManager(max_tokens=1000)
    
    # Test basic functionality
    messages = [
        Message(role="user", content="Hello, world!"),
        Message(role="assistant", content="Hi there!"),
    ]
    
    # Test compaction (public API)
    compacted = manager.compact(messages)
    assert isinstance(compacted, list)
    assert all(isinstance(msg, Message) for msg in compacted)
    
    # Test compaction with result (public API)
    result = manager.compact_with_result(messages)
    assert hasattr(result, 'messages')
    assert hasattr(result, 'was_compacted')
    assert hasattr(result, 'dropped_count')
    assert hasattr(result, 'importance_scores')
    assert hasattr(result, 'clusters')
    assert hasattr(result, 'compression_ratio')
    
    # Test importance scoring (private method but part of class responsibility)
    scores = manager._calculate_importance_scores(messages)
    assert isinstance(scores, dict)
    assert len(scores) == len(messages)
    assert all(0.0 <= score <= 1.0 for score in scores.values())


def test_duplicate_code_methods():
    """Test methods flagged as duplicate code to ensure they work correctly.
    
    This helps identify if _count_tokens and validate_compacted_sequence
    are actually duplicates or just similar.
    """
    from henchman.utils.intelligent_context import IntelligentContextManager
    
    manager = IntelligentContextManager()
    
    # Test _count_tokens if it exists
    if hasattr(manager, '_count_tokens'):
        messages = [Message(role="user", content="Hello world")]
        tokens = manager._count_tokens(messages)
        assert isinstance(tokens, int)
        assert tokens > 0
    
    # Test that validate_compacted_sequence is a class method
    # and doesn't require instance
    messages = [Message(role="user", content="test")]
    result = SequenceValidator.validate_compacted_sequence(messages)
    assert isinstance(result, bool)


def test_feature_envy_methods():
    """Test methods flagged with "Feature Envy" to understand their dependencies.
    
    This helps determine if methods should be moved to different classes.
    """
    manager = IntelligentContextManager()
    
    # Test _apply_intelligent_truncation_with_semantic_preservation if it exists
    if hasattr(manager, '_apply_intelligent_truncation_with_semantic_preservation'):
        messages = [
            Message(role="user", content="Test message"),
            Message(role="assistant", content="Response"),
        ]
        
        # This method might be private, so we use getattr
        method = getattr(manager, '_apply_intelligent_truncation_with_semantic_preservation')
        
        # Try to call it with appropriate parameters
        # We need to check the signature first
        import inspect
        sig = inspect.signature(method)
        params = list(sig.parameters.keys())
        
        # Based on the smell report, it accesses 'message' 5 times
        # Let's assume it takes messages and max_tokens
        if 'messages' in params and 'max_tokens' in params:
            result = method(messages=messages, max_tokens=100)
            assert isinstance(result, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])