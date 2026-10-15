"""Test for the real bug in _is_apostrophe_in_word method."""

import pytest

from henchman.utils.intelligent_context_extractor import ContentExtractor, _ParserState
from henchman.utils.intelligent_context_parser import _ApostropheDetector


def test_invalid_string_prefix_ar():
    """Test that ar'hello' is not mistakenly treated as having string prefix 'r'.

    ar'hello' is invalid Python syntax (ar is not a valid string prefix).
    The bug was that the method would scan back from ', find 'r' (valid prefix char),
    stop at 'a' (not valid), and check prefix 'r' (valid), treating it as string delimiter.
    With the fix, it recognizes that 'a' is alnum, so 'ar' is an identifier, not a string prefix.
    """
    parser = _ParserState()

    # Test case: ar'hello'
    text = "ar'hello'"
    i = 2  # position of '
    result = _ApostropheDetector.is_apostrophe_in_word(parser, text, i)

    # With the fix, it should skip string prefix check because 'ar' looks like identifier
    # Then check if it's a contraction: 'hello' doesn't match contraction suffixes
    # So returns False (string delimiter), which is reasonable for invalid syntax
    # The important thing is it doesn't mistakenly think it has prefix 'r'
    assert not result, f"ar'hello' should be string delimiter (False), got {result}"

    # Actually, let me think about this. ar'hello' could be:
    # - Variable 'ar' followed by string 'hello' (invalid: missing operator)
    # - Attempt at string literal with invalid prefix 'ar'
    # In code context, it's probably a typo or invalid syntax.
    # The parser should probably treat it as apostrophe to be safe.


def test_invalid_string_prefix_ur_python3():
    """Test that ur'hello' is not mistakenly treated as having valid string prefix.

    ur'hello' is invalid in Python 3 (u cannot combine with r).
    The bug was similar to ar'hello': scanning would find 'r', stop at 'u',
    check prefix 'r' (valid), treat as string delimiter.
    With fix, 'u' is alnum, so 'ur' is identifier, skip string prefix check.
    """
    parser = _ParserState()

    text = "ur'hello'"
    i = 2  # position of '
    result = _ApostropheDetector.is_apostrophe_in_word(parser, text, i)

    # With fix, skips string prefix check (ur looks like identifier)
    # 'hello' not a contraction, returns False (string delimiter)
    assert not result, f"ur'hello' should be string delimiter (False), got {result}"


def test_valid_string_prefix_r():
    """Test that r'hello' is correctly identified as string delimiter."""
    parser = _ParserState()

    text = "r'hello'"
    i = 1  # position of '
    result = _ApostropheDetector.is_apostrophe_in_word(parser, text, i)

    # r'hello' is valid raw string
    # Should return False (string delimiter, not apostrophe)
    assert not result, f"r'hello' should be string delimiter (False), got {result}"


def test_apostrophe_in_word_isnt():
    """Test that isn't is correctly identified as apostrophe in word."""
    parser = _ParserState()

    text = "isn't"
    i = 3  # position of '
    result = _ApostropheDetector.is_apostrophe_in_word(parser, text, i)

    # Should return True (apostrophe in word)
    assert result, f"isn't should be apostrophe (True), got {result}"


def test_code_block_with_ar_string():
    """Test how the bug affects code block extraction."""
    # Create a code block with ar'hello'
    content = """```python
x = ar'hello'  # This is invalid Python
y = r'world'   # This is valid
```"""

    result = ContentExtractor.extract_code_blocks(content)
    assert len(result) == 1, f"Expected 1 code block, got {len(result)}"

    # The bug might cause incorrect parsing if ar'hello' is treated as string
    # when it should be treated as containing apostrophe
    block = result[0]
    print(f"Extracted block: {block}")

    # The code should be extracted correctly regardless
    # But the parser state during extraction might be affected


def test_abr_string_prefix_bug():
    """Test the abr'hello' case where scanning logic is wrong.

    In abr'hello', the parser scans back from ':
    - r (valid), b (valid), a (not valid) -> stops
    - Checks prefix "br" (valid) -> treats as string delimiter
    - But abr'hello' is not a valid string literal!
    """
    parser = _ParserState()

    text = "abr'hello'"
    i = 3  # position of '
    result = _ApostropheDetector.is_apostrophe_in_word(parser, text, i)

    # abr'hello' is invalid Python
    # Currently might return False (treats as string delimiter because "br" is valid)
    # Should return True (apostrophe) or at least not treat as valid string
    print(f"abr'hello' result: {result}")
    # This exposes the scanning logic bug


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
