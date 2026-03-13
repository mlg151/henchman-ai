"""Test for duplicate code bug in extract_critical_sections."""
import sys
sys.path.insert(0, 'src')

from henchman.utils.intelligent_context import ContentExtractor

def test_extract_critical_sections_no_duplicate_code_blocks():
    """Test that extract_critical_sections doesn't duplicate code blocks."""
    # Create a test content with a code block
    content = """
    Here is some text.
    
    ```python
    def hello():
        return "world"
    ```
    
    More text here.
    """
    
    sections = ContentExtractor.extract_critical_sections(content)
    
    # Count code blocks
    code_blocks = [s for s in sections if s.startswith("```python")]
    
    # Should have exactly 1 code block, not 2
    assert len(code_blocks) == 1, f"Expected 1 code block, got {len(code_blocks)}"
    print(f"✓ Test passed: Found {len(code_blocks)} code block(s)")
    
    # Also check total sections count is reasonable
    print(f"Total sections: {len(sections)}")
    
    # Verify no duplicate sections
    seen = set()
    duplicates = []
    for section in sections:
        if section in seen:
            duplicates.append(section)
        seen.add(section)
    
    assert len(duplicates) == 0, f"Found duplicate sections: {duplicates}"
    print("✓ No duplicate sections found")

if __name__ == "__main__":
    test_extract_critical_sections_no_duplicate_code_blocks()
    print("\nAll tests passed!")