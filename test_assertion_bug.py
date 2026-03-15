"""Test for the assertion bug in working_memory.py"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from henchman.agents.working_memory import WorkingMemory, WorkingMemoryEntry

def test_assertion_bug():
    """Test that should_read_file doesn't have incorrect assertions."""
    memory = WorkingMemory(current_task="Test")
    memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "10-50"))
    
    # Test with start=30, end=None - this would be in the `elif start is not None:` branch
    # If the incorrect assertion were reachable, this would raise AssertionError
    should_read, reason = memory.should_read_file("/test/file.py", start=30)
    
    print(f"Test 1 - start=30, end=None:")
    print(f"  should_read: {should_read}")
    print(f"  reason: {reason}")
    
    # Should return True with appropriate reason
    assert should_read is True
    assert "may need to read lines beyond" in reason.lower() or "beyond" in reason.lower()
    
    # Also test with start=None, end=30 - this would be in the `else:` branch
    # where `assert end is not None` is actually correct
    should_read2, reason2 = memory.should_read_file("/test/file.py", end=30)
    
    print(f"\nTest 2 - start=None, end=30:")
    print(f"  should_read: {should_read2}")
    print(f"  reason: {reason2}")
    
    assert should_read2 is True
    assert "may need to read lines before" in reason2.lower() or "before" in reason2.lower()
    
    print("\nAll tests passed!")

if __name__ == "__main__":
    test_assertion_bug()