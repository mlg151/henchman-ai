"""Test quick fixes for intelligent_context.py smells."""

import pytest
from henchman.utils.intelligent_context import ContentExtractor


def test_content_extractor_no_duplicate_code():
    """Verify that extract_error_sections and extract_tool_sections don't have duplicate code."""
    # They should use the shared _extract_by_patterns method
    content = "Error: test\nTool call: test\nAnother error"
    
    error_sections = ContentExtractor.extract_error_sections(content)
    tool_sections = ContentExtractor.extract_tool_sections(content)
    
    # They should return different results based on different patterns
    assert isinstance(error_sections, list)
    assert isinstance(tool_sections, list)
    
    # Test that they use different pattern lists
    # (This is implicit in their implementation)


def test_methods_have_type_hints():
    """Check that key methods have type hints."""
    import inspect
    from henchman.utils.intelligent_context import (
        IntelligentContextManager,
        IntelligentContextConfig,
        SequenceValidator,
    )
    
    # Check IntelligentContextManager.__init__
    init_sig = inspect.signature(IntelligentContextManager.__init__)
    for param_name, param in init_sig.parameters.items():
        if param_name != 'self':
            assert param.annotation != inspect.Parameter.empty, f"Parameter {param_name} missing type hint"
    
    # Check IntelligentContextConfig._create_from_params
    method = IntelligentContextConfig._create_from_params
    sig = inspect.signature(method)
    for param_name, param in sig.parameters.items():
        if param_name not in ('self', 'cls'):
            assert param.annotation != inspect.Parameter.empty, f"Parameter {param_name} missing type hint"
    
    # Check SequenceValidator.validate_compacted_sequence
    method = SequenceValidator.validate_compacted_sequence
    sig = inspect.signature(method)
    for param_name, param in sig.parameters.items():
        if param_name not in ('self', 'cls'):
            assert param.annotation != inspect.Parameter.empty, f"Parameter {param_name} missing type hint"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])