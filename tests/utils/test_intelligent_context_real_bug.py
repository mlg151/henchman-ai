"""Test for a real bug in intelligent_context.py."""

import pytest
from henchman.utils.intelligent_context import ContentExtractor, _ParserState


def test_parser_state_apostrophe_bug():
    """Test the _is_apostrophe_in_word method directly.
    
    The bug: when checking if a single quote is an apostrophe in a word,
    the method incorrectly handles certain edge cases with string prefixes.
    """
    parser = _ParserState()
    
    # Test case 1: ar'hello'
    # 'ar' is not a valid string prefix (contains 'a')
    # The method should check if 'ar' is a valid prefix, but it doesn't!
    # Because 'a' is alphanumeric, it skips the prefix check.
    text1 = "ar'hello'"
    i1 = 2  # position of '
    result1 = parser._is_apostrophe_in_word(text1, i1)
    print(f"ar'hello' at position {i1}: {result1}")
    # Currently returns True (thinks it's apostrophe)
    # But 'ar'hello' is invalid Python syntax
    
    # Test case 2: r'hello' (valid raw string)
    text2 = "r'hello'"
    i2 = 1  # position of '
    result2 = parser._is_apostrophe_in_word(text2, i2)
    print(f"r'hello' at position {i2}: {result2}")
    # Should return False (it's a string delimiter, not apostrophe)
    
    # Test case 3: x = r'hello'
    text3 = "x = r'hello'"
    i3 = 5  # position of ' (after r)
    result3 = parser._is_apostrophe_in_word(text3, i3)
    print(f"x = r'hello' at position {i3}: {result3}")
    # Should return False (string delimiter)
    
    # Test case 4: isn't (apostrophe in word)
    text4 = "isn't"
    i4 = 3  # position of '
    result4 = parser._is_apostrophe_in_word(text4, i4)
    print(f"isn't at position {i4}: {result4}")
    # Should return True (apostrophe in word)
    
    # Test case 5: ur'hello' (invalid Python 3 prefix)
    text5 = "ur'hello'"
    i5 = 2  # position of '
    result5 = parser._is_apostrophe_in_word(text5, i5)
    print(f"ur'hello' at position {i5}: {result5}")
    # Currently returns True (thinks it's apostrophe)
    # But ur'hello' is trying to be a string literal (invalid)
    
    # Test case 6: variable'string (invalid Python)
    text6 = "variable'string"
    i6 = 8  # position of '
    result6 = parser._is_apostrophe_in_word(text6, i6)
    print(f"variable'string at position {i6}: {result6}")
    # Should return True? variable'string is invalid Python syntax
    # But it looks like an apostrophe in a word
    
    # The bug is in the logic for when to check string prefixes.
    # Look at this condition in _is_apostrophe_in_word:
    # if j < i - 1 and (j < 0 or not (text[j].isalnum() or text[j] == "_")):
    # 
    # For ar'hello':
    # - j is position of 'a' (0)
    # - j < i - 1 is True (0 < 1)
    # - j < 0 is False
    # - text[j].isalnum() is True ('a' is alnum)
    # - So condition is False, we skip prefix check!
    # 
    # But we SHOULD check if 'ar' is a valid prefix (it's not).
    # The issue: we only check prefix if character before prefix
    # is NOT alnum/underscore. But 'a' IS alnum, so we skip.
    # This means ar'hello' is treated as apostrophe, not as
    # invalid string literal.


def test_code_block_extraction_with_bug():
    """Test how the bug affects code block extraction."""
    # Create a code block with ar'hello'
    content = '''```python
x = ar'hello'
y = r'world'
```'''
    
    result = ContentExtractor.extract_code_blocks(content)
    assert len(result) == 1, f"Expected 1 code block, got {len(result)}"
    code = result[0]
    print(f"Extracted code: {code}")
    
    # The bug might cause incorrect parsing of the code block
    # if ar'hello' is treated as apostrophe instead of string literal.
    # This could affect backtick counting and fence detection.


if __name__ == "__main__":
    pytest.main([__file__, "-v"])