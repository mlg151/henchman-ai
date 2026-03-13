"""Edge case tests for ContentExtractor to address code smells."""

import pytest
from henchman.utils.intelligent_context import ContentExtractor


def test_extract_sections_empty_content():
    """Test extract_sections with empty content."""
    result = ContentExtractor.extract_error_sections("")
    assert result == []
    
    result = ContentExtractor.extract_tool_sections("")
    assert result == []


def test_extract_by_patterns_no_matches():
    """Test _extract_by_patterns with no matches."""
    result = ContentExtractor._extract_by_patterns("some content", [r"pattern1", r"pattern2"])
    assert result == []


def test_extract_by_patterns_with_matches():
    """Test _extract_by_patterns with matches."""
    content = "Error: something went wrong\nTool: do something"
    patterns = [r"Error:[^\n]*", r"Tool:[^\n]*"]
    result = ContentExtractor._extract_by_patterns(content, patterns)
    assert len(result) == 2
    assert "Error: something went wrong" in result
    assert "Tool: do something" in result


def test_extract_code_blocks_empty():
    """Test extract_code_blocks with empty content."""
    result = ContentExtractor.extract_code_blocks("")
    assert result == []


def test_extract_code_blocks_no_code():
    """Test extract_code_blocks with no code blocks."""
    content = "This is just text without any code blocks."
    result = ContentExtractor.extract_code_blocks(content)
    assert result == []


def test_extract_code_blocks_with_code():
    """Test extract_code_blocks with code blocks."""
    content = """Here's some text.
```python
def hello():
    return "world"
```
More text.
```bash
echo "hello"
```"""
    result = ContentExtractor.extract_code_blocks(content)
    assert len(result) == 2
    assert 'def hello():' in result[0]
    assert 'echo "hello"' in result[1]


def test_create_extractor_methods_creates_methods():
    """Test that _create_extractor_methods creates the expected methods."""
    # The method should have been called when the module was imported
    assert hasattr(ContentExtractor, "extract_error_sections")
    assert hasattr(ContentExtractor, "extract_tool_sections")
    
    # Test that the created methods work
    content = "Error: test error\nTool call: test tool"
    error_sections = ContentExtractor.extract_error_sections(content)
    tool_sections = ContentExtractor.extract_tool_sections(content)
    
    assert len(error_sections) == 1
    assert len(tool_sections) == 1
    assert "Error: test error" in error_sections[0]
    assert "Tool call: test tool" in tool_sections[0]