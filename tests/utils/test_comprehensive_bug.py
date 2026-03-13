"""Comprehensive test to find bugs in extract_code_blocks."""

from henchman.utils.intelligent_context import ContentExtractor


def test_nested_code_blocks_in_strings():
    """Test code blocks that contain strings with backticks."""
    # String containing backticks inside a code block
    content = '''```python
print("```")
```'''
    result = ContentExtractor.extract_code_blocks(content)
    print(f"Test 1 result: {result}")
    assert len(result) == 1, f"Expected 1 code block, got {len(result)}"
    assert 'print("```")' in result[0], f"String with backticks not preserved: {result[0]}"


def test_malformed_code_block_no_closing():
    """Test malformed code block with no closing backticks."""
    content = '''Some text
```python
print("hello")
More text without closing backticks'''
    result = ContentExtractor.extract_code_blocks(content)
    print(f"Test 2 result: {result}")
    # Should return empty list or handle gracefully
    # Currently returns empty list
    assert len(result) == 0, f"Expected 0 code blocks for malformed input, got {len(result)}"


def test_code_block_with_backticks_in_comments():
    """Test code block with backticks in comments."""
    content = '''```python
# This is a comment with `backticks`
print("hello")
```'''
    result = ContentExtractor.extract_code_blocks(content)
    print(f"Test 3 result: {result}")
    assert len(result) == 1, f"Expected 1 code block, got {len(result)}"
    assert '# This is a comment with `backticks`' in result[0], f"Comment with backticks not preserved: {result[0]}"


def test_consecutive_code_blocks():
    """Test consecutive code blocks without separating text."""
    content = '''```python
print("first")
```
```python
print("second")
```'''
    result = ContentExtractor.extract_code_blocks(content)
    print(f"Test 4 result: {result}")
    assert len(result) == 2, f"Expected 2 code blocks, got {len(result)}"
    assert 'print("first")' in result[0], f"First block not extracted: {result[0]}"
    assert 'print("second")' in result[1], f"Second block not extracted: {result[1]}"


def test_code_block_with_unicode():
    """Test code block with Unicode characters."""
    content = '''```python
# Unicode string
s = "Hello 🐍"
print(s)
```'''
    result = ContentExtractor.extract_code_blocks(content)
    print(f"Test 5 result: {result}")
    assert len(result) == 1, f"Expected 1 code block, got {len(result)}"
    assert 's = "Hello 🐍"' in result[0], f"Unicode string not preserved: {result[0]}"


def test_raw_string_with_odd_backslashes():
    """Test raw string with odd number of backslashes before quote."""
    # r'\\\"' - three backslashes then quote
    # In raw string: \\\" = backslash, backslash, escaped quote
    content = '''```python
s = r'\\\\\\"'
```'''
    result = ContentExtractor.extract_code_blocks(content)
    print(f"Test 6 result: {result}")
    assert len(result) == 1, f"Expected 1 code block, got {len(result)}"
    # Hard to test exactly due to escaping


if __name__ == "__main__":
    tests = [
        test_nested_code_blocks_in_strings,
        test_malformed_code_block_no_closing,
        test_code_block_with_backticks_in_comments,
        test_consecutive_code_blocks,
        test_code_block_with_unicode,
        test_raw_string_with_odd_backslashes,
    ]
    
    for i, test in enumerate(tests, 1):
        try:
            test()
            print(f"Test {i} passed")
        except AssertionError as e:
            print(f"Test {i} failed: {e}")
        except Exception as e:
            print(f"Test {i} error: {e}")