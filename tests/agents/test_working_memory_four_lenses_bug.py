"""Test for a real bug in working_memory.py using Four Lenses approach."""

import pytest
from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry, LineRange

def test_memory_should_read_file_bool_start():
    """Test should_read_file with bool start value (True/False).
    
    BUG: bool is a subclass of int in Python, so isinstance(True, int) returns True.
    The code uses type(start) is not int to reject bool values, which works.
    But what about numpy.int64 or other integer-like types?
    """
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "full"))
    
    # Test with bool True (should be rejected)
    should_read, reason = memory.should_read_file("/test/file.py", True, 10)
    assert should_read is True, f"bool start=True should be rejected. Got: {should_read}, reason: {reason}"
    assert "invalid" in reason.lower() or "integer" in reason.lower(), (
        f"Should report invalid line number error for bool. Got: {reason}"
    )
    
    # Test with bool False (should be rejected)
    should_read, reason = memory.should_read_file("/test/file.py", False, 10)
    assert should_read is True, f"bool start=False should be rejected. Got: {should_read}, reason: {reason}"
    assert "invalid" in reason.lower() or "integer" in reason.lower(), (
        f"Should report invalid line number error for bool. Got: {reason}"
    )

def test_memory_should_read_file_float_end_minus_one():
    """Test should_read_file with float end=-1.0.
    
    BUG: end=-1.0 (float) should be rejected, but end=-1 (int) is allowed.
    The type check uses type(end) is not int, which rejects float.
    """
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "full"))
    
    # Test with float -1.0 (should be rejected)
    should_read, reason = memory.should_read_file("/test/file.py", 10, -1.0)
    assert should_read is True, f"float end=-1.0 should be rejected. Got: {should_read}, reason: {reason}"
    assert "invalid" in reason.lower() or "integer" in reason.lower(), (
        f"Should report invalid line number error for float. Got: {reason}"
    )
    
    # Test with int -1 (should be allowed, converted to None)
    should_read, reason = memory.should_read_file("/test/file.py", 10, -1)
    assert should_read is False, f"int end=-1 should be allowed (read to EOF). Got: {should_read}, reason: {reason}"
    assert "already read" in reason.lower()

def test_memory_should_read_file_none_start():
    """Test should_read_file with start=None explicitly passed.
    
    This should work (means read from beginning).
    """
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "10-50"))
    
    # Test with start=None, end=100 (read from beginning to line 100)
    should_read, reason = memory.should_read_file("/test/file.py", None, 100)
    assert should_read is True, f"start=None should work. Got: {should_read}, reason: {reason}"
    # Should say we need to read lines before 10

def test_memory_parse_line_ranges_unicode_digits():
    """Test _parse_line_ranges with Unicode digits.
    
    BUG: .isdecimal() accepts Arabic digits (٠١٢٣), but int() might not parse them?
    Actually, int() does parse Arabic digits in Python!
    """
    memory = WorkingMemory(current_task="Test")
    
    # Test with Arabic digits (٠١٢٣ = 0123 in Arabic)
    # Note: "١-١٠" means "1-10" in Arabic digits
    ranges = memory._parse_line_ranges("١-١٠")  # Arabic 1-10
    # This might fail because int() might not parse Arabic digits?
    # Actually, int("١") works in Python! Returns 1.
    print(f"Arabic digits test: ranges = {ranges}")
    
    # Test with Eastern Arabic digits (١٢٣ = 123)
    ranges = memory._parse_line_ranges("١-٢")  # Arabic 1-2
    print(f"Eastern Arabic digits test: ranges = {ranges}")

def test_memory_should_read_file_negative_start_after_full_check():
    """Test should_read_file with negative start AFTER full file check.
    
    BUG: If file was read fully AND start is negative, should report invalid line number,
    not "File already read (full)".
    """
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "full"))
    
    # Test with start=-5, end=10
    should_read, reason = memory.should_read_file("/test/file.py", -5, 10)
    print(f"start=-5, end=10: should_read={should_read}, reason={reason}")
    # Should return True with error about invalid line number
    
    # The validation happens at lines 547-567, BEFORE the "full" check at lines 570-582.
    # So start=-5 should be caught at line 551 (if start < 1).
    assert should_read is True, f"start=-5 should be rejected. Got: {should_read}, reason: {reason}"
    assert "invalid" in reason.lower() or "positive" in reason.lower(), (
        f"Should report invalid line number error. Got: {reason}"
    )

if __name__ == "__main__":
    test_memory_should_read_file_bool_start()
    test_memory_should_read_file_float_end_minus_one()
    test_memory_should_read_file_none_start()
    test_memory_parse_line_ranges_unicode_digits()
    test_memory_should_read_file_negative_start_after_full_check()
    print("\nAll tests run")