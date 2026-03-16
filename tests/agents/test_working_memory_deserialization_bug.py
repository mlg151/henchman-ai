"""Test for deserialization bug in working_memory.py."""

import pytest
import yaml

from henchman.agents.working_memory import (
    WorkingMemoryEntry,
    WorkingMemory,
)


def test_deserialization_bug_invalid_lines_read():
    """Test REAL BUG: Deserialization fails for entries with invalid lines_read.
    
    BUG: _parse_line_ranges skips invalid parts (e.g., "10-20,invalid,30-40" → [10-20, 30-40]),
    but _validate_lines_read raises ValueError for invalid format.
    WorkingMemoryEntry.__post_init__ calls _validate_lines_read.
    
    When loading from YAML (deserialization), __post_init__ is called and raises ValueError,
    causing deserialization to fail!
    
    This is a core functionality bug because:
    1. It breaks deserialization of saved working memory
    2. It's inconsistent: parsing allows it but validation rejects it
    3. It could happen if old code created entries with invalid format
       or if there's a bug elsewhere that creates invalid format
    """
    # Create a dictionary representing an entry with invalid lines_read
    entry_dict = {
        "path": "/test/file.py",
        "purpose": "Test",
        "lines_read": "10-20,invalid,30-40",  # Invalid format
        "key_insights": [],
        "timestamp": "2024-01-01T00:00:00Z",
    }
    
    # Try to create entry from dict (simulating YAML deserialization)
    # This should NOT raise ValueError anymore after fix
    # _validate_lines_read now accepts strings with invalid parts as long as there's at least one valid part
    entry = WorkingMemoryEntry.from_dict(entry_dict)
    assert entry.path == "/test/file.py"
    assert entry.lines_read == "10-20,invalid,30-40"
    
    # _parse_line_ranges handles it gracefully
    from henchman.agents.working_memory import WorkingMemory
    ranges = WorkingMemory._parse_line_ranges("10-20,invalid,30-40")
    assert len(ranges) == 2  # Skips "invalid"
    
    # Now validation and parsing are consistent!
    # Both accept strings with invalid parts as long as there's at least one valid part
    # This fixes the deserialization bug


def test_working_memory_deserialization_bug():
    """Test that WorkingMemory.load fails for entries with invalid lines_read."""
    # Create a WorkingMemory with an entry that has invalid lines_read
    # Actually, we can't create it because __post_init__ raises ValueError
    # So this bug would manifest as:
    # 1. Old code creates entry with invalid lines_read (bug in old code)
    # 2. Save to YAML
    # 3. New code tries to load → ValueError
    
    # Simulate YAML content with invalid lines_read
    yaml_content = """
current_task: Test
task_objectives: []
recent_files:
  - path: /test/file.py
    purpose: Test
    lines_read: "10-20,invalid,30-40"
    key_insights: []
    timestamp: "2024-01-01T00:00:00Z"
active_context: {}
decisions_made: []
completed_steps: []
next_actions: []
insights_gained: []
problems_encountered: []
"""
    
    data = yaml.safe_load(yaml_content)
    
    # Try to load - should NOT raise ValueError after fix
    memory = WorkingMemory.from_dict(data)
    assert memory.current_task == "Test"
    assert len(memory.recent_files) == 1
    assert memory.recent_files[0].lines_read == "10-20,invalid,30-40"
    
    # FIXED: Deserialization now succeeds for YAML with invalid parts in lines_read
    # as long as there's at least one valid part
    # This preserves the load/save contract