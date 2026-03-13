"""Test for the index error bug in intelligent_context.py.

This test demonstrates that _is_apostrophe_in_word raises IndexError
when called with i >= len(text), which is a bug.
"""

import pytest
from henchman.utils.intelligent_context_parser import _ApostropheDetector, _ParserState


def test_is_apostrophe_in_word_index_error_bug():
    """Test that _is_apostrophe_in_word handles i >= len(text) gracefully."""
    parser = _ParserState()
    
    text = "hello"  # len = 5
    
    # Test with i = len(text) - should return False (not raise IndexError)
    result = _ApostropheDetector.is_apostrophe_in_word(parser, text, 5)  # i = 5, len(text) = 5
    assert result == False, f"Expected False for i=5 (out of bounds), got {result}"
    
    # Test with i > len(text) - should return False (not raise IndexError)
    result = _ApostropheDetector.is_apostrophe_in_word(parser, text, 10)  # i = 10, len(text) = 5
    assert result == False, f"Expected False for i=10 (out of bounds), got {result}"
    
    # Test with i = len(text) - 1 (valid) - should return False (not a quote)
    result = _ApostropheDetector.is_apostrophe_in_word(parser, text, 4)  # i = 4, text[4] = 'o'
    assert result == False, f"Expected False for 'hello'[4] = 'o', got {result}"
    
    # Test with empty string and i = 0 - should return False (not raise IndexError)
    result = _ApostropheDetector.is_apostrophe_in_word(parser, "", 0)
    assert result == False, f"Expected False for empty string with i=0, got {result}"
    
    # Test with i = 0 and len(text) = 1 - should work
    result = _ApostropheDetector.is_apostrophe_in_word(parser, "a", 0)  # i = 0, text[0] = 'a'
    assert result == False, f"Expected False for 'a'[0] = 'a', got {result}"


def test_is_apostrophe_in_word_negative_index():
    """Test that _is_apostrophe_in_word handles negative indices.
    
    Negative indices wrap in Python, so text[-1] is valid.
    The method should handle this and return False (not a quote).
    """
    parser = _ParserState()
    
    text = "hello"
    
    # Test with i = -1 (last character) - should return False
    result = _ApostropheDetector.is_apostrophe_in_word(parser, text, -1)  # text[-1] = 'o'
    assert result == False, f"Expected False for 'hello'[-1] = 'o', got {result}"
    
    # Test with i = -2 - should return False
    result = _ApostropheDetector.is_apostrophe_in_word(parser, text, -2)  # text[-2] = 'l'
    assert result == False, f"Expected False for 'hello'[-2] = 'l', got {result}"
    
    # Test with i = -len(text) - should return False
    result = _ApostropheDetector.is_apostrophe_in_word(parser, text, -5)  # text[-5] = 'h'
    assert result == False, f"Expected False for 'hello'[-5] = 'h', got {result}"
    
    # Test with i < -len(text) - should return False (not raise IndexError)
    result = _ApostropheDetector.is_apostrophe_in_word(parser, text, -6)  # i = -6, len(text) = 5
    assert result == False, f"Expected False for i=-6 (out of bounds), got {result}"


if __name__ == "__main__":
    pytest.main([__file__, "-xvs"])