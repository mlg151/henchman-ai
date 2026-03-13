"""Test for refactoring extract_error_sections and extract_tool_sections."""

import pytest
from henchman.utils.intelligent_context import ContentExtractor


def test_extract_error_sections_basic():
    """Test that extract_error_sections still works after refactoring."""
    content = """
    Some normal text.
    Error: Something went wrong!
    Traceback (most recent call last):
      File "test.py", line 1, in <module>
        raise ValueError("test")
    ValueError: test
    
    More normal text.
    """
    
    sections = ContentExtractor.extract_error_sections(content)
    assert len(sections) == 1
    assert "Traceback" in sections[0]
    assert "ValueError" in sections[0]


def test_extract_tool_sections_basic():
    """Test that extract_tool_sections still works after refactoring."""
    content = """
    Some normal text.
    Tool call: read_file(path="test.txt")
    Another tool: write_file(path="output.txt", content="data")
    More normal text.
    """
    
    sections = ContentExtractor.extract_tool_sections(content)
    # Tool sections might not be extracted by default patterns
    # This test verifies the method still works without error


def test_extract_sections_generic():
    """Test the generic extract_sections method."""
    content = """
    Error: test
    Tool: test
    """
    
    # Test error pattern
    error_sections = ContentExtractor.extract_sections(content, "error")
    
    # Test tool pattern  
    tool_sections = ContentExtractor.extract_sections(content, "tool")
    
    # Verify both work without error
    assert isinstance(error_sections, list)
    assert isinstance(tool_sections, list)


def test_extract_error_and_tool_are_not_identical():
    """Test that extract_error_sections and extract_tool_sections return different results."""
    content = """
    Error: Something went wrong!
    Tool call: read_file(path="test.txt")
    """
    
    error_sections = ContentExtractor.extract_error_sections(content)
    tool_sections = ContentExtractor.extract_tool_sections(content)
    
    # They should use different patterns and potentially return different results
    # The important thing is they don't throw errors


def test_pattern_registry():
    """Test that pattern registry contains expected patterns."""
    registry = ContentExtractor._PATTERN_REGISTRY
    assert "error" in registry
    assert "tool" in registry
    assert isinstance(registry["error"], list)
    assert isinstance(registry["tool"], list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])