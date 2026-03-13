"""Test to demonstrate the raw string prefix bug in _is_raw_string_prefix."""

import pytest
from henchman.utils.intelligent_context import _ParserState


def test_is_raw_string_prefix_bug():
    """Test that _is_raw_string_prefix incorrectly accepts non-raw prefixes."""
    parser = _ParserState()
    
    # Test cases where the bug manifests
    test_cases = [
        # (content, position, expected_result, description)
        # 'b' prefix (bytes, not raw) - should return False but returns True due to bug
        ('b"hello"', 1, False, "bytes prefix 'b' should not be raw"),
        # 'f' prefix (formatted, not raw) - should return False but returns True due to bug
        ('f"hello {name}"', 1, False, "formatted prefix 'f' should not be raw"),
        # 'u' prefix (unicode, not raw) - should return False but returns True due to bug
        ('u"hello"', 1, False, "unicode prefix 'u' should not be raw"),
        # 'r' prefix (raw) - should return True
        ('r"hello\\n"', 1, True, "raw prefix 'r' should be raw"),
        # 'br' prefix (bytes raw) - should return True
        ('br"hello\\n"', 2, True, "bytes raw prefix 'br' should be raw"),
        # 'fr' prefix (formatted raw) - should return True
        ('fr"hello {name}\\n"', 2, True, "formatted raw prefix 'fr' should be raw"),
    ]
    
    for content, position, expected, description in test_cases:
        result = parser._is_raw_string_prefix(content, position)
        assert result == expected, f"{description}: expected {expected}, got {result} for '{content}' at position {position}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])