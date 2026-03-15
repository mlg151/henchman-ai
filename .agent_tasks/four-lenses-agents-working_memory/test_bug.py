"""Test to find a bug in working_memory.py"""

from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry

def test_boolean_bug_already_fixed():
    """Test that boolean bug is already fixed."""
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "full"))
    
    # Boolean values should be rejected
    should_read, reason = memory.should_read_file("/test/file.py", True, 10)
    assert should_read is True, f"Boolean True should be rejected, got {should_read}"
    assert "invalid" in reason.lower() or "type" in reason.lower() or "bool" in reason.lower()
    print(f"✓ Boolean bug is FIXED: start=True correctly rejected")

def test_negative_start_bug():
    """Test negative start line numbers."""
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "full"))
    
    # start=-1 should be invalid
    should_read, reason = memory.should_read_file("/test/file.py", -1, 10)
    assert should_read is True, f"start=-1 should be invalid, got {should_read}"
    assert "invalid" in reason.lower() or "positive" in reason.lower()
    print(f"✓ Negative start bug is FIXED: start=-1 correctly rejected")

def test_end_minus_one_special_case():
    """Test end=-1 special case (means 'read to EOF')."""
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "full"))
    
    # end=-1 is valid special value
    should_read, reason = memory.should_read_file("/test/file.py", 1, -1)
    assert should_read is False, f"end=-1 is valid, file read fully, should return False, got {should_read}"
    assert "already read" in reason.lower()
    print(f"✓ end=-1 special case works correctly")

def test_path_normalization():
    """Test path normalization."""
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("./file.py", "Test", "full"))
    
    should_read, reason = memory.should_read_file("file.py", 10, 50)
    assert should_read is False, f"Paths should be normalized, ./file.py == file.py, got {should_read}"
    print(f"✓ Path normalization works correctly")

def test_full_with_whitespace():
    """Test 'full' with various whitespace."""
    test_cases = [
        "full",
        "FULL",
        "Full",
        " full ",
        "\tfull\t",
        "full,10-20",
        "10-20,full",
        "full, 10-20, 30-40",
    ]
    
    for lines_read in test_cases:
        memory = WorkingMemory(current_task="Test")
        memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", lines_read))
        
        should_read, reason = memory.should_read_file("/test/file.py", 10, 50)
        assert should_read is False, f"lines_read='{lines_read}' should be considered 'full', got {should_read}"
    
    print(f"✓ 'full' detection with whitespace works correctly")

def test_parse_line_ranges_edge_cases():
    """Test _parse_line_ranges edge cases."""
    memory = WorkingMemory(current_task="Test")
    
    test_cases = [
        ("", []),
        ("   ", []),
        ("invalid", []),
        ("10-20", [memory._parse_line_ranges("10-20")[0]]),
        ("10-20,30-40", [memory._parse_line_ranges("10-20")[0], memory._parse_line_ranges("30-40")[0]]),
        ("10", [memory._parse_line_ranges("10")[0]]),
        ("10--20", []),  # Invalid: double dash
        ("20-10", []),  # Invalid: start > end
        ("0-10", []),  # Invalid: line 0
        ("10-20,invalid,30-40", [memory._parse_line_ranges("10-20")[0], memory._parse_line_ranges("30-40")[0]]),
    ]
    
    for input_str, expected in test_cases:
        result = memory._parse_line_ranges(input_str)
        if expected == []:
            assert result == [], f"'{input_str}' should parse to [], got {result}"
        else:
            assert len(result) == len(expected), f"'{input_str}' should parse to {len(expected)} ranges, got {len(result)}"
    
    print(f"✓ _parse_line_ranges edge cases work correctly")

if __name__ == "__main__":
    print("Testing for bugs in working_memory.py...")
    print("=" * 60)
    
    test_boolean_bug_already_fixed()
    test_negative_start_bug()
    test_end_minus_one_special_case()
    test_path_normalization()
    test_full_with_whitespace()
    test_parse_line_ranges_edge_cases()
    
    print("=" * 60)
    print("All tests pass - no bugs found!")
    print("The bugs described in the tests have been fixed.")