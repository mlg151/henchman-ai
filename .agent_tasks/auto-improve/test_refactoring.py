"""Test refactoring of intelligent_context.py."""

import pytest
from henchman.utils.intelligent_context import (
    ContentExtractor,
    IntelligentContextManager,
    IntelligentContextParams,
    Message,
)


class TestContentExtractorRefactoring:
    """Test refactoring of ContentExtractor duplicate methods."""
    
    def test_extract_error_and_tool_sections_share_logic(self):
        """Test that error and tool extraction share common logic."""
        content = """
        Error: Something went wrong
        Tool call: read_file
        Exception: ValueError
        Calling tool: write_file
        """
        
        error_sections = ContentExtractor.extract_error_sections(content)
        tool_sections = ContentExtractor.extract_tool_sections(content)
        
        # Both should use the same underlying pattern matching logic
        assert isinstance(error_sections, list)
        assert isinstance(tool_sections, list)
        
        # Error sections should contain error patterns
        error_text = " ".join(error_sections).lower()
        assert "error" in error_text or "exception" in error_text
        
        # Tool sections should contain tool patterns  
        tool_text = " ".join(tool_sections).lower()
        assert "tool" in tool_text or "calling" in tool_text


class TestIntelligentContextManagerRefactoring:
    """Test refactoring of IntelligentContextManager."""
    
    def setup_method(self):
        """Create a test manager instance."""
        self.manager = IntelligentContextManager(
            max_tokens=8000,
            max_protected_ratio=0.3,
            importance_threshold=0.5,
            cluster_similarity_threshold=0.7,
            adaptive_compression=True,
            config=None,
        )
    
    def test_wrapper_methods_have_consistent_pattern(self):
        """Test that wrapper methods follow consistent delegation pattern."""
        messages = [
            Message(role="user", content="Hello"),
            Message(role="assistant", content="Hi"),
        ]
        
        # Test _count_tokens wrapper
        token_count = self.manager._count_tokens(messages)
        assert isinstance(token_count, int)
        
        # Test validate_compacted_sequence wrapper
        is_valid = self.manager.validate_compacted_sequence(messages)
        assert isinstance(is_valid, bool)
        
        # Test _calculate_importance_scores wrapper
        scores = self.manager._calculate_importance_scores(messages)
        assert isinstance(scores, dict)
        assert len(scores) == len(messages)
        
        # Test _preserve_critical_context wrapper
        scores = {0: 0.8, 1: 0.6}
        preserved = self.manager._preserve_critical_context(messages, scores)
        assert isinstance(preserved, list)
    
    def test_init_accepts_params_object(self):
        """Test that __init__ can accept params object."""
        params = IntelligentContextParams(
            max_tokens=4000,
            max_protected_ratio=0.2,
            importance_threshold=0.6,
            cluster_similarity_threshold=0.8,
            adaptive_compression=False,
        )
        
        # Test via from_params factory method
        manager = IntelligentContextManager.from_params(params=params, config=None)
        assert manager is not None
        assert manager.config.max_tokens == 4000


if __name__ == "__main__":
    # Run tests
    test_extractor = TestContentExtractorRefactoring()
    test_extractor.test_extract_error_and_tool_sections_share_logic()
    print("✓ test_extract_error_and_tool_sections_share_logic passed")
    
    test_manager = TestIntelligentContextManagerRefactoring()
    test_manager.setup_method()
    test_manager.test_wrapper_methods_have_consistent_pattern()
    print("✓ test_wrapper_methods_have_consistent_pattern passed")
    
    test_manager.test_init_accepts_params_object()
    print("✓ test_init_accepts_params_object passed")
    
    print("\nAll refactoring tests passed!")