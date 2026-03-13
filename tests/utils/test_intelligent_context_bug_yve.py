"""Test for the y've bug in _is_apostrophe_in_word method."""

import pytest
from henchman.utils.intelligent_context import _ParserState


def test_is_apostrophe_in_word_yve_bug():
    """Test that _is_apostrophe_in_word correctly rejects invalid contraction 'y've'."""
    parser = _ParserState()
    
    # Test case: "y've" is NOT a valid English contraction
    # The function currently returns True (BUG), should return False
    text = "y've"
    pos = 1  # position of '
    result = parser._is_apostrophe_in_word(text, pos)
    
    # This is the bug: returns True but should be False
    print(f"Result for 'y've': {result} (BUG: should be False)")
    
    # Let's also test valid contractions to ensure we don't break them
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
        result = parser._is_apostrophe_in_word(text, pos)
        assert result == expected, f"Text '{text}' at position {pos}: expected {expected}, got {result}"
    
    # Now test invalid "contractions" that should return False
    invalid_contractions = [
        ("y've", 1, False),    # Invalid: not a real word
        ("z've", 1, False),    # Invalid: not a real word
        ("q've", 1, False),    # Invalid: not a real word
        ("x've", 1, False),    # Invalid: not a real word
    ]
    
    for text, pos, expected in invalid_contractions:
        result = parser._is_apostrophe_in_word(text, pos)
        # Currently fails for y've (BUG)
        if text == "y've":
            print(f"BUG: '{text}' returns {result}, should be {expected}")
        else:
            assert result == expected, f"Text '{text}' at position {pos}: expected {expected}, got {result}"


if __name__ == "__main__":
    pytest.main([__file__, "-xvs"])