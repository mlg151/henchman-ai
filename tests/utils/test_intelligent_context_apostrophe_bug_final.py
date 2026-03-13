"""Test for the apostrophe bug in intelligent_context.py.

This test demonstrates the bug where _is_apostrophe_in_word incorrectly
returns False for valid English contractions like "they've".
"""

import pytest
from henchman.utils.intelligent_context_parser import _ApostropheDetector, _ParserState


def test_is_apostrophe_in_word_theyve_bug():
    """Test the specific bug with 'they've' contraction."""
    parser = _ParserState()
    
    # The bug: "they've" at position 4 (the quote) should return True
    text = "they've"
    pos = 4  # Position of the quote character
    
    result = _ApostropheDetector.is_apostrophe_in_word(parser, text, pos)
    
    # This test will FAIL, demonstrating the bug
    assert result == True, f"Text '{text}' at position {pos}: expected True (apostrophe in contraction), got {result}"
    
    # Additional test cases that should all return True
    test_cases = [
        ("they've", 4, True),
        ("we've", 2, True),
        ("you've", 3, True),
        ("could've", 5, True),   # apostrophe at position 5, not 6
        ("should've", 6, True),  # apostrophe at position 6, not 7
        ("would've", 5, True),   # apostrophe at position 5, not 6
        ("might've", 5, True),   # apostrophe at position 5, not 6
        ("must've", 4, True),    # apostrophe at position 4, not 5
    ]
    
    for text, pos, expected in test_cases:
        result = _ApostropheDetector.is_apostrophe_in_word(parser, text, pos)
        assert result == expected, f"Text '{text}' at position {pos}: expected {expected}, got {result}"


def test_is_apostrophe_in_word_common_contractions():
    """Test all common English contraction patterns."""
    parser = _ParserState()
    
    test_cases = [
        # n't contractions
        ("don't", 3, True),
        ("can't", 3, True),
        ("won't", 3, True),
        ("isn't", 3, True),
        ("aren't", 4, True),
        ("wasn't", 4, True),
        ("weren't", 5, True),
        ("haven't", 5, True),
        ("hasn't", 4, True),
        ("hadn't", 4, True),
        ("shouldn't", 7, True),
        ("wouldn't", 6, True),
        ("couldn't", 6, True),
        ("mightn't", 6, True),
        ("mustn't", 5, True),
        
        # 's contractions
        ("it's", 2, True),
        ("he's", 2, True),
        ("she's", 3, True),   # apostrophe at position 3, not 4
        ("that's", 4, True),
        ("what's", 4, True),
        ("who's", 3, True),
        ("where's", 5, True), # apostrophe at position 5, not 6
        ("when's", 4, True),
        ("why's", 3, True),
        ("how's", 3, True),
        
        # 'm contractions
        ("I'm", 1, True),
        
        # 'll contractions
        ("I'll", 1, True),
        ("you'll", 3, True),
        ("he'll", 2, True),
        ("she'll", 3, True),   # apostrophe at position 3, not 4
        ("it'll", 2, True),
        ("we'll", 2, True),
        ("they'll", 4, True),  # apostrophe at position 4, not 5
        ("that'll", 4, True),
        ("what'll", 4, True),
        ("who'll", 3, True),
        
        # 're contractions
        ("you're", 3, True),
        ("we're", 2, True),
        ("they're", 4, True),  # apostrophe at position 4, not 5
        ("there're", 5, True), # apostrophe at position 5, not 6
        
        # 've contractions (BUG GROUP)
        ("I've", 1, True),
        ("you've", 3, True),
        ("we've", 2, True),
        ("they've", 4, True),    # apostrophe at position 4, not 5
        ("could've", 5, True),   # apostrophe at position 5, not 6
        ("should've", 6, True),  # apostrophe at position 6, not 7
        ("would've", 5, True),   # apostrophe at position 5, not 6
        ("might've", 5, True),   # apostrophe at position 5, not 6
        ("must've", 4, True),    # apostrophe at position 4, not 5
        
        # 'd contractions
        ("I'd", 1, True),
        ("you'd", 3, True),
        ("he'd", 2, True),
        ("she'd", 3, True),   # apostrophe at position 3, not 4
        ("it'd", 2, True),
        ("we'd", 2, True),
        ("they'd", 4, True),  # apostrophe at position 4, not 5
        ("that'd", 4, True),
        ("what'd", 4, True),
        ("who'd", 3, True),
        
        # Negative cases (should be False)
        ("a'hello", 1, False),  # Not a common contraction
        ("x'y", 1, False),  # Not a common contraction
        ("test'", 4, False),  # Quote at end of word
        ("'hello", 0, False),  # Quote at beginning
    ]
    
    for text, pos, expected in test_cases:
        result = _ApostropheDetector.is_apostrophe_in_word(parser, text, pos)
        assert result == expected, f"Text '{text}' at position {pos}: expected {expected}, got {result}"


if __name__ == "__main__":
    pytest.main([__file__, "-xvs"])