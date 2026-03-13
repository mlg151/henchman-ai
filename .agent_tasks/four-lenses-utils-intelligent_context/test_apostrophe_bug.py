"""Test for apostrophe bug in _is_apostrophe_in_word method."""

from henchman.utils.intelligent_context import _ParserState

def test_apostrophe_in_word():
    """Test _is_apostrophe_in_word method."""
    state = _ParserState()
    
    # Test cases where single quote should be apostrophe in word
    assert state._is_apostrophe_in_word("don't", 3) == True  # n't
    assert state._is_apostrophe_in_word("isn't", 3) == True  # n't
    assert state._is_apostrophe_in_word("can't", 3) == True  # n't
    
    # Test cases where single quote should NOT be apostrophe (string delimiter)
    # a'hello' - variable a followed by string (invalid Python but should be string)
    # Actually, a'hello' is invalid Python syntax. Let's test valid cases:
    assert state._is_apostrophe_in_word("'hello'", 0) == False  # String start
    assert state._is_apostrophe_in_word("r'hello'", 1) == False  # Raw string
    assert state._is_apostrophe_in_word("fr'hello'", 2) == False  # Formatted raw string
    
    # Test edge case: what about print('hello')?
    # The quote at position 6 in "print('hello')" has '(' before it
    text = "print('hello')"
    quote_pos = 6  # Position of first quote
    assert state._is_apostrophe_in_word(text, quote_pos) == False  # Should be string delimiter
    
    # Test apostrophe at end of word: cats'
    assert state._is_apostrophe_in_word("cats'", 4) == True  # s' (apostrophe indicating possession)
    
    # Test apostrophe followed by non-letter: a'1
    assert state._is_apostrophe_in_word("a'1", 1) == False  # ' followed by digit
    
    print("All tests passed!")

if __name__ == "__main__":
    test_apostrophe_in_word()