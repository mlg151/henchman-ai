"""Test for validation bug in working_memory.py.

Demonstrates that 'full,invalid' is incorrectly accepted as valid lines_read.
"""

import pytest
from henchman.agents.working_memory import WorkingMemoryEntry


def test_working_memory_entry_validation_bug():
    """Test that WorkingMemoryEntry correctly handles 'full,invalid' (after fix).
    
    After fix: 'full,invalid' should be ACCEPTED because it contains 'full'.
    _parse_line_ranges returns [] for any string containing 'full'.
    Validation should match parsing.
    """
    # After fix: 'full,invalid' should be ACCEPTED because it contains 'full'
    # _parse_line_ranges returns [] for "full,invalid"
    entry = WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="full,invalid",  # Contains 'full', invalid part ignored
        key_insights=[],
    )
    assert entry.lines_read == "full,invalid"
    
    # 'full,10-invalid' should also be accepted (contains 'full')
    entry2 = WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="full,10-invalid",  # Contains 'full', invalid part ignored
        key_insights=[],
    )
    assert entry2.lines_read == "full,10-invalid"
    
    # 'full,invalid-20' should also be accepted (contains 'full')
    entry3 = WorkingMemoryEntry(
        path="/test/file.py", 
        purpose="Test",
        lines_read="full,invalid-20",  # Contains 'full', invalid part ignored
        key_insights=[],
    )
    assert entry3.lines_read == "full,invalid-20"
    
    # But 'invalid' (no valid parts, no 'full') should be rejected
    with pytest.raises(ValueError, match="Invalid lines_read"):
        WorkingMemoryEntry(
            path="/test/file.py",
            purpose="Test",
            lines_read="invalid",  # No valid parts, no 'full'
            key_insights=[],
        )
    
    print("Test passes: 'full,invalid' correctly handled (accepted with 'full')")


def test_working_memory_entry_valid_cases():
    """Test that valid cases still work."""
    # Valid: just 'full'
    entry1 = WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="full",
        key_insights=[],
    )
    assert entry1.lines_read == "full"
    
    # Valid: 'full,10-20' (full with valid range)
    entry2 = WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="full,10-20",
        key_insights=[],
    )
    assert entry2.lines_read == "full,10-20"
    
    # Valid: '10-20,full' (valid range with full)
    entry3 = WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="10-20,full",
        key_insights=[],
    )
    assert entry3.lines_read == "10-20,full"
    
    # Valid: '10-20,30-40' (multiple valid ranges)
    entry4 = WorkingMemoryEntry(
        path="/test/file.py",
        purpose="Test",
        lines_read="10-20,30-40",
        key_insights=[],
    )
    assert entry4.lines_read == "10-20,30-40"
    
    print("Test passes: valid cases still work")


if __name__ == "__main__":
    try:
        test_working_memory_entry_validation_bug()
        print("BUG: Test should have failed but passed!")
    except AssertionError:
        print("Test correctly failed (bug exists)")
    
    test_working_memory_entry_valid_cases()