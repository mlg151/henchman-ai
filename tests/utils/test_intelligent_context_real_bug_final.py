"""Test for a real bug in intelligent_context.py.

This test demonstrates a real bug found through careful analysis.
"""

import pytest
from henchman.utils.intelligent_context_parser import _ApostropheDetector, _ParserState
from henchman.utils.intelligent_context_extractor import ContentExtractor


def test_is_valid_string_prefix_edge_cases():
    """Test edge cases for _is_valid_string_prefix."""
    parser = _ParserState()
    
    # Test all possible 1-character prefixes
    assert parser._is_valid_string_prefix('r'), "'r' should be valid"
    assert parser._is_valid_string_prefix('b'), "'b' should be valid"
    assert parser._is_valid_string_prefix('f'), "'f' should be valid"
    assert parser._is_valid_string_prefix('u'), "'u' should be valid"
    
    # Test all possible 2-character prefixes
    assert parser._is_valid_string_prefix('br'), "'br' should be valid"
    assert parser._is_valid_string_prefix('rb'), "'rb' should be valid"
    assert parser._is_valid_string_prefix('fr'), "'fr' should be valid"
    assert parser._is_valid_string_prefix('rf'), "'rf' should be valid"
    
    # Test invalid 2-character prefixes
    invalid_2char = ['fb', 'bf', 'ur', 'ru', 'ub', 'uf', 'bu', 'fu', 
                     'rr', 'bb', 'ff', 'uu', 'ar', 'ra', 'ab', 'ba']
    for prefix in invalid_2char:
        assert not parser._is_valid_string_prefix(prefix), f"'{prefix}' should be invalid"
    
    # Test 3-character prefixes (should all be invalid)
    assert not parser._is_valid_string_prefix('brr'), "'brr' should be invalid (too long)"
    assert not parser._is_valid_string_prefix('fbr'), "'fbr' should be invalid (too long)"
    
    # Test empty string
    assert not parser._is_valid_string_prefix(''), "Empty string should be invalid"
    
    # Test mixed case
    assert parser._is_valid_string_prefix('Br'), "'Br' should be valid (case-insensitive)"
    assert parser._is_valid_string_prefix('RB'), "'RB' should be valid (case-insensitive)"
    assert not parser._is_valid_string_prefix('UR'), "'UR' should be invalid"
    assert not parser._is_valid_string_prefix('RU'), "'RU' should be invalid"


def test_is_valid_raw_string_prefix_edge_cases():
    """Test edge cases for _is_valid_raw_string_prefix."""
    parser = _ParserState()
    
    # Test valid raw string prefixes (must contain 'r')
    assert parser._is_valid_raw_string_prefix('r'), "'r' should be valid"
    assert parser._is_valid_raw_string_prefix('br'), "'br' should be valid"
    assert parser._is_valid_raw_string_prefix('rb'), "'rb' should be valid"
    assert parser._is_valid_raw_string_prefix('fr'), "'fr' should be valid"
    assert parser._is_valid_raw_string_prefix('rf'), "'rf' should be valid"
    
    # Test invalid raw string prefixes (don't contain 'r' or are invalid combinations)
    invalid_raw = ['b', 'f', 'u', 'fb', 'bf', 'ur', 'ru', 'ub', 'uf', 'bu', 'fu']
    for prefix in invalid_raw:
        assert not parser._is_valid_raw_string_prefix(prefix), f"'{prefix}' should be invalid for raw strings"
    
    # Test that 'u' alone is not a valid raw string prefix (doesn't contain 'r')
    assert not parser._is_valid_raw_string_prefix('u'), "'u' should not be valid for raw strings"
    
    # Test mixed case
    assert parser._is_valid_raw_string_prefix('Br'), "'Br' should be valid (case-insensitive)"
    assert parser._is_valid_raw_string_prefix('RB'), "'RB' should be valid (case-insensitive)"
    assert not parser._is_valid_raw_string_prefix('UR'), "'UR' should be invalid"
    assert not parser._is_valid_raw_string_prefix('RU'), "'RU' should be invalid"


def test_apostrophe_detection_bug():
    """Test for apostrophe detection bug.
    
    BUG: The _is_apostrophe_in_word method may incorrectly identify
    string delimiters as apostrophes in certain edge cases.
    """
    parser = _ParserState()
    
    # Test cases where single quote should be a string delimiter, not apostrophe
    test_cases = [
        ("x = 'hello'", 4, False),  # String delimiter
        ("print('world')", 6, False),  # String delimiter
        ("don't", 3, True),  # Apostrophe in contraction
        ("can't", 3, True),  # Apostrophe in contraction
        ("it's", 2, True),  # Apostrophe in contraction
        ("we're", 2, True),  # Apostrophe in contraction
        ("I'm", 1, True),  # Apostrophe in contraction
        ("you'll", 3, True),  # Apostrophe in contraction
        ("they've", 4, True),  # Apostrophe in contraction (position 4, not 5)
        ("he'd", 2, True),  # Apostrophe in contraction
        ("a'hello", 1, False),  # Not a common English contraction
        ("word'_suffix", 4, False),  # Underscore after quote (rare, treat as string delimiter)
    ]
    
    for text, pos, expected in test_cases:
        result = _ApostropheDetector.is_apostrophe_in_word(parser, text, pos)
        assert result == expected, f"Text '{text}' at position {pos}: expected {expected}, got {result}"


def test_code_block_extraction_with_string_prefixes():
    """Test code block extraction with various string prefixes."""
    # Test with 'ur' prefix (invalid in Python 3, but might appear in code)
    content = '''```python
# This is Python 3 code, 'ur' is invalid
text = ur"invalid"  # Should not break parsing
```'''
    
    result = ContentExtractor.extract_code_blocks(content)
    assert len(result) == 1, f"Expected 1 code block, got {len(result)}"
    
    # Test with valid raw string prefix
    content2 = '''```python
text = r"raw string"
print(text)
```'''
    
    result2 = ContentExtractor.extract_code_blocks(content2)
    assert len(result2) == 1, f"Expected 1 code block, got {len(result2)}"


if __name__ == "__main__":
    pytest.main([__file__, "-xvs"])