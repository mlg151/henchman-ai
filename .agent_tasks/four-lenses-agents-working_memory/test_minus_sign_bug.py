"""Test for bug with mathematical minus sign in _parse_line_ranges."""

from henchman.agents.working_memory import WorkingMemory

def test_minus_sign_bug():
    """Test that _parse_line_ranges doesn't handle mathematical minus sign U+2212.
    
    BUG: Regex r'[-\u2013\u2014]' doesn't include mathematical minus sign U+2212.
    If someone copies "10−20" (with minus sign), it won't parse.
    """
    memory = WorkingMemory(current_task="Test")
    
    # Test with hyphen (works)
    ranges_hyphen = memory._parse_line_ranges("10-20")
    print(f"_parse_line_ranges('10-20') = {ranges_hyphen}")
    assert len(ranges_hyphen) == 1
    assert ranges_hyphen[0].start == 10
    assert ranges_hyphen[0].end == 20
    
    # Test with en dash U+2013 (works)
    ranges_endash = memory._parse_line_ranges("10\u201320")
    print(f"_parse_line_ranges('10\\u201320') = {ranges_endash}")
    assert len(ranges_endash) == 1
    assert ranges_endash[0].start == 10
    assert ranges_endash[0].end == 20
    
    # Test with em dash U+2014 (works)
    ranges_emdash = memory._parse_line_ranges("10\u201420")
    print(f"_parse_line_ranges('10\\u201420') = {ranges_emdash}")
    assert len(ranges_emdash) == 1
    assert ranges_emdash[0].start == 10
    assert ranges_emdash[0].end == 20
    
    # Test with mathematical minus sign U+2212 (BUG: doesn't work)
    ranges_minus = memory._parse_line_ranges("10\u221220")
    print(f"_parse_line_ranges('10\\u221220') = {ranges_minus}")
    # Currently returns [] because regex doesn't match minus sign
    # Should return [LineRange(10,20)]
    print(f"BUG: Returns {ranges_minus}, should return [LineRange(10,20)]")
    
    # Also test figure dash U+2012
    ranges_figure = memory._parse_line_ranges("10\u201220")
    print(f"_parse_line_ranges('10\\u201220') = {ranges_figure}")
    # Also doesn't work
    
    # Test mixed: hyphen works, minus doesn't
    ranges_mixed = memory._parse_line_ranges("10-20,30\u221240")
    print(f"_parse_line_ranges('10-20,30\\u221240') = {ranges_mixed}")
    # Parses 10-20, skips 30−40
    assert len(ranges_mixed) == 1
    assert ranges_mixed[0].start == 10
    assert ranges_mixed[0].end == 20

if __name__ == "__main__":
    test_minus_sign_bug()