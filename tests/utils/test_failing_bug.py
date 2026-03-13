"""Test to expose a real bug in extract_code_blocks."""

from henchman.utils.intelligent_context import ContentExtractor


def test_code_block_with_trailing_backslash():
    """Test code block ending with backslash at end of content."""
    # This might expose the escape_next state bug
    content = '''```python
print("hello") \\
```'''
    result = ContentExtractor.extract_code_blocks(content)
    print(f"Result: {result}")
    assert len(result) == 1, f"Expected 1 code block, got {len(result)}"
    # Should preserve the line continuation
    assert 'print("hello") \\' in result[0], f"Line continuation not preserved: {result[0]}"


def test_nested_backticks_in_raw_string():
    """Test raw string containing backticks that look like code block markers."""
    content = '''```python
s = r"""
```
This is not a code block
```
"""
```'''
    result = ContentExtractor.extract_code_blocks(content)
    print(f"Result length: {len(result)}")
    # Should extract ONE code block, not get confused by backticks in raw string
    assert len(result) == 1, f"Expected 1 code block, got {len(result)}"
    # The raw string should be preserved
    assert 'r"""' in result[0], f"Raw string not preserved: {result[0][:100]}..."


def test_consecutive_backticks_in_code():
    """Test code with consecutive backticks that aren't markers."""
    content = '''```python
# Comment with ``` backticks
print("`hello`")
```'''
    result = ContentExtractor.extract_code_blocks(content)
    print(f"Result: {result}")
    assert len(result) == 1, f"Expected 1 code block, got {len(result)}"
    assert '# Comment with ``` backticks' in result[0], f"Comment with backticks not preserved: {result[0]}"


if __name__ == "__main__":
    test_code_block_with_trailing_backslash()
    print("Test 1 passed")
    test_nested_backticks_in_raw_string()
    print("Test 2 passed")
    test_consecutive_backticks_in_code()
    print("Test 3 passed")