"""Test for ur/ru string prefix bug in intelligent_context.py.

Test that _is_valid_raw_string_prefix correctly rejects ur and ru prefixes
in Python 3 (they are invalid syntax, not valid string prefixes).
"""

import pytest
from henchman.utils.intelligent_context import _ParserState


def test_is_valid_raw_string_prefix_ur_ru():
    """Test that ur and ru are rejected as invalid string prefixes in Python 3."""
    parser = _ParserState()
    
    # Valid raw string prefixes in Python 3
    valid_prefixes = ['r', 'br', 'rb', 'fr', 'rf']
    for prefix in valid_prefixes:
        assert parser._is_valid_raw_string_prefix(prefix), f"Valid prefix '{prefix}' should return True"
    
    # Invalid prefixes in Python 3 (ur and ru are Python 2 only)
    invalid_prefixes = ['ur', 'ru', 'rr', 'ub', 'uf', 'bu', 'fu', 'ff', 'bb', 'uu']
    for prefix in invalid_prefixes:
        assert not parser._is_valid_raw_string_prefix(prefix), f"Invalid prefix '{prefix}' should return False in Python 3"
    
    # Test uppercase versions (should also be invalid for ur/ru)
    assert not parser._is_valid_raw_string_prefix('UR'), f"Uppercase UR should be invalid"
    assert not parser._is_valid_raw_string_prefix('RU'), f"Uppercase RU should be invalid"
    assert not parser._is_valid_raw_string_prefix('Ur'), f"Mixed case Ur should be invalid"
    assert not parser._is_valid_raw_string_prefix('rU'), f"Mixed case rU should be invalid"


def test_python_3_string_prefix_behavior():
    """Verify actual Python 3 behavior for string prefixes."""
    import sys
    
    # Test that ur and ru raise SyntaxError in Python 3
    test_cases = [
        ('ur"test"', False, "ur prefix should be invalid in Python 3"),
        ('ru"test"', False, "ru prefix should be invalid in Python 3"),
        ('r"test"', True, "r prefix should be valid"),
        ('u"test"', True, "u prefix should be valid (redundant but allowed)"),
        ('br"test"', True, "br prefix should be valid"),
        ('fr"test"', True, "fr prefix should be valid"),
    ]
    
    for code, should_be_valid, message in test_cases:
        try:
            exec(code)
            is_valid = True
        except SyntaxError:
            is_valid = False
        
        assert is_valid == should_be_valid, f"{message}: {code} (Python {sys.version_info.major}.{sys.version_info.minor})"


if __name__ == "__main__":
    pytest.main([__file__, "-xvs"])