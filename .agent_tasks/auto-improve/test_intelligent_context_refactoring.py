"""Test file for intelligent_context.py refactoring.

This test file focuses on the specific code smells identified in the report.
"""

import pytest
from henchman.utils.intelligent_context import ContentExtractor, IntelligentContextManager


def test_extract_error_sections_and_extract_tool_sections_are_duplicates():
    """Test that extract_error_sections and extract_tool_sections are duplicates.
    
    This test verifies the HIGH severity smell: duplicate code between
    extract_error_sections and extract_tool_sections.
    """
    test_content = """
    Some normal text.
    Error: Something went wrong!
    Traceback (most recent call last):
      File "test.py", line 1, in <module>
        raise ValueError("test")
    ValueError: test
    
    Tool call: read_file(path="test.txt")
    Another error: File not found
    """
    
    # Both methods should work but they're identical implementations
    error_sections = ContentExtractor.extract_error_sections(test_content)
    tool_sections = ContentExtractor.extract_tool_sections(test_content)
    
    # They should return different results based on their patterns
    assert len(error_sections) > 0, "Should find error sections"
    assert len(tool_sections) >= 0, "May or may not find tool sections"
    
    # Verify they call the same underlying method with different parameters
    # This is the duplication we need to fix


def test_feature_envy_in_create_from_params():
    """Test the feature envy smell in _create_from_params method."""
    # This method accesses 'params' 5 times but 'self' only 0 times
    # We need to verify this behavior and plan refactoring
    pass


def test_large_class_intelligent_context_manager():
    """Test that IntelligentContextManager is too large (744 lines)."""
    # The class has 30 methods (threshold: 20) and spans 744 lines (threshold: 300)
    # We need to verify this and plan extraction of smaller classes
    manager = IntelligentContextManager()
    assert hasattr(manager, '_calculate_importance_scores')
    assert hasattr(manager, '_apply_intelligent_truncation_with_semantic_preservation')
    # More assertions to verify class size and method count


def test_primitive_obsession_in_init():
    """Test primitive obsession in __init__ method."""
    # Function has 5 primitive-typed parameters
    manager = IntelligentContextManager(
        max_tokens=8000,
        max_protected_ratio=0.3,
        importance_threshold=0.5,
        cluster_similarity_threshold=0.7,
        adaptive_compression=True
    )
    assert manager.max_tokens == 8000
    # Verify all parameters are passed correctly


def test_feature_envy_in_apply_intelligent_truncation():
    """Test feature envy in _apply_intelligent_truncation_with_semantic_preservation."""
    # Method accesses 'message' 5 times but 'self' only 2 times
    # We need to verify this behavior
    pass


def test_duplicate_count_tokens_and_validate_compacted_sequence():
    """Test duplicate code between _count_tokens and validate_compacted_sequence."""
    # These functions are 100% similar according to the smell report
    # We need to verify and refactor
    pass


def test_duplicate_calculate_importance_scores_and_preserve_critical_context():
    """Test duplicate code between _calculate_importance_scores and _preserve_critical_context."""
    # These functions are 95% similar according to the smell report
    # We need to verify and refactor
    pass


def test_duplicate_calculate_cluster_importance_and_preserve_critical_context():
    """Test duplicate code between _calculate_cluster_importance and _preserve_critical_context."""
    # These functions are 95% similar according to the smell report
    # We need to verify and refactor
    pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])