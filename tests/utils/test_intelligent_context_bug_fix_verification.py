"""Verification test for the string prefix bug fix."""

import pytest

from henchman.utils.intelligent_context_parser import _ApostropheDetector, _ParserState


def test_invalid_string_prefix_not_mistaken_for_apostrophe():
    """Test that invalid string prefix combinations are treated as string delimiters in code context."""
    state = _ParserState()

    # fb' is NOT a valid Python string prefix (f and b can't combine)
    # In code context, even invalid prefixes indicate attempted string literals
    text = "fb's"
    result = _ApostropheDetector.is_apostrophe_in_word(state, text, 2)
    # fb' is invalid prefix, but in code it's an attempted string literal
    # So it should return False (string delimiter, not apostrophe)
    assert not result, "fb's should be treated as string delimiter (fb is invalid prefix but indicates string in code)"

    # ur' is NOT valid in Python 3 (u cannot combine with r)
    text2 = "ur's"
    result2 = _ApostropheDetector.is_apostrophe_in_word(state, text2, 2)
    assert not result2, "ur's should be treated as string delimiter (ur is invalid in Python 3 but indicates string)"

    # rr' is NOT valid (duplicate r)
    text3 = "rr's"
    result3 = _ApostropheDetector.is_apostrophe_in_word(state, text3, 2)
    assert not result3, "rr's should be treated as string delimiter (rr is invalid but indicates string)"

    # br' IS valid (bytes raw)
    text4 = "br's"
    result4 = _ApostropheDetector.is_apostrophe_in_word(state, text4, 2)
    assert not result4, "br's should be treated as string literal (br is valid prefix)"

    # b' IS valid (bytes)
    text5 = "b's"
    result5 = _ApostropheDetector.is_apostrophe_in_word(state, text5, 1)
    assert not result5, "b's should be treated as string literal (b is valid prefix)"

    # r' IS valid (raw)
    text6 = "r's"
    result6 = _ApostropheDetector.is_apostrophe_in_word(state, text6, 1)
    assert not result6, "r's should be treated as string literal (r is valid prefix)"


def test_valid_string_prefix_detection():
    """Test that valid string prefixes are correctly detected."""
    state = _ParserState()

    # Test _is_valid_string_prefix
    assert state._is_valid_string_prefix("b")
    assert state._is_valid_string_prefix("r")
    assert state._is_valid_string_prefix("f")
    assert state._is_valid_string_prefix("u")
    assert state._is_valid_string_prefix("br")
    assert state._is_valid_string_prefix("rb")
    assert state._is_valid_string_prefix("fr")
    assert state._is_valid_string_prefix("rf")

    # Invalid combinations
    assert not state._is_valid_string_prefix("fb")
    assert not state._is_valid_string_prefix("bf")
    assert not state._is_valid_string_prefix("ur")
    assert not state._is_valid_string_prefix("ru")
    assert not state._is_valid_string_prefix("ub")
    assert not state._is_valid_string_prefix("bu")
    assert not state._is_valid_string_prefix("uf")
    assert not state._is_valid_string_prefix("fu")
    assert not state._is_valid_string_prefix("rr")
    assert not state._is_valid_string_prefix("bb")
    assert not state._is_valid_string_prefix("ff")
    assert not state._is_valid_string_prefix("uu")

    # Too long
    assert not state._is_valid_string_prefix("brr")
    assert not state._is_valid_string_prefix("fbr")


if __name__ == "__main__":
    pytest.main([__file__, "-xvs"])
