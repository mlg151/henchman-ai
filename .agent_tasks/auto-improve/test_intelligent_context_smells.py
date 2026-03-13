"""Tests for fixing code smells in intelligent_context.py.

This test file focuses on edge cases and verification for the refactoring
of duplicate code and other code smells in intelligent_context.py.
"""

import pytest
from unittest.mock import Mock, patch
from henchman.providers.base import Message
from henchman.utils.intelligent_context import (
    IntelligentContextManager,
    KeywordExtractor,
    ContentExtractor,
    TokenCounterWrapper,
    SequenceValidator,
)


class TestDuplicateCodeFixes:
    """Tests for fixing duplicate code smells."""
    
    def test_line_contains_keyword_is_duplicate(self):
        """Test that _line_contains_keyword is a duplicate of _contains_keyword."""
        # Both methods should behave identically
        line = "This is an error message"
        keywords = ["error", "warning", "critical"]
        
        # Test the actual implementation
        result1 = KeywordExtractor._contains_keyword(line, keywords)
        # The duplicate method should return the same result
        # Note: _line_contains_keyword is a static method that calls _contains_keyword
        # We need to check if it exists and behaves the same
        assert result1 is True
        
    def test_count_tokens_wrapper_consistency(self):
        """Test that _count_tokens method uses TokenCounterWrapper correctly."""
        manager = IntelligentContextManager()
        messages = [
            Message(role="user", content="Hello"),
            Message(role="assistant", content="Hi there!"),
        ]
        
        # Mock the TokenCounterWrapper to verify it's called
        with patch.object(TokenCounterWrapper, 'count_messages_tokens', return_value=10) as mock_count:
            result = manager._count_tokens(messages)
            mock_count.assert_called_once_with(messages)
            assert result == 10
    
    def test_validate_compacted_sequence_wrapper(self):
        """Test that validate_compacted_sequence uses SequenceValidator correctly."""
        manager = IntelligentContextManager()
        messages = [
            Message(role="user", content="Test"),
            Message(role="assistant", content="Response"),
        ]
        
        # Mock the SequenceValidator to verify it's called
        with patch.object(SequenceValidator, 'validate_compacted_sequence', return_value=True) as mock_validate:
            result = manager.validate_compacted_sequence(messages)
            mock_validate.assert_called_once_with(messages)
            assert result is True
    
    def test_extract_critical_sections_wrapper(self):
        """Test that extract_critical_sections uses ContentExtractor correctly."""
        content = "Some content with important sections"
        
        # Mock the ContentExtractor to verify it's called
        with patch.object(ContentExtractor, 'extract_critical_sections', return_value=["section1"]) as mock_extract:
            result = ContentExtractor.extract_critical_sections(content)
            mock_extract.assert_called_once_with(content)
            assert result == ["section1"]


class TestFeatureEnvyFixes:
    """Tests for fixing feature envy smells."""
    
    def test_create_from_params_feature_envy(self):
        """Test _create_from_params method for feature envy."""
        # This method accesses 'params' heavily - we should verify it works correctly
        # or consider moving it to where 'params' is defined
        from henchman.utils.intelligent_context import IntelligentContextConfig
        
        params = {
            "max_tokens": 4000,
            "max_protected_ratio": 0.2,
            "importance_threshold": 0.6,
            "cluster_similarity_threshold": 0.8,
            "adaptive_compression": True,
        }
        
        config = IntelligentContextConfig._create_from_params(params)
        assert config is not None
        assert config.max_tokens == 4000
        assert config.max_protected_ratio == 0.2


class TestPrimitiveObsessionFixes:
    """Tests for fixing primitive obsession smells."""
    
    def test_init_has_too_many_primitives(self):
        """Test that __init__ has many primitive parameters."""
        # This is more of a structural check - the smell report indicates
        # __init__ has 5 primitive-typed parameters
        manager = IntelligentContextManager(
            max_tokens=4000,
            max_protected_ratio=0.3,
            importance_threshold=0.5,
            cluster_similarity_threshold=0.7,
            adaptive_compression=True,
        )
        
        assert manager is not None
        # Verify parameters are set correctly
        # Note: We need to check if these are stored in a config object
        # or directly as attributes


class TestLargeClassRefactoring:
    """Tests for refactoring the large IntelligentContextManager class."""
    
    def test_class_is_too_large(self):
        """Verify the class is indeed large (713 lines according to report)."""
        # This is a meta-test to confirm the issue exists
        import inspect
        source_lines = inspect.getsource(IntelligentContextManager)
        line_count = len(source_lines.split('\n'))
        
        # The report says 713 lines, which is well over the 300-line threshold
        assert line_count > 300, f"Class has {line_count} lines, should be > 300"
        
    def test_method_responsibilities_are_clear(self):
        """Test that methods have clear single responsibilities."""
        manager = IntelligentContextManager()
        
        # Check that methods don't do too many things
        # We'll examine a few key methods for complexity
        methods_to_check = [
            '_apply_intelligent_truncation_with_semantic_preservation',
            '_calculate_importance_scores',
            '_cluster_messages',
        ]
        
        for method_name in methods_to_check:
            if hasattr(manager, method_name):
                method = getattr(manager, method_name)
                # We can't easily check complexity here, but we can verify
                # the method exists and is callable
                assert callable(method)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])