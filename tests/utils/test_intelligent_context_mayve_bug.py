"""Test for bug in _is_apostrophe_in_word method rejecting valid contraction "may've".

This test demonstrates that _is_apostrophe_in_word incorrectly rejects
"may've" due to overly restrictive validation for 've contractions.
"""

import pytest
from henchman.utils.intelligent_context import _ParserState


def test_is_apostrophe_in_word_mayve_bug():
    """Test that _is_apostrophe_in_word accepts valid contraction "may've".
    
    BUG: The function rejects "may've" because it has special-case logic
    for 've contractions where char_before == 'y' that only accepts "they've".
    This is incorrect - "may've" is a valid English contraction.
    """
    parser = _ParserState()
    
    # Test 1: "may've" should be accepted
    text = "may've"
    i = text.find("'")  # Position of apostrophe
    
    # Should return True (valid contraction)
    result = parser._is_apostrophe_in_word(text, i)
    assert result == True, f"Text '{text}' at position {i}: expected True for valid contraction 'may've', got {result}"
    
    # Test 2: "they've" should still work
    text2 = "they've"
    i2 = text2.find("'")
    
    result2 = parser._is_apostrophe_in_word(text2, i2)
    assert result2 == True, f"Text '{text2}' at position {i2}: expected True, got {result2}"
    
    # Test 3: Other valid 've contractions should work
    test_cases = [
        ("I've", True),
        ("you've", True),
        ("we've", True),
        ("they've", True),
        ("could've", True),
        ("should've", True),
        ("would've", True),
        ("might've", True),
        ("must've", True),
        ("may've", True),  # Currently fails due to bug
        ("y've", False),   # Invalid - not a word
    ]
    
    for text, expected in test_cases:
        i = text.find("'")
        result = parser._is_apostrophe_in_word(text, i)
        assert result == expected, f"Text '{text}': expected {expected}, got {result}"


if __name__ == "__main__":
    pytest.main([__file__, "-xvs"])