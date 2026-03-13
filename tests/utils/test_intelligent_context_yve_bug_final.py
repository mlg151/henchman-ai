"""Test for the y've bug in _is_apostrophe_in_word method.

This test demonstrates a real bug where invalid contractions like "y've"
are incorrectly identified as apostrophes in words.
"""

import pytest
from henchman.utils.intelligent_context_parser import _ApostropheDetector, _ParserState


def test_is_apostrophe_in_word_yve_bug():
    """Test that _is_apostrophe_in_word correctly rejects invalid contraction 'y've'."""
    parser = _ParserState()
    
    # BUG: "y've" is NOT a valid English contraction but returns True
    text = "y've"
    pos = 1  # position of '
    result = _ApostropheDetector.is_apostrophe_in_word(parser, text, pos)
    
    # This should be False but is True (BUG)
    assert result == False, f"BUG: 'y've' should return False (invalid contraction), got {result}"


def test_is_apostrophe_in_word_valid_contractions_still_work():
    """Test that valid contractions still work correctly after fix."""
    parser = _ParserState()
    
    valid_contractions = [
        ("they've", 4, True),  # Valid: they've
        ("I've", 1, True),     # Valid: I've  
        ("you've", 3, True),   # Valid: you've
        ("we've", 2, True),    # Valid: we've
        ("could've", 5, True), # Valid: could've
        ("should've", 6, True), # Valid: should've
        ("would've", 5, True), # Valid: would've
        ("might've", 5, True), # Valid: might've
        ("must've", 4, True),  # Valid: must've
    ]
    
    for text, pos, expected in valid_contractions:
        result = _ApostropheDetector.is_apostrophe_in_word(parser, text, pos)
        assert result == expected, f"Text '{text}' at position {pos}: expected {expected}, got {result}"


def test_is_apostrophe_in_word_invalid_single_letter_contractions():
    """Test that invalid single-letter 'contractions' are rejected."""
    parser = _ParserState()
    
    invalid_contractions = [
        ("y've", 1, False),    # Invalid: not a real word (SPECIFIC BUG WE'RE FIXING)
        ("z've", 1, False),    # Invalid: not a real word
        ("q've", 1, False),    # Invalid: not a real word
        ("x've", 1, False),    # Invalid: not a real word
        # Note: 'a've', 'e've', 'i've', 'o've', 'u've' currently return True
        # but fixing those would require more extensive changes
        # We're only fixing the 'y've' bug per instructions
    ]
    
    for text, pos, expected in invalid_contractions:
        result = _ApostropheDetector.is_apostrophe_in_word(parser, text, pos)
        assert result == expected, f"Text '{text}' at position {pos}: expected {expected}, got {result}"


if __name__ == "__main__":
    pytest.main([__file__, "-xvs"])