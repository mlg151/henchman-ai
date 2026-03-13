"""Test for the Four Lenses bug in _is_apostrophe_in_word method.

This test demonstrates the bug where _is_apostrophe_in_word incorrectly
checks text[i-1] when i == 0 after negative index conversion.
"""

import pytest
from henchman.utils.intelligent_context_parser import _ApostropheDetector, _ParserState


def test_is_apostrophe_in_word_negative_index_at_start_bug():
    """Test that _is_apostrophe_in_word handles negative index pointing to first character correctly.
    
    BUG: When i = -len(text) (points to first character), after conversion i = 0.
    The method then checks text[i-1] which is text[-1] (last character) instead
    of returning False because there's no character before position 0.
    """
    parser = _ParserState()
    
    # Test 1: Quote at position 0 (first character) with negative index
    text = "'hello"  # Quote at position 0
    i = -6  # -len(text) = -6, points to first character "'"
    
    # Expected: Should return False because quote is at position 0 (no character before it)
    # Actual bug: Accesses text[-1] (last character 'o') and may return True if 'o' is alnum
    result = _ApostropheDetector.is_apostrophe_in_word(parser, text, i)
    assert result == False, f"Text '{text}' at position {i} (first char): expected False (no char before), got {result}"
    
    # Test 2: Same test with positive index
    result2 = _ApostropheDetector.is_apostrophe_in_word(parser, text, 0)
    assert result2 == False, f"Text '{text}' at position 0: expected False, got {result2}"
    
    # Test 3: String where last character is alnum (exposes the bug more clearly)
    text3 = "'test"  # Quote at position 0, last character 't' is alnum
    i3 = -5  # -len(text3) = -5
    
    result3 = _ApostropheDetector.is_apostrophe_in_word(parser, text3, i3)
    assert result3 == False, f"Text '{text3}' at position {i3}: expected False, got {result3}"
    
    # Test 4: Empty string (edge case)
    result4 = _ApostropheDetector.is_apostrophe_in_word(parser, "", 0)
    assert result4 == False, f"Empty string at position 0: expected False, got {result4}"
    
    # Test 5: Single quote character
    result5 = _ApostropheDetector.is_apostrophe_in_word(parser, "'", 0)
    assert result5 == False, f"Text \"'\" at position 0: expected False, got {result5}"
    
    # Test 6: String starting with quote followed by letter
    text6 = "'a"  # Quote at position 0, 'a' at position 1
    result6 = _ApostropheDetector.is_apostrophe_in_word(parser, text6, 0)
    assert result6 == False, f"Text '{text6}' at position 0: expected False, got {result6}"


def test_is_apostrophe_in_word_regular_cases_still_work():
    """Test that regular cases still work correctly after fix."""
    parser = _ParserState()
    
    # Valid apostrophe cases
    assert _ApostropheDetector.is_apostrophe_in_word(parser, "don't", 3) == True
    assert _ApostropheDetector.is_apostrophe_in_word(parser, "can't", 3) == True
    assert _ApostropheDetector.is_apostrophe_in_word(parser, "it's", 2) == True
    
    # Not apostrophe cases
    assert _ApostropheDetector.is_apostrophe_in_word(parser, "x = 'hello'", 4) == False
    assert _ApostropheDetector.is_apostrophe_in_word(parser, "print('test')", 6) == False
    assert _ApostropheDetector.is_apostrophe_in_word(parser, "a'hello", 1) == False


if __name__ == "__main__":
    pytest.main([__file__, "-xvs"])