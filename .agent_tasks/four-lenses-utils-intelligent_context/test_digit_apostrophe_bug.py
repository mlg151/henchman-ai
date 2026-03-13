"""Test for digit before apostrophe bug in _is_apostrophe_in_word method."""

from henchman.utils.intelligent_context import _ParserState

def test_digit_before_apostrophe():
    """Test that digits before apostrophe are handled correctly."""
    state = _ParserState()
    
    # Test digit before apostrophe (e.g., "2024's")
    text = "2024's"
    i = 4  # Position of quote
    result = state._is_apostrophe_in_word(text, i)
    print(f"'{text}' at position {i}: {result}")
    # Should return True (apostrophe) but returns False
    
    # Test letter before apostrophe (e.g., "cat's")
    text = "cat's"
    i = 3  # Position of quote
    result = state._is_apostrophe_in_word(text, i)
    print(f"'{text}' at position {i}: {result}")
    # Should return True
    
    # Test underscore before apostrophe (e.g., "word_'s")
    text = "word_'s"
    i = 5  # Position of quote
    result = state._is_apostrophe_in_word(text, i)
    print(f"'{text}' at position {i}: {result}")
    # Should return True
    
    # Test string prefix (e.g., "r'hello'")
    text = "r'hello'"
    i = 1  # Position of quote
    result = state._is_apostrophe_in_word(text, i)
    print(f"'{text}' at position {i}: {result}")
    # Should return False (string delimiter)
    
    print("\nThe bug: '2024's' returns False (not apostrophe) but should return True")

if __name__ == "__main__":
    test_digit_before_apostrophe()