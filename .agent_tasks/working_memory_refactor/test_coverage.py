#!/usr/bin/env python3
"""Test to cover missing lines in working_memory.py."""

import pytest
from henchman.agents.working_memory import (
    WorkingMemoryEntry,
    WorkingMemory,
    LineRange,
    WorkingMemorySystem,
    DecisionEntry,
    ActionEntry,
    ProblemEntry,
)
from pathlib import Path
import tempfile
import yaml


def test_working_memory_entry_validation_invalid_lines_read():
    """Test validation of invalid lines_read strings."""
    # Test invalid range (start > end)
    with pytest.raises(ValueError, match="Invalid lines_read"):
        WorkingMemoryEntry(
            path="/test/file.py",
            purpose="test",
            lines_read="50-10",  # start > end
        )
    
    # Test non-decimal characters in range
    with pytest.raises(ValueError, match="Invalid lines_read"):
        WorkingMemoryEntry(
            path="/test/file.py",
            purpose="test",
            lines_read="10-abc",  # non-decimal in end
        )
    
    # Test non-decimal characters in single line
    with pytest.raises(ValueError, match="Invalid lines_read"):
        WorkingMemoryEntry(
            path="/test/file.py",
            purpose="test",
            lines_read="abc",  # non-decimal
        )
    
    # Test negative line numbers
    with pytest.raises(ValueError, match="Invalid lines_read"):
        WorkingMemoryEntry(
            path="/test/file.py",
            purpose="test",
            lines_read="-10-20",  # negative start
        )
    
    # Test zero line numbers
    with pytest.raises(ValueError, match="Invalid lines_read"):
        WorkingMemoryEntry(
            path="/test/file.py",
            purpose="test",
            lines_read="0-10",  # zero start
        )


def test_working_memory_entry_validation_valid_lines_read():
    """Test validation of valid lines_read strings."""
    # These should not raise exceptions
    entry1 = WorkingMemoryEntry(
        path="/test/file.py",
        purpose="test",
        lines_read="10-20",  # valid range
    )
    assert entry1.lines_read == "10-20"
    
    entry2 = WorkingMemoryEntry(
        path="/test/file.py",
        purpose="test",
        lines_read="10",  # valid single line
    )
    assert entry2.lines_read == "10"
    
    entry3 = WorkingMemoryEntry(
        path="/test/file.py",
        purpose="test",
        lines_read="full",  # valid full
    )
    assert entry3.lines_read == "full"
    
    entry4 = WorkingMemoryEntry(
        path="/test/file.py",
        purpose="test",
        lines_read="",  # valid empty
    )
    assert entry4.lines_read == ""
    
    entry5 = WorkingMemoryEntry(
        path="/test/file.py",
        purpose="test",
        lines_read="10-20,30-40",  # valid multiple ranges
    )
    assert entry5.lines_read == "10-20,30-40"


def test_working_memory_should_read_file_edge_cases():
    """Test edge cases for should_read_file method."""
    memory = WorkingMemory()
    
    # Test with invalid line numbers (bool instead of int)
    result, reason = memory.should_read_file("/test.py", start=True, end=False)
    assert result is True
    assert "Invalid line number" in reason
    
    # Test with negative end (not -1)
    result, reason = memory.should_read_file("/test.py", start=1, end=-2)
    assert result is True
    assert "Invalid line number" in reason
    
    # Test with start > end
    result, reason = memory.should_read_file("/test.py", start=10, end=5)
    assert result is True
    assert "Invalid line range" in reason
    
    # Test with float line numbers
    result, reason = memory.should_read_file("/test.py", start=1.5, end=10.0)
    assert result is True
    assert "Invalid line number" in reason


def test_working_memory_system_edge_cases():
    """Test edge cases for WorkingMemorySystem."""
    system = WorkingMemorySystem()
    
    # Test get_current_memory when no current task
    assert system.get_current_memory() is None
    
    # Test archive_current_memory when no current task
    with pytest.raises(ValueError, match="No current task to archive"):
        system.archive_current_memory(Path("/tmp"))


def test_line_range_from_str_edge_cases():
    """Test edge cases for LineRange.from_str."""
    # Test with invalid dash characters
    assert LineRange.from_str("10_20") is None  # underscore instead of dash
    assert LineRange.from_str("10.20") is None  # dot instead of dash
    assert LineRange.from_str("10 20") is None  # space instead of dash
    
    # Test with non-decimal characters
    assert LineRange.from_str("abc-def") is None
    assert LineRange.from_str("10-abc") is None
    assert LineRange.from_str("abc-10") is None
    
    # Test with invalid range (start > end)
    assert LineRange.from_str("20-10") is None
    
    # Test with zero or negative numbers
    assert LineRange.from_str("0-10") is None
    assert LineRange.from_str("-10-20") is None
    assert LineRange.from_str("10--20") is None


def test_working_memory_update_problem_not_found():
    """Test update_problem when problem not found."""
    memory = WorkingMemory()
    problem = ProblemEntry(problem="test problem", status="open")
    memory.add_problem(problem)
    
    # Try to update a different problem
    updated = ProblemEntry(problem="different problem", status="resolved")
    with pytest.raises(ValueError, match="Problem 'different problem' not found"):
        memory.update_problem(updated)


def test_working_memory_add_problem_invalid_type():
    """Test add_problem with invalid type."""
    memory = WorkingMemory()
    with pytest.raises(TypeError, match="entry must be a ProblemEntry"):
        memory.add_problem("not a problem entry")  # type: ignore


def test_working_memory_update_problem_invalid_type():
    """Test update_problem with invalid type."""
    memory = WorkingMemory()
    problem = ProblemEntry(problem="test", status="open")
    memory.add_problem(problem)
    
    with pytest.raises(TypeError, match="updated must be a ProblemEntry"):
        memory.update_problem("not a problem entry")  # type: ignore


if __name__ == "__main__":
    # Run tests
    test_working_memory_entry_validation_invalid_lines_read()
    print("✓ test_working_memory_entry_validation_invalid_lines_read")
    
    test_working_memory_entry_validation_valid_lines_read()
    print("✓ test_working_memory_entry_validation_valid_lines_read")
    
    test_working_memory_should_read_file_edge_cases()
    print("✓ test_working_memory_should_read_file_edge_cases")
    
    test_working_memory_system_edge_cases()
    print("✓ test_working_memory_system_edge_cases")
    
    test_line_range_from_str_edge_cases()
    print("✓ test_line_range_from_str_edge_cases")
    
    test_working_memory_update_problem_not_found()
    print("✓ test_working_memory_update_problem_not_found")
    
    test_working_memory_add_problem_invalid_type()
    print("✓ test_working_memory_add_problem_invalid_type")
    
    test_working_memory_update_problem_invalid_type()
    print("✓ test_working_memory_update_problem_invalid_type")
    
    print("\nAll tests passed!")