"""Test for potential bug in intelligent_context.py."""

from henchman.utils.intelligent_context import ContentExtractor


def test_extract_code_blocks_raw_string_with_escaped_quote():
    """Test raw string with escaped quote."""
    # In raw string r"\"", the backslash escapes the quote
    # So the string contains: backslash, quote
    # Not: quote (end of string)
    content = '''```python
s = r"\\""
print(s)
```'''
    blocks = ContentExtractor.extract_code_blocks(content)
    # This might fail because the parser might think the quote is escaped
    # and end the string incorrectly
    print(f"Blocks: {blocks}")
    if blocks:
        print(f"Block 0: {blocks[0]}")


def test_extract_code_blocks_triple_quote_at_end():
    """Test triple quote at end of content."""
    content = '''```python
s = """hello"""
```'''
    blocks = ContentExtractor.extract_code_blocks(content)
    print(f"Triple quote test: {blocks}")


def test_extract_code_blocks_nested_quotes():
    """Test nested quotes."""
    content = '''```python
s = "He said, 'Hello'"
print(s)
```'''
    blocks = ContentExtractor.extract_code_blocks(content)
    print(f"Nested quotes test: {blocks}")


if __name__ == "__main__":
    test_extract_code_blocks_raw_string_with_escaped_quote()
    test_extract_code_blocks_triple_quote_at_end()
    test_extract_code_blocks_nested_quotes()