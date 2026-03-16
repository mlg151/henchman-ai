"""Test for validation bug in working_memory.py.

Demonstrates that 'full,invalid' is incorrectly accepted as valid lines_read.
"""

import pytest
from henchman.agents.working_memory import WorkingMemoryEntry


def test_working_memory_entry_validation_bug():
    """Test that WorkingMemoryEntry incorrectly accepts 'full,invalid'.
    
    This test FAILS with the current code (bug exists).
    It should PASS after the fix (raises ValueError).
    """
    # BUG: 'full,invalid' should be rejected because 'invalid' is not a valid range
    # but current code accepts it because it contains 'full'
    with pytest.raises(ValueError, match="Invalid lines_read"):
        entry = WorkingMemoryEntry(
            path="/test/file.py",
            purpose="Test",
            lines_read="full,invalid",  # Contains invalid content 'invalid'
            key_insights=[],
        )
    
    # Also test other invalid combinations
    with pytest.raises(ValueError, match="Invalid lines_read"):
        entry = WorkingMemoryEntry(
            path="/test/file.py",
            purpose="Test",
            lines_read="full,10-invalid",  # '10-invalid' has non-digit after dash
            key_insights=[],
        )
    
    with pytest.raises(ValueError, match="Invalid lines_read"):
        entry = WorkingMemoryEntry(
            path="/test/file.py", 
            purpose="Test",
            lines_read="full,invalid-20",  # 'invalid-20' has non-digit before dash
            key_insights=[],
        )
    
    print("Test passes: 'full,invalid' correctly rejected")


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