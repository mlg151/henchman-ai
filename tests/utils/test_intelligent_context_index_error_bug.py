"""Test for index error bug in intelligent_context.py.

This test demonstrates that _is_apostrophe_in_word can raise IndexError
when called with an out-of-bounds position.
"""

import pytest
from henchman.utils.intelligent_context_parser import _ApostropheDetector, _ParserState


def test_is_apostrophe_in_word_index_error():
    """Test that _is_apostrophe_in_word returns False for out-of-bounds index."""
    parser = _ParserState()
    
    text = "hello"
    
    # Test with i >= len(text) - should return False, not raise IndexError
    result = _ApostropheDetector.is_apostrophe_in_word(parser, text, 5)  # len(text) = 5, so index 5 is out of bounds
    assert result == False, f"Text '{text}' at position 5 (out of bounds): expected False, got {result}"
    
    result = _ApostropheDetector.is_apostrophe_in_word(parser, text, 10)  # Definitely out of bounds
    assert result == False, f"Text '{text}' at position 10 (out of bounds): expected False, got {result}"
    
    # Test with i = len(text) - 1 (last character) - should work
    # Last character is 'o', not a quote, so should return False
    result = _ApostropheDetector.is_apostrophe_in_word(parser, text, 4)
    assert result == False, f"Text '{text}' at position 4 (last char 'o'): expected False, got {result}"
    
    # Test with negative i - should return False, not raise IndexError
    result = _ApostropheDetector.is_apostrophe_in_word(parser, text, -1)
    assert result == False, f"Text '{text}' at position -1 (negative index): expected False, got {result}"


def test_is_apostrophe_in_word_edge_cases():
    """Test edge cases for _is_apostrophe_in_word."""
    parser = _ParserState()
    
    # Empty string - position 0 is out of bounds (len=0)
    result = _ApostropheDetector.is_apostrophe_in_word(parser, "", 0)
    assert result == False, f"Empty string at position 0: expected False (out of bounds), got {result}"
    
    # Single character string with quote
    result = _ApostropheDetector.is_apostrophe_in_word(parser, "'", 0)
    # i == 0, so should return False (line 481: "or i == 0")
    assert result == False, f"Text \"'\" at position 0: expected False (i == 0), got {result}"
    
    # Two character string with quote at position 0
    result = _ApostropheDetector.is_apostrophe_in_word(parser, "'a", 0)
    # i == 0, so should return False
    assert result == False, f"Text \"'a\" at position 0: expected False (i == 0), got {result}"
    
    # Two character string with quote at position 1
    result = _ApostropheDetector.is_apostrophe_in_word(parser, "a'", 1)
    # i == 1, text[1] == "'", text[0] == "a" (isalnum), text[2] is out of bounds
    # Line 525: "if i + 1 >= len(text): return False"
    # i + 1 = 2, len(text) = 2, so i + 1 >= len(text) is True, returns False
    assert result == False, f"Text \"a'\" at position 1: expected False (no char after quote), got {result}"


if __name__ == "__main__":
    pytest.main([__file__, "-xvs"])