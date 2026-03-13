"""Test file for intelligent_context.py refactoring."""

import pytest
from henchman.utils.intelligent_context import (
    ContentExtractor,
    IntelligentContextConstants,
    IntelligentContextConfig,
    IntelligentContextParams,
    PreservedContent,
    ConversationTypeDetector,
    ImportanceSorter,
    MessageSafetyEnforcer,
    TokenCounterWrapper,
    IntelligentTruncator,
    SequenceValidator,
    MessagePreserver,
    CompressionConfig,
    IntelligentCompactionResult,
    ResultCreationParams,
    SummaryGenerator,
    IntelligentContextManager,
)
from henchman.providers.base import Message


def test_content_extractor_duplicate_functions():
    """Test that extract_error_sections and extract_tool_sections work correctly."""
    test_content = """
    Some normal text.
    Traceback (most recent call last):
      File "test.py", line 1, in <module>
        raise ValueError("test")
    ValueError: test
    
    Tool call: read_file
    Calling tool: write_file
    
    Error: Something went wrong
    """
    
    error_sections = ContentExtractor.extract_error_sections(test_content)
    tool_sections = ContentExtractor.extract_tool_sections(test_content)
    
    # Should extract error sections
    assert any("Traceback" in s for s in error_sections)
    assert any("Error:" in s for s in error_sections)
    
    # Should extract tool sections
    assert any("Tool call:" in s for s in tool_sections)
    assert any("Calling tool:" in s for s in tool_sections)


def test_feature_envy_methods():
    """Test methods flagged for feature envy."""
    # Test _create_from_params method
    params = IntelligentContextParams(
        max_tokens=4000,
        max_protected_ratio=0.2,
        importance_threshold=0.6,
        cluster_similarity_threshold=0.8,
        adaptive_compression=True,
    )
    
    config = IntelligentContextConfig._create_from_params(params)
    assert config is not None
    assert config.max_tokens == 4000
    assert config.max_protected_ratio == 0.2


def test_large_class_intelligent_context_manager():
    """Test that IntelligentContextManager can be instantiated."""
    manager = IntelligentContextManager(
        max_tokens=8000,
        max_protected_ratio=0.3,
        importance_threshold=0.5,
        cluster_similarity_threshold=0.7,
        adaptive_compression=True,
        config=None,
    )
    assert manager is not None


def test_primitive_obsession_in_init():
    """Test the __init__ method with many primitive parameters."""
    manager = IntelligentContextManager(
        max_tokens=8000,
        max_protected_ratio=0.3,
        importance_threshold=0.5,
        cluster_similarity_threshold=0.7,
        adaptive_compression=True,
        config=None,
    )
    assert manager is not None


def test_validate_compacted_sequence():
    """Test the validate_compacted_sequence method."""
    messages = [
        Message(role="system", content="You are a helpful assistant."),
        Message(role="user", content="Hello"),
        Message(role="assistant", content="Hi there!"),
    ]
    
    # This is a class method that should work
    result = SequenceValidator.validate_compacted_sequence(messages)
    assert isinstance(result, bool)


def test_count_tokens_duplicate():
    """Test _count_tokens method for duplicate code detection."""
    messages = [
        Message(role="user", content="Hello world"),
        Message(role="assistant", content="Hi there"),
    ]
    
    manager = IntelligentContextManager(
        max_tokens=8000,
        max_protected_ratio=0.3,
        importance_threshold=0.5,
        cluster_similarity_threshold=0.7,
        adaptive_compression=True,
        config=None,
    )
    
    token_count = manager._count_tokens(messages)
    assert isinstance(token_count, int)


def test_calculate_importance_scores_duplicate():
    """Test _calculate_importance_scores method for duplicate code detection."""
    messages = [
        Message(role="user", content="Hello world"),
        Message(role="assistant", content="Hi there"),
    ]
    
    manager = IntelligentContextManager(
        max_tokens=8000,
        max_protected_ratio=0.3,
        importance_threshold=0.5,
        cluster_similarity_threshold=0.7,
        adaptive_compression=True,
        config=None,
    )
    
    scores = manager._calculate_importance_scores(messages)
    assert isinstance(scores, dict)
    assert len(scores) == len(messages)


if __name__ == "__main__":
    # Run tests
    test_content_extractor_duplicate_functions()
    print("✓ test_content_extractor_duplicate_functions passed")
    
    test_feature_envy_methods()
    print("✓ test_feature_envy_methods passed")
    
    test_large_class_intelligent_context_manager()
    print("✓ test_large_class_intelligent_context_manager passed")
    
    test_primitive_obsession_in_init()
    print("✓ test_primitive_obsession_in_init passed")
    
    test_validate_compacted_sequence()
    print("✓ test_validate_compacted_sequence passed")
    
    test_count_tokens_duplicate()
    print("✓ test_count_tokens_duplicate passed")
    
    test_calculate_importance_scores_duplicate()
    print("✓ test_calculate_importance_scores_duplicate passed")
    
    print("\nAll tests passed!")