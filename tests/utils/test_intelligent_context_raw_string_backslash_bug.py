"""Test for raw string backslash bug in intelligent_context.py.

This test demonstrates the bug where handle_backslash returns False
for escaped quotes in raw strings, causing the escaped quote to be
processed incorrectly.
"""

import pytest
from henchman.utils.intelligent_context import ContentExtractor, _ParserState


def test_raw_string_escaped_quote_does_not_end_string():
    """Test that escaped single quote in raw string doesn't end string prematurely.
    
    In a raw string r"\'", the backslash escapes the quote, so the quote
    should not end the string. However, if handle_backslash returns False
    (bug), the quote will be processed by _process_char and might end the string.
    """
    # Test with code block containing raw string with escaped quote
    content = '''```python
# Raw string with escaped single quote
text = r"\\'"
# Backticks after the escaped quote should be inside the string
more = r"\\'`backtick`"
print(text, more)
```'''
    
    result = ContentExtractor.extract_code_blocks(content)
    
    # Bug: The code block might not be extracted correctly if string ends prematurely
    # due to escaped quote being processed incorrectly
    assert len(result) == 1, f"Expected 1 code block, got {len(result)}: {result}"
    
    # The raw string should be preserved
    extracted = result[0]
    assert 'r"\\\'"' in extracted or 'r"\\' in extracted, \
        f"Raw string with escaped quote not preserved: {extracted}"
    
    # If bug exists, string might end at escaped quote, making `backtick` outside string
    # and potentially interfering with fence detection
    assert '`backtick`' in extracted, \
        f"Backticks after escaped quote not preserved: {extracted}"


def test_parser_state_handle_backslash_return_value():
    """Test that handle_backslash returns True when it sets escape_next in raw strings."""
    parser = _ParserState()
    
    # Test raw string scenario: r"\'"
    content = r"r\'"
    parser.in_string = True
    parser.raw_string = True
    parser.string_char = '"'
    
    # Position 1 is the backslash, next char is quote
    result = parser.handle_backslash(content, 1)
    
    # BUG: handle_backslash should return True because it sets escape_next = True
    # but currently returns False
    print(f"handle_backslash returned: {result}, escape_next: {parser.escape_next}")
    
    # This is the bug: returns False even though escape_next is True
    # The test will fail with current implementation
    assert result == True, \
        f"handle_backslash should return True when it sets escape_next, got {result}"
    assert parser.escape_next == True, \
        f"escape_next should be True for escaped quote in raw string"


def test_raw_string_with_escaped_quote_and_backticks_inside():
    """More comprehensive test with backticks inside raw string after escaped quote."""
    content = '''```python
# Complex case: raw string with escaped quote followed by backticks
path = r"C:\\\\Users\\\\test\\'`backtick`example"
print(path)
```'''
    
    result = ContentExtractor.extract_code_blocks(content)
    
    # Should extract full code block
    assert len(result) == 1, f"Expected 1 code block, got {len(result)}"
    
    # The backticks should be inside the string literal
    extracted = result[0]
    # Check that we have the raw string with backticks
    assert '`backtick`' in extracted, \
        f"Backticks inside raw string not preserved: {extracted}"


if __name__ == "__main__":
    # Run tests
    test_parser_state_handle_backslash_return_value()
    print("test_parser_state_handle_backslash_return_value passed!")
    
    test_raw_string_escaped_quote_does_not_end_string()
    print("test_raw_string_escaped_quote_does_not_end_string passed!")
    
    test_raw_string_with_escaped_quote_and_backticks_inside()
    print("test_raw_string_with_escaped_quote_and_backticks_inside passed!")
    
    print("\nAll tests passed!")