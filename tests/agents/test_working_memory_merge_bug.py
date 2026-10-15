"""Test for a potential bug in the range merging logic."""

from henchman.agents.working_memory import LineRange, WorkingMemory, WorkingMemoryEntry


def test_memory_merge_ranges_adjacent():
    """Test that merge_line_ranges correctly merges adjacent ranges."""
    from henchman.agents.line_range_utils import merge_line_ranges

    # Test merging adjacent ranges: 1-10 and 11-20 should merge to 1-20
    ranges = [LineRange(1, 10), LineRange(11, 20)]
    merged = merge_line_ranges(ranges)

    assert len(merged) == 1
    assert merged[0].start == 1
    assert merged[0].end == 20

    # Test with overlapping ranges: 1-15 and 10-20 should merge to 1-20
    ranges2 = [LineRange(1, 15), LineRange(10, 20)]
    merged2 = merge_line_ranges(ranges2)

    assert len(merged2) == 1
    assert merged2[0].start == 1
    assert merged2[0].end == 20

    # Test with non-adjacent ranges: 1-10 and 21-30 should NOT merge
    ranges3 = [LineRange(1, 10), LineRange(21, 30)]
    merged3 = merge_line_ranges(ranges3)

    assert len(merged3) == 2
    assert merged3[0].start == 1
    assert merged3[0].end == 10
    assert merged3[1].start == 21
    assert merged3[1].end == 30


def test_memory_should_read_file_with_gap():
    """Test should_read_file when there's a gap in read ranges.

    Bug scenario: If we read lines 1-10 and 21-30, and request lines 1-30,
    should_read_file should return True (need to read) because there's a gap
    at lines 11-20.
    """
    memory = WorkingMemory(current_task="Test")

    # Add two entries with a gap: lines 1-10 and 21-30 (missing 11-20)
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "1-10"))
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "21-30"))

    # Request lines 1-30 (has gap at 11-20)
    should_read, reason = memory.should_read_file("/test/file.py", 1, 30)

    # Should return True because there's a gap at lines 11-20
    assert should_read is True, (
        f"Lines 1-30 have a gap at 11-20. Should return True (need to read). "
        f"Got: {should_read}, reason: {reason}"
    )
    assert "need to be read" in reason.lower() or "gap" in reason.lower()


def test_memory_should_read_file_covered_by_multiple_ranges():
    """Test should_read_file when requested range is covered by multiple ranges.

    If we read lines 1-10 and 11-20, and request lines 1-20,
    should_read_file should return False (already read) because
    the merged ranges cover 1-20.
    """
    memory = WorkingMemory(current_task="Test")

    # Add two adjacent entries: lines 1-10 and 11-20
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "1-10"))
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "11-20"))

    # Request lines 1-20 (covered by adjacent ranges 1-10 and 11-20)
    should_read, reason = memory.should_read_file("/test/file.py", 1, 20)

    # Should return False because merged ranges cover 1-20
    assert should_read is False, (
        f"Lines 1-20 are covered by adjacent ranges 1-10 and 11-20. "
        f"Should return False (already read). Got: {should_read}, reason: {reason}"
    )
    assert "already read" in reason.lower()


def test_memory_should_read_file_partial_overlap():
    """Test should_read_file with partial overlap.

    If we read lines 1-10, and request lines 5-15,
    should_read_file should return True (need to read lines 11-15).
    """
    memory = WorkingMemory(current_task="Test")

    # Add entry: lines 1-10
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "1-10"))

    # Request lines 5-15 (partially overlaps with 1-10)
    should_read, reason = memory.should_read_file("/test/file.py", 5, 15)

    # Should return True because we need lines 11-15
    assert should_read is True, (
        f"Lines 5-15 partially overlap with 1-10 (need lines 11-15). "
        f"Should return True (need to read). Got: {should_read}, reason: {reason}"
    )
    assert "need to be read" in reason.lower()


if __name__ == "__main__":
    # Run tests
    import sys

    print("Testing range merging logic...")
    print("=" * 60)

    tests = [
        test_memory_merge_ranges_adjacent,
        test_memory_should_read_file_with_gap,
        test_memory_should_read_file_covered_by_multiple_ranges,
        test_memory_should_read_file_partial_overlap,
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

    print("\n" + "=" * 60)
    print(f"Total: {len(tests)} tests, {failures} failures")
    sys.exit(1 if failures > 0 else 0)
