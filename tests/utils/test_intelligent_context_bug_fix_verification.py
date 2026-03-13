"""Verification test for the string prefix bug fix."""

import pytest
from henchman.utils.intelligent_context import _ParserState


def test_invalid_string_prefix_not_mistaken_for_apostrophe():
    """Test that invalid string prefix combinations are treated as string delimiters in code context."""
    state = _ParserState()
    
    # fb' is NOT a valid Python string prefix (f and b can't combine)
    # In code context, even invalid prefixes indicate attempted string literals
    text = "fb's"
    result = state._is_apostrophe_in_word(text, 2)
    # fb' is invalid prefix, but in code it's an attempted string literal
    # So it should return False (string delimiter, not apostrophe)
    assert result == False, "fb's should be treated as string delimiter (fb is invalid prefix but indicates string in code)"
    
    # ur' is NOT valid in Python 3 (u cannot combine with r)
    text2 = "ur's"
    result2 = state._is_apostrophe_in_word(text2, 2)
    assert result2 == False, "ur's should be treated as string delimiter (ur is invalid in Python 3 but indicates string)"
    
    # rr' is NOT valid (duplicate r)
    text3 = "rr's"
    result3 = state._is_apostrophe_in_word(text3, 2)
    assert result3 == False, "rr's should be treated as string delimiter (rr is invalid but indicates string)"
    
    # br' IS valid (bytes raw)
    text4 = "br's"
    result4 = state._is_apostrophe_in_word(text4, 2)
    assert result4 == False, "br's should be treated as string literal (br is valid prefix)"
    
    # b' IS valid (bytes)
    text5 = "b's"
    result5 = state._is_apostrophe_in_word(text5, 1)
    assert result5 == False, "b's should be treated as string literal (b is valid prefix)"
    
    # r' IS valid (raw)
    text6 = "r's"
    result6 = state._is_apostrophe_in_word(text6, 1)
    assert result6 == False, "r's should be treated as string literal (r is valid prefix)"


def test_valid_string_prefix_detection():
    """Test that valid string prefixes are correctly detected."""
    state = _ParserState()
    
    # Test _is_valid_string_prefix
    assert state._is_valid_string_prefix("b") == True
    assert state._is_valid_string_prefix("r") == True
    assert state._is_valid_string_prefix("f") == True
    assert state._is_valid_string_prefix("u") == True
    assert state._is_valid_string_prefix("br") == True
    assert state._is_valid_string_prefix("rb") == True
    assert state._is_valid_string_prefix("fr") == True
    assert state._is_valid_string_prefix("rf") == True
    
    # Invalid combinations
    assert state._is_valid_string_prefix("fb") == False
    assert state._is_valid_string_prefix("bf") == False
    assert state._is_valid_string_prefix("ur") == False
    assert state._is_valid_string_prefix("ru") == False
    assert state._is_valid_string_prefix("ub") == False
    assert state._is_valid_string_prefix("bu") == False
    assert state._is_valid_string_prefix("uf") == False
    assert state._is_valid_string_prefix("fu") == False
    assert state._is_valid_string_prefix("rr") == False
    assert state._is_valid_string_prefix("bb") == False
    assert state._is_valid_string_prefix("ff") == False
    assert state._is_valid_string_prefix("uu") == False
    
    # Too long
    assert state._is_valid_string_prefix("brr") == False
    assert state._is_valid_string_prefix("fbr") == False


if __name__ == "__main__":
    pytest.main([__file__, "-xvs"])