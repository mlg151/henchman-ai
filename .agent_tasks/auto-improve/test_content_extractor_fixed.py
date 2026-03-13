"""Test edge cases for ContentExtractor to ensure code smell fixes don't break functionality."""

import pytest
from henchman.utils.intelligent_context import ContentExtractor


def test_extract_error_sections_empty():
    """Test error extraction with empty content."""
    result = ContentExtractor.extract_error_sections("")
    assert result == []


def test_extract_error_sections_no_errors():
    """Test error extraction with content containing no errors."""
    content = "This is normal text without any errors."
    result = ContentExtractor.extract_error_sections(content)
    assert result == []


def test_extract_error_sections_multiple_errors():
    """Test error extraction with multiple error types."""
    content = "Error: First error\nSome normal text\nException: Second error\nTraceback (most recent call last):\n  File \"test.py\", line 1\n    raise ValueError(\"test\")\nValueError: test\nwarning: This is a warning"
    result = ContentExtractor.extract_error_sections(content)
    assert len(result) >= 3  # Should find at least 3 error sections


def test_extract_tool_sections_empty():
    """Test tool extraction with empty content."""
    result = ContentExtractor.extract_tool_sections("")
    assert result == []


def test_extract_tool_sections_no_tools():
    """Test tool extraction with content containing no tools."""
    content = "This is normal text without any tool calls."
    result = ContentExtractor.extract_tool_sections(content)
    assert result == []


def test_extract_tool_sections_multiple_tools():
    """Test tool extraction with multiple tool calls."""
    content = "Tool call: read_file {\"path\": \"test.txt\"}\nSome normal text\nCalling tool: write_file {\"path\": \"output.txt\", \"content\": \"hello\"}\nExecuting: shell {\"command\": \"ls\"}\nFunction: test_function {\"arg\": \"value\"}"
    result = ContentExtractor.extract_tool_sections(content)
    assert len(result) >= 4  # Should find at least 4 tool sections


def test_extract_code_blocks_empty():
    """Test code block extraction with empty content."""
    result = ContentExtractor.extract_code_blocks("")
    assert result == []


def test_extract_code_blocks_no_code():
    """Test code block extraction with no code blocks."""
    content = "This is text without code blocks."
    result = ContentExtractor.extract_code_blocks(content)
    assert result == []


def test_extract_code_blocks_with_language():
    """Test code block extraction with language specification."""
    content = "Some text\n```python\ndef hello():\n    return \"world\"\n```\nMore text\n```\nNo language specified\n```"
    result = ContentExtractor.extract_code_blocks(content)
    assert len(result) == 2
    assert any("def hello()" in block for block in result)
    assert any("No language specified" in block for block in result)


def test_extract_sections_invalid_pattern():
    """Test extract_sections with invalid pattern name."""
    with pytest.raises(ValueError, match="Unknown pattern name"):
        ContentExtractor.extract_sections("content", "invalid_pattern")


def test_extract_sections_valid_patterns():
    """Test extract_sections with valid pattern names."""
    content = "Error: test\nTool call: test"
    
    error_result = ContentExtractor.extract_sections(content, "error")
    tool_result = ContentExtractor.extract_sections(content, "tool")
    
    assert isinstance(error_result, list)
    assert isinstance(tool_result, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])