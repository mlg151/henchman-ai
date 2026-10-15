"""Test for Unicode dash handling bug in working_memory.py."""

from henchman.agents.working_memory import WorkingMemory


def test_memory_parse_line_ranges_unicode_dash_handling():
    """Test _parse_line_ranges with various Unicode dash characters.

    BUG: The regex [-\u2012\u2013\u2014\u2015\u2212] might not handle all dash characters correctly.
    Specifically, what about:
    - Figure dash '‒' (U+2012) - included
    - En dash '–' (U+2013) - included
    - Em dash '—' (U+2014) - included
    - Horizontal bar '―' (U+2015) - included
    - Minus sign '−' (U+2212) - included
    - But what about:
      - Hyphen-minus '-' (U+002D) - included
      - What about other dash-like characters?
    """
    from henchman.agents.line_range_utils import parse_line_ranges

    # Test with hyphen-minus (ASCII dash)
    ranges = parse_line_ranges("10-20")
    assert len(ranges) == 1
    assert ranges[0].start == 10
    assert ranges[0].end == 20

    # Test with en dash (U+2013)
    ranges = parse_line_ranges("10–20")  # en dash
    assert len(ranges) == 1
    assert ranges[0].start == 10
    assert ranges[0].end == 20

    # Test with em dash (U+2014)
    ranges = parse_line_ranges("10—20")  # em dash
    assert len(ranges) == 1
    assert ranges[0].start == 10
    assert ranges[0].end == 20

    # Test with minus sign (U+2212)
    ranges = parse_line_ranges("10−20")  # minus sign
    assert len(ranges) == 1
    assert ranges[0].start == 10
    assert ranges[0].end == 20

    # Test with figure dash (U+2012) - this might be the bug!
    # The regex includes \u2012, but let's test
    ranges = parse_line_ranges("10‒20")  # figure dash
    assert len(ranges) == 1
    assert ranges[0].start == 10
    assert ranges[0].end == 20

    # Test with horizontal bar (U+2015)
    ranges = parse_line_ranges("10―20")  # horizontal bar
    assert len(ranges) == 1
    assert ranges[0].start == 10
    assert ranges[0].end == 20

    # Test mixed: comma-separated with different dashes
    ranges = parse_line_ranges("10-20,30–40,50—60,70−80")
    assert len(ranges) == 4
    assert ranges[0].start == 10 and ranges[0].end == 20
    assert ranges[1].start == 30 and ranges[1].end == 40
    assert ranges[2].start == 50 and ranges[2].end == 60
    assert ranges[3].start == 70 and ranges[3].end == 80

    print("✓ parse_line_ranges handles Unicode dash characters correctly")


def test_memory_parse_line_ranges_invalid_unicode_dash():
    """Test parse_line_ranges with invalid Unicode dash-like characters.

    BUG: What if someone uses a dash-like character not in the regex?
    """
    from henchman.agents.line_range_utils import parse_line_ranges

    # Test with underscore (not a dash) - should parse as single line "10_20"
    ranges = parse_line_ranges("10_20")
    # Should parse as single line "10_20" which is not a valid integer
    # So it should skip this part
    assert ranges == []  # Or maybe parse as single line 10? Let's see

    # Test with tilde (not a dash)
    ranges = parse_line_ranges("10~20")
    assert ranges == []  # Should skip

    # Test with equals sign (not a dash)
    ranges = parse_line_ranges("10=20")
    assert ranges == []  # Should skip


def test_memory_should_read_file_with_unicode_dash_in_history():
    """Test should_read_file when history contains Unicode dash characters.

    BUG: If a file was read with lines "10–20" (en dash), and we ask for lines 10-20 (ASCII dash),
    should it recognize they're the same?
    """
    memory = WorkingMemory(current_task="Test")

    # Add entry with en dash
    from henchman.agents.working_memory import WorkingMemoryEntry
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "10–20"))  # en dash

    # Request same range with ASCII dash
    should_read, reason = memory.should_read_file("/test/file.py", 10, 20)

    # Should return False (already read)
    assert should_read is False, f"Lines 10-20 were read (with en dash), should return False. Got: {should_read}, reason: {reason}"
    assert "already read" in reason.lower()


if __name__ == "__main__":
    import sys

    tests = [
        test_memory_parse_line_ranges_unicode_dash_handling,
        test_memory_parse_line_ranges_invalid_unicode_dash,
        test_memory_should_read_file_with_unicode_dash_in_history,
    ]

    failures = 0
    for test in tests:
        print(f"\nRunning {test.__name__}...")
        try:
            test()
            print("  ✓ PASS")
        except AssertionError as e:
            print(f"  ✗ FAIL: {e}")
            failures += 1
        except Exception as e:
            print(f"  ✗ ERROR: {e}")
            failures += 1

    print(f"\nTotal: {len(tests)} tests, {failures} failures")
    sys.exit(1 if failures > 0 else 0)
