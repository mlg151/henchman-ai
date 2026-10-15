"""Test raw string backslash handling bug."""

from henchman.utils.intelligent_context import ContentExtractor


def test_raw_string_escaped_quote():
    """Test raw string with escaped quote: r'\"'"""
    # Actually r'\"' is valid - it's a raw string with backslash-quote
    # In raw strings, backslash doesn't escape except for quotes
    # So r'\"' is backslash followed by quote
    content = '''```python
s = r'\\"'
```'''
    result = ContentExtractor.extract_code_blocks(content)
    print(f"Result: {result[0] if result else 'No result'}")
    assert len(result) == 1, f"Expected 1 code block, got {len(result)}"
    # Should preserve r'\"'
    assert "r'\\\"'" in result[0] or 'r\'\\\\"\'' in result[0], f"Raw string not preserved: {result[0]}"


def test_raw_string_double_backslash():
    """Test raw string with double backslash: r'\\\\'"""
    content = '''```python
path = r'C:\\\\Users'
```'''
    result = ContentExtractor.extract_code_blocks(content)
    print(f"Result: {result[0] if result else 'No result'}")
    assert len(result) == 1, f"Expected 1 code block, got {len(result)}"
    assert "r'C:\\\\\\\\Users'" in result[0] or "r'C:\\\\Users'" in result[0], f"Raw string not preserved: {result[0]}"


if __name__ == "__main__":
    test_raw_string_escaped_quote()
    test_raw_string_double_backslash()
    print("All tests passed")
