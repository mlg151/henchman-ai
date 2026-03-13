"""Test refactoring of extract_error_sections and extract_tool_sections."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from henchman.utils.intelligent_context import ContentExtractor

def test_extractor_methods_exist():
    """Test that extractor methods exist and are callable."""
    assert hasattr(ContentExtractor, 'extract_error_sections')
    assert hasattr(ContentExtractor, 'extract_tool_sections')
    assert callable(ContentExtractor.extract_error_sections)
    assert callable(ContentExtractor.extract_tool_sections)
    
    print("✓ Extractor methods exist")

def test_extractor_methods_work():
    """Test that extractor methods work correctly."""
    content = """
    Normal text here.
    Error: Something went wrong
    Tool call: read_file path="test.txt"
    Exception: Another error
    Calling tool: write_file
    """
    
    error_sections = ContentExtractor.extract_error_sections(content)
    tool_sections = ContentExtractor.extract_tool_sections(content)
    
    assert isinstance(error_sections, list)
    assert isinstance(tool_sections, list)
    
    # Should extract errors
    assert any("Error:" in section for section in error_sections)
    assert any("Exception:" in section for section in error_sections)
    
    # Should extract tools
    assert any("Tool call:" in section for section in tool_sections)
    assert any("Calling tool:" in section for section in tool_sections)
    
    print("✓ Extractor methods work correctly")

def test_extractor_methods_are_different():
    """Test that error and tool extractors return different results."""
    content = """
    Error: test error
    Tool call: test tool
    """
    
    error_sections = ContentExtractor.extract_error_sections(content)
    tool_sections = ContentExtractor.extract_tool_sections(content)
    
    # They should extract different things
    assert len(error_sections) == 1
    assert len(tool_sections) == 1
    assert "Error:" in error_sections[0]
    assert "Tool call:" in tool_sections[0]
    
    print("✓ Extractor methods return different results")

def test_extract_sections_method():
    """Test the underlying extract_sections method."""
    content = "Error: test\nTool call: test"
    
    # Test error extraction via extract_sections
    error_sections = ContentExtractor.extract_sections(content, "error")
    assert isinstance(error_sections, list)
    assert len(error_sections) == 1
    assert "Error:" in error_sections[0]
    
    # Test tool extraction via extract_sections
    tool_sections = ContentExtractor.extract_sections(content, "tool")
    assert isinstance(tool_sections, list)
    assert len(tool_sections) == 1
    assert "Tool call:" in tool_sections[0]
    
    print("✓ Underlying extract_sections method works")

if __name__ == "__main__":
    test_extractor_methods_exist()
    test_extractor_methods_work()
    test_extractor_methods_are_different()
    test_extract_sections_method()
    print("\n✅ All tests passed!")