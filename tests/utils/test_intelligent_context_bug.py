"""Test for the backslash escape bug in intelligent_context.py."""

from henchman.utils.intelligent_context_extractor import ContentExtractor


def test_escaped_quote_in_string():
    """Test that escaped quotes in strings don't break code block extraction.
    
    This test exposes the bug where escaped quotes are not properly skipped.
    """
    # Test 1: Regular string with escaped quote
    content1 = '''Some text before
```python
print("Hello\\"World")
```
Some text after'''
    
    result1 = ContentExtractor.extract_code_blocks(content1)
    assert len(result1) == 1, f"Expected 1 code block, got {len(result1)}. Escaped quote broke parsing."
    
    # Test 2: Raw string with escaped quote (odd number of backslashes)
    content2 = '''```python
print(r"Hello\\"World")
```'''
    
    result2 = ContentExtractor.extract_code_blocks(content2)
    assert len(result2) == 1, f"Expected 1 code block, got {len(result2)}. Raw string with escaped quote broke parsing."
    
    # Test 3: Complex case with multiple escaped quotes
    content3 = '''```python
text = "He said \\"Hello\\" and she said \\"Hi\\""
print(text)
```'''
    
    result3 = ContentExtractor.extract_code_blocks(content3)
    assert len(result3) == 1, f"Expected 1 code block, got {len(result3)}. Multiple escaped quotes broke parsing."
    
    # Test 4: Edge case - backslash at end of string
    content4 = '''```python
path = "C:\\\\Users\\\\"
print(path)
```'''
    
    result4 = ContentExtractor.extract_code_blocks(content4)
    assert len(result4) == 1, f"Expected 1 code block, got {len(result4)}. Backslash at end broke parsing."


def test_escaped_backtick_in_string():
    """Test that escaped backticks in strings don't break code block parsing."""
    # Test with escaped backtick in string
    content = '''```python
print("This is a backtick: `")
```'''
    
    result = ContentExtractor.extract_code_blocks(content)
    assert len(result) == 1, f"Expected 1 code block, got {len(result)}. Escaped backtick in string broke parsing."
    
    # Verify the backtick is preserved
    if result:
        assert "`" in result[0], "Backtick not preserved in extracted code"


if __name__ == "__main__":
    test_escaped_quote_in_string()
    test_escaped_backtick_in_string()
    print("All tests passed!")