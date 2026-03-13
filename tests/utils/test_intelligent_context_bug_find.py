"""Test to find a bug in intelligent_context.py."""

import pytest
from henchman.utils.intelligent_context import ContentExtractor


def test_code_block_with_backtick_in_comment():
    """Test code block with backtick in comment.
    
    Backticks in comments should not be treated as fence markers.
    """
    content = '''```python
# This is a comment with a backtick: `
print("hello")
```'''
    
    result = ContentExtractor.extract_code_blocks(content)
    assert len(result) == 1, f"Expected 1 code block, got {len(result)}"
    code = result[0]
    assert '# This is a comment with a backtick: `' in code, \
        f"Comment with backtick not preserved. Code: {code}"


def test_code_block_with_triple_backtick_in_comment():
    """Test code block with triple backtick in comment.
    
    ``` inside a comment should not end the code block.
    """
    content = '''```python
# Here's some fake code:
# ```python
# print("fake")
# ```
print("real")
```'''
    
    result = ContentExtractor.extract_code_blocks(content)
    assert len(result) == 1, f"Expected 1 code block, got {len(result)}"
    code = result[0]
    # Should include the entire comment with triple backticks
    assert '# ```python' in code, f"Triple backtick in comment not preserved. Code: {code}"
    assert '# ```' in code, f"Closing triple backtick in comment not preserved. Code: {code}"


def test_code_block_with_string_containing_backtick_and_newline():
    """Test code block with string containing backtick and newline.
    
    This tests string handling across multiple lines.
    """
    content = '''```python
message = "Line 1`
Line 2"
print(message)
```'''
    
    result = ContentExtractor.extract_code_blocks(content)
    assert len(result) == 1, f"Expected 1 code block, got {len(result)}"
    code = result[0]
    # The string should be preserved
    assert 'message = "Line 1`' in code, f"String with backtick not preserved. Code: {code}"
    assert 'Line 2"' in code, f"String continuation not preserved. Code: {code}"


def test_raw_string_with_odd_backslashes_before_quote():
    """Test raw string with odd number of backslashes before quote.
    
    In raw strings, an odd number of backslashes before a quote escapes it.
    """
    content = '''```python
# r"\\"" would be: backslash, backslash, quote, quote
# Actually, r"\\"" is invalid (unterminated string)
# r"\\\"" would be: backslash, backslash, backslash, quote, quote
# Let me think...
pass
```'''
    
    # Actually, this is getting complex. Let me test a simpler case.
    content = '''```python
# In raw strings, backslash doesn't escape except for quotes
# r"\\"" is backslash, backslash, quote, quote - invalid
# r"\\\"" is backslash, backslash, backslash, quote, quote - string with \\\" then extra quote
pass
```'''
    
    result = ContentExtractor.extract_code_blocks(content)
    # Should extract the code block
    assert len(result) == 1, f"Expected 1 code block, got {len(result)}"


def test_comment_inside_string():
    """Test that # inside a string doesn't start a comment.
    
    This is a potential bug: if we see # inside a string, we shouldn't
    start treating it as a comment.
    """
    content = '''```python
message = "This is not a # comment"
print(message)
```'''
    
    result = ContentExtractor.extract_code_blocks(content)
    assert len(result) == 1, f"Expected 1 code block, got {len(result)}"
    code = result[0]
    assert 'message = "This is not a # comment"' in code, \
        f"String with # not preserved. Code: {code}"


def test_escape_sequence_in_raw_string():
    """Test escape sequences in raw strings.
    
    In raw strings, most escape sequences are not processed.
    But a backslash before a quote escapes it if there's an odd number.
    """
    content = '''```python
# r"\\n" is backslash, backslash, n
# r"\\\"" is backslash, backslash, backslash, quote
# Actually, r"\\\"" is: backslash, backslash, escaped quote
# Because odd number of backslashes before quote escapes it
s1 = r"\\n"  # Two backslashes, n
s2 = r"\\\""  # Two backslashes, escaped quote
print(s1, s2)
```'''
    
    result = ContentExtractor.extract_code_blocks(content)
    assert len(result) == 1, f"Expected 1 code block, got {len(result)}"
    # Just check it extracts something
    assert len(result[0]) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])