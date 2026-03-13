"""Failing test for apostrophe bug in _is_apostrophe_in_word method."""

import pytest
from henchman.utils.intelligent_context import _ParserState


def test_apostrophe_after_digit():
    """Test that apostrophe after digit is recognized as apostrophe in word."""
    state = _ParserState()
    # "2024's" - apostrophe after digit should be recognized as apostrophe
    assert state._is_apostrophe_in_word("2024's", 4) == True, \
        "Apostrophe after digit should be recognized as apostrophe in word"


def test_apostrophe_after_underscore():
    """Test that apostrophe after underscore is recognized as apostrophe in word."""
    state = _ParserState()
    # "word_'s" - apostrophe after underscore should be recognized as apostrophe
    assert state._is_apostrophe_in_word("word_'s", 5) == True, \
        "Apostrophe after underscore should be recognized as apostrophe in word"


def test_apostrophe_after_letter():
    """Test that apostrophe after letter is recognized as apostrophe in word."""
    state = _ParserState()
    # "cat's" - apostrophe after letter should be recognized as apostrophe
    assert state._is_apostrophe_in_word("cat's", 3) == True, \
        "Apostrophe after letter should be recognized as apostrophe in word"


def test_string_prefix_not_apostrophe():
    """Test that string prefixes are not recognized as apostrophes."""
    state = _ParserState()
    # "r'hello'" - quote after 'r' should not be apostrophe (string prefix)
    assert state._is_apostrophe_in_word("r'hello'", 1) == False, \
        "Quote after string prefix should not be recognized as apostrophe"


if __name__ == "__main__":
    # Run tests
    test_apostrophe_after_letter()
    test_string_prefix_not_apostrophe()
    
    # These should fail with current code
    try:
        test_apostrophe_after_digit()
        print("ERROR: test_apostrophe_after_digit should have failed but didn't")
    except AssertionError:
        print("✓ test_apostrophe_after_digit failed as expected")
    
    try:
        test_apostrophe_after_underscore()
        print("ERROR: test_apostrophe_after_underscore should have failed but didn't")
    except AssertionError:
        print("✓ test_apostrophe_after_underscore failed as expected")
    
    print("\nAll tests behaved as expected (some failing, some passing)")