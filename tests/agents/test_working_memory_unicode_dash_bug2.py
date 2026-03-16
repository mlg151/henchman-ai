"""Test for Unicode dash bug in _parse_line_ranges."""

from henchman.agents.working_memory import WorkingMemory


def test_memory_parse_line_ranges_unicode_dash_bug():
    """Test _parse_line_ranges bug: missing Unicode dash characters.
    
    BUG: The regex in _parse_line_ranges doesn't include all common dash characters:
    - U+2010 HYPHEN (‐)
    - U+2011 NON-BREAKING HYPHEN (‑)
    - U+2043 HYPHEN BULLET (⁃)
    - U+FE63 SMALL HYPHEN-MINUS (﹣)
    - U+FF0D FULLWIDTH HYPHEN-MINUS (－)
    
    Only these are included:
    - U+002D HYPHEN-MINUS (-)
    - U+2012 FIGURE DASH (‒)
    - U+2013 EN DASH (–)
    - U+2014 EM DASH (—)
    - U+2015 HORIZONTAL BAR (―)
    - U+2212 MINUS SIGN (−)
    
    This means "10‐20" (U+2010) won't be parsed correctly.
    """
    from henchman.agents.line_range_utils import parse_line_ranges
    
    # Test with U+2010 HYPHEN (not in regex)
    result = parse_line_ranges("10‐20")  # U+2010
    # BUG: Returns empty list because dash not matched
    # Should return [LineRange(10, 20)]
    assert result == [], f"U+2010 HYPHEN not parsed, got {result}"
    
    # Test with U+002D HYPHEN-MINUS (in regex)
    result2 = parse_line_ranges("10-20")  # U+002D
    assert len(result2) == 1, f"U+002D should be parsed, got {result2}"
    assert result2[0].start == 10 and result2[0].end == 20
    
    # Test with U+2013 EN DASH (in regex)
    result3 = parse_line_ranges("10–20")  # U+2013
    assert len(result3) == 1, f"U+2013 should be parsed, got {result3}"
    assert result3[0].start == 10 and result3[0].end == 20
    
    print("Test demonstrates Unicode dash bug in _parse_line_ranges")


if __name__ == "__main__":
    test_memory_parse_line_ranges_unicode_dash_bug()