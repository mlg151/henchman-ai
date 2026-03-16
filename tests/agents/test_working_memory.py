"""Tests for working memory system."""

import os
import tempfile
from pathlib import Path

import pytest

from henchman.agents.working_memory import (
    ActionEntry,
    DecisionEntry,
    LineRange,
    ProblemEntry,
    WorkingMemory,
    WorkingMemoryEntry,
    WorkingMemorySystem,
)
from henchman.agents.line_range_utils import parse_line_ranges


class TestWorkingMemoryEntry:
    """Test WorkingMemoryEntry class."""

    def test_entry_creation(self):
        """Test creating a working memory entry."""
        entry = WorkingMemoryEntry(
            path="/test/file.py",
            purpose="Read for understanding",
            lines_read="1-50",
            key_insights=["Function foo does X", "Class Bar handles Y"],
        )
        
        assert entry.path == "/test/file.py"
        assert entry.purpose == "Read for understanding"
        assert entry.lines_read == "1-50"
        assert entry.key_insights == ["Function foo does X", "Class Bar handles Y"]
        assert entry.timestamp is not None

    def test_entry_to_dict(self):
        """Test serializing entry to dictionary."""
        entry = WorkingMemoryEntry(
            path="/test/file.py",
            purpose="Test",
            lines_read="full",
        )
        
        data = entry.to_dict()
        assert data["path"] == "/test/file.py"
        assert data["purpose"] == "Test"
        assert data["lines_read"] == "full"
        assert "key_insights" in data
        assert "timestamp" in data

    def test_entry_from_dict(self):
        """Test creating entry from dictionary."""
        data = {
            "path": "/test/file.py",
            "purpose": "Test",
            "lines_read": "10-20",
            "key_insights": ["Insight 1"],
            "timestamp": "2024-01-01T00:00:00Z",
        }
        
        entry = WorkingMemoryEntry.from_dict(data)
        assert entry.path == "/test/file.py"
        assert entry.purpose == "Test"
        assert entry.lines_read == "10-20"
        assert entry.key_insights == ["Insight 1"]
        assert entry.timestamp == "2024-01-01T00:00:00Z"


class TestWorkingMemory:
    """Test WorkingMemory class."""

    def test_memory_creation(self):
        """Test creating working memory."""
        memory = WorkingMemory(
            current_task="Test task",
            task_objectives=["Objective 1", "Objective 2"],
        )
        
        assert memory.current_task == "Test task"
        assert memory.task_objectives == ["Objective 1", "Objective 2"]
        assert memory.recent_files == []
        assert memory.active_context == {}
        assert memory.decisions_made == []
        assert memory.completed_steps == []
        assert memory.next_actions == []
        assert memory.insights_gained == []
        assert memory.problems_encountered == []

    def test_memory_add_file(self):
        """Test adding a file to memory."""
        memory = WorkingMemory(current_task="Test")
        entry = WorkingMemoryEntry(
            path="/test/file.py",
            purpose="Read for understanding",
            lines_read="1-50",
            key_insights=["Insight 1"],
        )
        memory.add_recent_file(entry)
        
        assert len(memory.recent_files) == 1
        stored_entry = memory.recent_files[0]
        assert stored_entry.path == "/test/file.py"
        assert stored_entry.purpose == "Read for understanding"
        assert stored_entry.lines_read == "1-50"
        assert stored_entry.key_insights == ["Insight 1"]

    def test_memory_add_file_does_not_modify_input(self):
        """Test that add_recent_file does not modify the input object (BUG FIX)."""
        memory = WorkingMemory(current_task="Test")
        # Create entry with relative path
        original_path = "./test/file.py"
        entry = WorkingMemoryEntry(
            path=original_path,
            purpose="Read for understanding",
            lines_read="1-50",
            key_insights=["Insight 1"],
        )
        
        # Store original values
        original_entry_path = entry.path
        
        # Add to memory
        memory.add_recent_file(entry)
        
        # BUG: entry.path should NOT be modified
        # Currently it IS modified (normalized in place)
        assert entry.path == original_path, (
            f"add_recent_file should not modify input object. "
            f"Expected path='{original_path}', got '{entry.path}'"
        )
        
        # The stored entry should have normalized path
        stored_entry = memory.recent_files[0]
        assert stored_entry.path != original_path, (
            f"Stored entry should have normalized path, not '{original_path}'"
        )
        # They should be different objects (or at least the path should be normalized in storage)
        # Note: With the bug, entry IS stored_entry (same object), so this would fail
        # With fix, they might be different objects or same object with copy-on-write semantics

    def test_memory_add_decision(self):
        """Test adding a decision to memory."""
        memory = WorkingMemory(current_task="Test")
        decision_entry = DecisionEntry(
            decision="Use approach A",
            rationale="It's simpler",
            impact="high"
        )
        memory.add_decision(decision_entry)
        
        assert len(memory.decisions_made) == 1
        stored_decision = memory.decisions_made[0]
        assert stored_decision.decision == "Use approach A"
        assert stored_decision.rationale == "It's simpler"
        assert stored_decision.impact == "high"

    def test_memory_add_completed_step(self):
        """Test adding a completed step to memory."""
        memory = WorkingMemory(current_task="Test")
        memory.add_completed_step("Read the documentation")
        
        assert len(memory.completed_steps) == 1
        assert memory.completed_steps[0] == "Read the documentation"

    def test_memory_add_next_action(self):
        """Test adding a next action to memory."""
        memory = WorkingMemory(current_task="Test")
        action_entry = ActionEntry(
            action="Implement feature X",
            priority="high",
            estimated_effort="2 hours"
        )
        memory.add_next_action(action_entry)
        
        assert len(memory.next_actions) == 1
        stored_action = memory.next_actions[0]
        assert stored_action.action == "Implement feature X"
        assert stored_action.priority == "high"
        assert stored_action.estimated_effort == "2 hours"

    def test_memory_add_insight(self):
        """Test adding an insight to memory."""
        memory = WorkingMemory(current_task="Test")
        memory.add_insight("The API rate limits are strict")
        
        assert len(memory.insights_gained) == 1
        assert memory.insights_gained[0] == "The API rate limits are strict"

    def test_memory_add_problem(self):
        """Test adding a problem to memory."""
        memory = WorkingMemory(current_task="Test")
        problem_entry = ProblemEntry(
            problem="Test failing",
            status="open",
            resolution=""
        )
        memory.add_problem(problem_entry)
        
        assert len(memory.problems_encountered) == 1
        stored_problem = memory.problems_encountered[0]
        assert stored_problem.problem == "Test failing"
        assert stored_problem.status == "open"
        assert stored_problem.resolution == ""

    def test_memory_update_problem(self):
        """Test updating a problem in memory."""
        memory = WorkingMemory(current_task="Test")
        memory.add_problem(ProblemEntry("Test failing", "open", ""))
        memory.update_problem(ProblemEntry("Test failing", "resolved", "Fixed assertion"))
        
        assert len(memory.problems_encountered) == 1
        problem = memory.problems_encountered[0]
        assert problem.problem == "Test failing"
        assert problem.status == "resolved"
        assert problem.resolution == "Fixed assertion"

    def test_memory_update_problem_not_found(self):
        """Test updating a problem that doesn't exist (should raise ValueError)."""
        memory = WorkingMemory(current_task="Test")
        memory.add_problem(ProblemEntry("Test failing", "open", ""))
        # Try to update a non-existent problem - should raise ValueError
        with pytest.raises(ValueError, match="Problem 'Non-existent problem' not found"):
            memory.update_problem(ProblemEntry("Non-existent problem", "resolved", "Fixed"))
        
        # Should still have only the original problem
        assert len(memory.problems_encountered) == 1
        problem = memory.problems_encountered[0]
        assert problem.problem == "Test failing"

    def test_memory_update_problem_invalid_input(self):
        """Test update_problem with invalid input (should raise error like add_problem)."""
        memory = WorkingMemory(current_task="Test")
        memory.add_problem(ProblemEntry("Test problem", "open", ""))
        
        # Test 1: None value - should raise TypeError (currently raises AttributeError)
        with pytest.raises(TypeError, match="updated must be a ProblemEntry"):
            memory.update_problem(None)  # type: ignore
        
        # Test 2: Object with problem attribute but missing status/resolution
        class PartialProblem:
            def __init__(self):
                self.problem = "Partial problem"
        
        with pytest.raises(TypeError, match="updated must be a ProblemEntry"):
            memory.update_problem(PartialProblem())  # type: ignore
        
        # Test 3: Object without problem attribute
        class NoProblem:
            def __init__(self):
                self.status = "open"
                self.resolution = ""
        
        with pytest.raises(TypeError, match="updated must be a ProblemEntry"):
            memory.update_problem(NoProblem())  # type: ignore
        
        # Test 4: Valid ProblemEntry should work
        memory.update_problem(ProblemEntry("Test problem", "resolved", "Fixed"))
        assert len(memory.problems_encountered) == 1
        problem = memory.problems_encountered[0]
        assert problem.problem == "Test problem"
        assert problem.status == "resolved"
        assert problem.resolution == "Fixed"
    def test_memory_add_problem_invalid_input(self):
        """Test add_problem with invalid input (should raise error)."""
        memory = WorkingMemory(current_task="Test")
        
        # Test 1: Object with problem attribute but missing status/resolution
        class PartialProblem:
            def __init__(self):
                self.problem = "Partial problem"
        
        # Should raise TypeError
        with pytest.raises(TypeError, match="entry must be a ProblemEntry"):
            memory.add_problem(PartialProblem())  # type: ignore
        
        # Test 2: Object without problem attribute
        class NoProblem:
            def __init__(self):
                self.status = "open"
                self.resolution = ""
        
        with pytest.raises(TypeError, match="entry must be a ProblemEntry"):
            memory.add_problem(NoProblem())  # type: ignore
        
        # Test 3: None value
        with pytest.raises(TypeError, match="entry must be a ProblemEntry"):
            memory.add_problem(None)  # type: ignore
        
        # Test 4: Empty string as problem
        empty_problem = ProblemEntry(problem="", status="open", resolution="")
        memory.add_problem(empty_problem)
        # This is actually valid - empty string is a valid problem description
        assert len(memory.problems_encountered) == 1
        
        # Test 4: Empty string as problem
        empty_problem = ProblemEntry(problem="", status="open", resolution="")
        memory.add_problem(empty_problem)
        # This is actually valid - empty string is a valid problem description
        # But maybe it shouldn't be? Let's check current behavior
        # Current behavior: adds it (because hasattr returns True for empty string)
        # This test documents the behavior
    
    def test_memory_add_problem_invalid_input_raises(self):
        """Test add_problem raises TypeError for invalid input (NEW TEST FOR FIX)."""
        memory = WorkingMemory(current_task="Test")
        
        # Test 1: Object with problem attribute but missing status/resolution
        class PartialProblem:
            def __init__(self):
                self.problem = "Partial problem"
        
        # After fix: should raise TypeError
        with pytest.raises(TypeError, match="entry must be a ProblemEntry"):
            memory.add_problem(PartialProblem())  # type: ignore
        
        # Test 2: Object without problem attribute
        class NoProblem:
            def __init__(self):
                self.status = "open"
                self.resolution = ""
        
        with pytest.raises(TypeError, match="entry must be a ProblemEntry"):
            memory.add_problem(NoProblem())  # type: ignore
        
        # Test 3: None value
        with pytest.raises(TypeError, match="entry must be a ProblemEntry"):
            memory.add_problem(None)  # type: ignore
        
        # Test 4: Valid ProblemEntry should work
        valid_problem = ProblemEntry(problem="Valid problem", status="open", resolution="")
        memory.add_problem(valid_problem)
        assert len(memory.problems_encountered) == 1
        assert memory.problems_encountered[0].problem == "Valid problem"
    def test_memory_should_read_file_with_multiple_entries(self):
        """Test should_read_file when there are multiple files in recent_files."""
        memory = WorkingMemory(current_task="Test")
        # Add multiple files
        memory.add_recent_file(WorkingMemoryEntry("/test/file1.py", "Test", "1-50"))
        memory.add_recent_file(WorkingMemoryEntry("/test/file2.py", "Test", "1-100"))
        memory.add_recent_file(WorkingMemoryEntry("/test/file3.py", "Test", "full"))
        
        # Check for file2 (should skip file1 with continue, find file2)
        should_read, reason = memory.should_read_file("/test/file2.py", 60, 150)
        
        # file2 was read lines 1-100, we want 60-150 (not fully contained - need 101-150)
        assert should_read is True
        assert "need to be read" in reason.lower()

    def test_memory_should_read_file_already_read_full(self):
        """Test should_read_file for a file already read fully."""
        memory = WorkingMemory(current_task="Test")
        memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "full"))
        should_read, reason = memory.should_read_file("/test/file.py")
        
        assert should_read is False
        assert "already read" in reason

    def test_memory_should_read_file_no_line_range(self):
        """Test should_read_file when no line range is provided (start_line/end_line is None)."""
        memory = WorkingMemory(current_task="Test")
        memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "10-50"))
        # Call without line range
        should_read, reason = memory.should_read_file("/test/file.py")
        
        # File was only partially read (lines 10-50), but calling without line range
        # means "should I read the whole file?" Answer should be YES because we haven't
        # read lines 1-9 or 51-end (or we don't know if we have).
        assert should_read is True, "File was only partially read (10-50), should read whole file when no line range specified"
        # Accept either old message ("not fully read") or new more accurate message
        assert ("not fully read" in reason.lower() or 
                "partial" in reason.lower() or 
                "need to read" in reason.lower() or
                "cannot determine" in reason.lower() or
                "file size unknown" in reason.lower()), \
            f"Reason should indicate file may not be fully read. Got: {reason}"

    def test_memory_should_read_file_overlapping_lines(self):
        """Test should_read_file for overlapping lines."""
        memory = WorkingMemory(current_task="Test")
        memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "10-50"))
        should_read, reason = memory.should_read_file("/test/file.py", 30, 70)
        
        # With the fix: 30-70 is not fully contained in 10-50 (need lines 51-70)
        assert should_read is True
        assert "New or partially overlapping" in reason or "need to be read" in reason

    def test_memory_should_read_file_different_lines(self):
        """Test should_read_file for different lines."""
        memory = WorkingMemory(current_task="Test")
        memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "10-50"))
        should_read, reason = memory.should_read_file("/test/file.py", 60, 100)
        
        assert should_read is True
        assert "need to be read" in reason.lower()

    def test_memory_should_read_file_full_read(self):
        """Test should_read_file when file was read fully (lines_read='full')."""
        memory = WorkingMemory(current_task="Test")
        memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "full"))
        should_read, reason = memory.should_read_file("/test/file.py", 10, 50)
        
        # BUG: This should be False! If file was read fully, any line range should be considered already read
        # Current implementation returns True because LineRange.from_str("full") returns None
        assert should_read is False, "File read fully should return False for any line range"
        assert "already read" in reason.lower()

    def test_memory_should_read_file_invalid_lines_read(self):
        """Test should_read_file when lines_read is not a valid range."""
        memory = WorkingMemory(current_task="Test")
        # Add with invalid lines_read format - should raise ValueError
        # Note: With the fix, WorkingMemoryEntry now validates lines_read
        # and raises ValueError for invalid format
        with pytest.raises(ValueError, match="Invalid lines_read"):
            memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "invalid-format"))
        
        # After fix: can't add invalid lines_read, so test different scenario
        # Add entry with empty lines_read (valid "no lines read")
        memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", ""))
        should_read, reason = memory.should_read_file("/test/file.py", 10, 50)
        
        assert should_read is True
        # Empty lines_read means "no lines have been read", not "invalid format"
        assert "no lines" in reason.lower() or "not read" in reason.lower()

    def test_memory_should_read_file_overlap_but_not_contained(self):
        """Test should_read_file when ranges overlap but requested range is not fully contained."""
        memory = WorkingMemory(current_task="Test")
        memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "10-50"))
        
        # Bug case: previously read 10-50, want to read 1-100 (overlaps but not contained)
        should_read, reason = memory.should_read_file("/test/file.py", 1, 100)
        assert should_read is True, "Should read when requested range (1-100) is not fully contained in previously read (10-50)"
        # New reason: "New or partially overlapping lines need to be read"
        assert "need to be read" in reason.lower()
        
        # Another bug case: previously read 10-50, want to read 30-70  
        should_read2, reason2 = memory.should_read_file("/test/file.py", 30, 70)
        assert should_read2 is True, "Should read when requested range (30-70) is not fully contained in previously read (10-50)"
        
        # Case where we shouldn't read: previously read 10-50, want 20-40 (fully contained)
        should_read3, reason3 = memory.should_read_file("/test/file.py", 20, 40)
        assert should_read3 is False, "Should NOT read when requested range (20-40) is fully contained in previously read (10-50)"

    def test_memory_get_file_insights(self):
        """Test getting insights for a file."""
        memory = WorkingMemory(current_task="Test")
        memory.add_recent_file(
            WorkingMemoryEntry(
                "/test/file.py",
                "Test",
                "full",
                ["Insight 1", "Insight 2"]
            )
        )
        
        insights = memory.get_file_insights("/test/file.py")
        assert insights == ["Insight 1", "Insight 2"]
        
        # Test for unknown file
        insights = memory.get_file_insights("/unknown/file.py")
        assert insights == []

    def test_memory_get_file_insights_multiple_entries(self):
        """Test getting insights for a file with multiple entries (should return most recent)."""
        memory = WorkingMemory(current_task="Test")
        # Add two entries for same file (older first, then newer)
        memory.add_recent_file(
            WorkingMemoryEntry(
                "/test/file.py",
                "First read",
                "1-50",
                ["Old insight 1", "Old insight 2"]
            )
        )
        memory.add_recent_file(
            WorkingMemoryEntry(
                "/test/file.py",
                "Second read", 
                "60-100",
                ["New insight 1", "New insight 2", "New insight 3"]
            )
        )
        
        # get_file_insights should return ALL insights from ALL entries (accumulated)
        insights = memory.get_file_insights("/test/file.py")
        # Fixed: Returns ALL insights in chronological order
        assert insights == ["Old insight 1", "Old insight 2", "New insight 1", "New insight 2", "New insight 3"], (
            f"get_file_insights returns {insights}, expected ALL insights in chronological order."
        )

    def test_memory_update_after_read(self):
        """Test update_after_read convenience method."""
        memory = WorkingMemory(current_task="Test")
        memory.update_after_read(
            path="/test/file.py",
            purpose="Test",
            line_range=LineRange(start=10, end=50),
            insights=["Important function"]
        )
        
        assert len(memory.recent_files) == 1
        entry = memory.recent_files[0]
        assert entry.path == "/test/file.py"
        assert entry.purpose == "Test"
        assert entry.lines_read == "10-50"
        assert entry.key_insights == ["Important function"]

    def test_memory_prune_recent_files(self):
        """Test pruning recent files."""
        memory = WorkingMemory(current_task="Test")
        # Add more than 10 files
        for i in range(15):
            memory.add_recent_file(WorkingMemoryEntry(f"/test/file{i}.py", "Test", "full"))
        
        assert len(memory.recent_files) == 15
        memory.prune_recent_files(max_entries=10)
        assert len(memory.recent_files) == 10
        # Should keep the most recent entries
        assert memory.recent_files[0].path == "/test/file5.py"
        assert memory.recent_files[-1].path == "/test/file14.py"

    def test_memory_prune_recent_files_no_pruning_needed(self):
        """Test pruning when no pruning is needed (len <= max_entries)."""
        memory = WorkingMemory(current_task="Test")
        # Add 5 files
        for i in range(5):
            memory.add_recent_file(WorkingMemoryEntry(f"/test/file{i}.py", "Test", "full"))
        
        assert len(memory.recent_files) == 5
        # Should not prune when max_entries is 10
        memory.prune_recent_files(max_entries=10)
        assert len(memory.recent_files) == 5
        # All files should still be there
        for i in range(5):
            assert memory.recent_files[i].path == f"/test/file{i}.py"

    def test_memory_to_dict(self):
        """Test serializing memory to dictionary."""
        memory = WorkingMemory(
            current_task="Test",
            task_objectives=["Goal 1"],
        )
        memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "full"))
        memory.add_decision(DecisionEntry("Decision", "Rationale", "medium"))
        memory.add_completed_step("Step 1")
        memory.add_next_action(ActionEntry("Action", "high", "1 hour"))
        memory.add_insight("Insight")
        memory.add_problem(ProblemEntry("Problem", "open", ""))
        
        data = memory.to_dict()
        assert data["current_task"] == "Test"
        assert data["task_objectives"] == ["Goal 1"]
        assert len(data["recent_files"]) == 1
        assert len(data["decisions_made"]) == 1
        assert len(data["completed_steps"]) == 1
        assert len(data["next_actions"]) == 1
        assert len(data["insights_gained"]) == 1
        assert len(data["problems_encountered"]) == 1

    def test_memory_from_dict(self):
        """Test creating memory from dictionary."""
        data = {
            "current_task": "Test task",
            "task_objectives": ["Goal 1"],
            "recent_files": [
                {
                    "path": "/test/file.py",
                    "purpose": "Test",
                    "lines_read": "full",
                    "key_insights": [],
                    "timestamp": "2024-01-01T00:00:00Z",
                }
            ],
            "active_context": {"key": "value"},
            "decisions_made": [{"decision": "Dec", "rationale": "Rat", "impact": "medium"}],
            "completed_steps": ["Step 1"],
            "next_actions": [{"action": "Act", "priority": "high", "estimated_effort": "1h"}],
            "insights_gained": ["Insight"],
            "problems_encountered": [{"problem": "Prob", "status": "open", "resolution": ""}],
        }
        
        memory = WorkingMemory.from_dict(data)
        assert memory.current_task == "Test task"
        assert memory.task_objectives == ["Goal 1"]
        assert len(memory.recent_files) == 1
        assert memory.recent_files[0].path == "/test/file.py"
        assert memory.active_context == {"key": "value"}
        assert len(memory.decisions_made) == 1
        assert memory.decisions_made[0].decision == "Dec"
        assert len(memory.completed_steps) == 1
        assert memory.completed_steps[0] == "Step 1"
        assert len(memory.next_actions) == 1
        assert memory.next_actions[0].action == "Act"
        assert len(memory.insights_gained) == 1
        assert memory.insights_gained[0] == "Insight"
        assert len(memory.problems_encountered) == 1
        assert memory.problems_encountered[0].problem == "Prob"

    def test_memory_save_and_load(self):
        """Test saving and loading memory to/from file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            memory = WorkingMemory(
                current_task="Test task",
                task_objectives=["Goal 1"],
            )
            memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "full"))
            
            # Save
            file_path = Path(tmpdir) / "memory.yaml"
            memory.save(file_path)
            assert file_path.exists()
            
            # Load
            loaded = WorkingMemory.load(file_path)
            assert loaded.current_task == "Test task"
            assert loaded.task_objectives == ["Goal 1"]
            assert len(loaded.recent_files) == 1
            assert loaded.recent_files[0].path == "/test/file.py"
    def test_memory_should_read_file_multiple_entries_same_file(self):
        """Test should_read_file when same file appears multiple times (should use most recent)."""
        memory = WorkingMemory(current_task="Test")
        
        # Add two entries for same file (simulating file read at different times)
        memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "First read", "1-50"))
        memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Second read", "60-100"))
        
        # Ask for lines that are in SECOND (more recent) read
        should_read, reason = memory.should_read_file("/test/file.py", 70, 90)
        
        # BUG: Currently finds FIRST entry (1-50), checks 70-90 against 1-50
        # Should find SECOND (most recent) entry (60-100) and return False
        assert should_read is False, (
            "Lines 70-90 are in most recent read (60-100), should return False. "
            "Bug: should_read_file finds FIRST entry, not MOST RECENT."
        )
        assert "already read" in reason.lower() or "contained" in reason.lower()
        # Another test case: most recent read is subset of earlier read
        memory2 = WorkingMemory(current_task="Test")
        memory2.add_recent_file(WorkingMemoryEntry("/test/file2.py", "First read", "1-100"))
        memory2.add_recent_file(WorkingMemoryEntry("/test/file2.py", "Second read", "10-50"))
        
        # Ask for lines that were in first read but NOT in second (more recent) read
        should_read2, reason2 = memory2.should_read_file("/test/file2.py", 60, 80)
        
        # BUG: Lines 60-80 WERE read in first read (1-100), so should return False
        # Current implementation only checks most recent (10-50) and returns True
        # This causes unnecessary re-reading
        assert should_read2 is False, (
            "Lines 60-80 were read in first read (1-100), should return False. "
            "Bug: should_read_file only checks most recent entry, not all entries."
        )
        assert "already read" in reason2.lower()
        
        # Test with uppercase "FULL"
        memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "FULL"))
        should_read, reason = memory.should_read_file("/test/file.py", 10, 50)
        
        # BUG: This should be False! File was read fully (FULL = full)
        # Current implementation returns True because "FULL" != "full"
        assert should_read is False, "File read fully (FULL) should return False for any line range"
        assert "already read" in reason.lower()
    def test_memory_should_read_file_invalid_lines_read_and_invalid_line_numbers(self):
        """Test should_read_file with invalid lines_read AND invalid line numbers.
        
        BUG: When lines_read is invalid (e.g., "invalid-format") AND line numbers are invalid
        (e.g., start=0, end=-1), the method should report the line number error, not the
        "invalid lines_read format" error. Line number validation should happen first.
        
        UPDATE: With the fix, WorkingMemoryEntry validates lines_read on creation,
        so we can't create entry with invalid lines_read. Test updated to use valid lines_read.
        """
        memory = WorkingMemory(current_task="Test")
        # Add with valid lines_read format (empty string means no lines read)
        memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", ""))
        
        # Test with start=0, end=-1 (both invalid)
        should_read, reason = memory.should_read_file("/test/file.py", 0, -1)
        
        # Should return error about invalid line numbers (start=0 is invalid)
        assert should_read is True
        assert "invalid" in reason.lower() or "positive" in reason.lower(), (
            f"Expected error about invalid line numbers, got: {reason}"
        )
        # The error should be about line numbers, not about lines_read format
        assert "invalid lines_read format" not in reason.lower(), (
            f"Should report line number error, not lines_read format error when line numbers are invalid. Got: {reason}"
        )
        # This test is for invalid lines_read, not for "full"
        # So we should check that it returns True (should read) with appropriate error
        """Test should_read_file handles case-insensitive 'full'."""
        memory = WorkingMemory(current_task="Test")
        
        # Test with uppercase "FULL"
        memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "FULL"))
        should_read, reason = memory.should_read_file("/test/file.py", 10, 50)
        
        # BUG: This should be False! File was read fully (FULL = full)
        # Current implementation returns True because "FULL" != "full"
        assert should_read is False, "File read fully (FULL) should return False for any line range"
        assert "already read" in reason.lower()
        
        # Test with mixed case "Full"
        memory2 = WorkingMemory(current_task="Test")
        memory2.add_recent_file(WorkingMemoryEntry("/test/file2.py", "Test", "Full"))
    def test_memory_should_read_file_invalid_line_numbers(self):
        """Test should_read_file with invalid line numbers (non-positive)."""
        memory = WorkingMemory(current_task="Test")
        memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "10-50"))
        
        # Test with start=0 (invalid, lines are 1-indexed)
        should_read, reason = memory.should_read_file("/test/file.py", 0, 10)
        assert should_read is True
        assert "invalid" in reason.lower() or "positive" in reason.lower()
        
        # Test with start=-5 (invalid)
        should_read, reason = memory.should_read_file("/test/file.py", -5, 10)
        assert should_read is True
        assert "invalid" in reason.lower() or "positive" in reason.lower()
        
        # Test with end=0 (invalid)
        should_read, reason = memory.should_read_file("/test/file.py", 1, 0)
        assert should_read is True
        assert "invalid" in reason.lower() or "positive" in reason.lower()
        
        # Test with both invalid
        should_read, reason = memory.should_read_file("/test/file.py", -5, -1)
        assert should_read is True
        assert "invalid" in reason.lower() or "positive" in reason.lower()

    def test_memory_should_read_file_invalid_line_numbers_partial_range(self):
        """Test should_read_file with invalid line numbers when only one of start/end is provided.
        
        BUG: Currently doesn't validate line numbers when only start or end is provided.
        Should validate start if provided (even if end is None) and end if provided (even if start is None).
        """
        memory = WorkingMemory(current_task="Test")
        memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "10-50"))
        
        # Test with start=0, end=None (invalid start, end is None)
        should_read, reason = memory.should_read_file("/test/file.py", start=0)
        assert should_read is True
        # BUG: Currently returns "File not fully read - partial read recorded"
        # Should return error about invalid line numbers
        assert "invalid" in reason.lower() or "positive" in reason.lower(), (
            f"Expected error about invalid line numbers, got: {reason}"
        )
        
        # Test with start=-5, end=None (invalid negative start)
        should_read, reason = memory.should_read_file("/test/file.py", start=-5)
        assert should_read is True
        assert "invalid" in reason.lower() or "positive" in reason.lower()
        
        # Test with start=None, end=0 (invalid end)
        should_read, reason = memory.should_read_file("/test/file.py", end=0)
        assert should_read is True
        assert "invalid" in reason.lower() or "positive" in reason.lower()
        
        # Test with start=None, end=-10 (invalid negative end)
        # Test with start=None, end=-10 (invalid negative end)
        should_read, reason = memory.should_read_file("/test/file.py", end=-10)
        assert should_read is True
        assert "invalid" in reason.lower() or "positive" in reason.lower()
        
        # Test with valid start=10, end=None (should return True because file not fully read)
        should_read, reason = memory.should_read_file("/test/file.py", start=10)
        assert should_read is True
        # New behavior: returns "May need to read lines beyond 50" instead of "File not fully read"
        assert "may need to read lines beyond" in reason.lower() or "beyond" in reason.lower()
        
        # Test with valid start=None, end=50 (should return True because file not fully read)
        should_read, reason = memory.should_read_file("/test/file.py", end=50)
        assert should_read is True
        # New behavior: returns "May need to read lines before 10" instead of "File not fully read"
        assert "may need to read lines before" in reason.lower() or "before" in reason.lower()

    def test_memory_should_read_file_invalid_line_numbers_with_full_read(self):
        """Test should_read_file with invalid line numbers when file was read fully.
        
        BUG: Invalid line number validation happens AFTER early return for "full" file.
        When file was read fully and invalid line numbers are provided (e.g., start=0),
        method should report invalid line number error, not "File already read (full)".
        """
        memory = WorkingMemory(current_task="Test")
        memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "full"))
        
        # Test with start=0, end=10 (invalid start, file read fully)
        should_read, reason = memory.should_read_file("/test/file.py", 0, 10)
        assert should_read is True, (
            f"Invalid line number start=0 should return True with error, "
            f"not False (file was read fully). Got: {should_read}, reason: {reason}"
        )
        assert "invalid" in reason.lower() or "positive" in reason.lower(), (
            f"Should report invalid line number error, not 'File already read (full)'. "
            f"Got reason: {reason}"
        )
        
        # Test with start=1, end=0 (invalid end, file read fully)
        should_read, reason = memory.should_read_file("/test/file.py", 1, 0)
        assert should_read is True
        assert "invalid" in reason.lower() or "positive" in reason.lower()
        
        # Test with start=0, end=None (invalid start, partial range, file read fully)
        should_read, reason = memory.should_read_file("/test/file.py", start=0)
        assert should_read is True
        assert "invalid" in reason.lower() or "positive" in reason.lower()
        
        # Test with start=None, end=0 (invalid end, partial range, file read fully)
        should_read, reason = memory.should_read_file("/test/file.py", end=0)
        assert should_read is True
        assert "invalid" in reason.lower() or "positive" in reason.lower()
        
        # Test with start=10, end=5 (start > end, file read fully)
        should_read, reason = memory.should_read_file("/test/file.py", 10, 5)
        assert should_read is True
        assert "invalid" in reason.lower() or "start.*>.*end" in reason.lower()
        
        # Valid line numbers should still return False (file read fully)
        should_read, reason = memory.should_read_file("/test/file.py", 10, 50)
        assert should_read is False
        assert "already read" in reason.lower()

    def test_memory_should_read_file_full_with_whitespace(self):
        """Test should_read_file handles 'full' with surrounding whitespace."""
        # Test with trailing space
        memory = WorkingMemory(current_task="Test")
        memory.add_recent_file(WorkingMemoryEntry("/test/file1.py", "Test", "FULL "))
        should_read, reason = memory.should_read_file("/test/file1.py", 10, 50)
        assert should_read is False, f"File marked as 'FULL ' should be considered fully read. Got: {should_read}, reason: {reason}"
        
        # Test with leading space
        memory2 = WorkingMemory(current_task="Test")
        memory2.add_recent_file(WorkingMemoryEntry("/test/file2.py", "Test", " full"))
        should_read2, reason2 = memory2.should_read_file("/test/file2.py", 10, 50)
        assert should_read2 is False, f"File marked as ' full' should be considered fully read"
        
        # Test with both spaces
        memory3 = WorkingMemory(current_task="Test")
        memory3.add_recent_file(WorkingMemoryEntry("/test/file3.py", "Test", " full "))
        should_read3, reason3 = memory3.should_read_file("/test/file3.py", 10, 50)
        assert should_read3 is False, f"File marked as ' full ' should be considered fully read"
        
        # Test with tabs
        memory4 = WorkingMemory(current_task="Test")
        memory4.add_recent_file(WorkingMemoryEntry("/test/file4.py", "Test", "\tfull\t"))
        should_read4, reason4 = memory4.should_read_file("/test/file4.py", 10, 50)
        assert should_read4 is False, f"File marked as '\\tfull\\t' should be considered fully read"

    def test_memory_should_read_file_full_then_partial(self):
        """Test should_read_file when file was read fully then partially.
        
        When a file was read fully at any point, it should be considered fully read,
        regardless of more recent partial reads. The full read indicates we've read
        the entire file during this agent task.
        """
        memory = WorkingMemory(current_task="Test")
        
        # Full read (older)
        memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Full read", "full"))
        # Partial read (newer) 
        memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Partial read", "10-50"))
        
        # Test 1: Lines in partial read (10-50) - should be False
        should_read, reason = memory.should_read_file("/test/file.py", 20, 40)
        assert should_read is False, f"Lines 20-40 should be already read (in partial read). Got: {should_read}"
        assert "already read" in reason.lower()
        
        # Test 2: Lines NOT in partial read but in full read (60-100) - should be False
        # The file was read fully in an older entry, so all lines should be considered read
        should_read, reason = memory.should_read_file("/test/file.py", 60, 100)
        assert should_read is False, (
            f"Lines 60-100 were read in the full read. "
            f"Should return False (already read). Got: {should_read}, reason: {reason}"
        )
        # Reason should indicate file was already read
        assert "already read" in reason.lower()
        
        # Test 3: Lines spanning both (1-100) - should be False
        # The file was read fully in an older entry, so all lines should be considered read
        should_read, reason = memory.should_read_file("/test/file.py", 1, 100)
        assert should_read is False, (
            f"Lines 1-100 were read in the full read. "
            f"Should return False (already read). Got: {should_read}"
        )
        
        # Test 4: Reverse order (partial then full) - should work correctly
        memory2 = WorkingMemory(current_task="Test")
        memory2.add_recent_file(WorkingMemoryEntry("/test/file2.py", "Partial read", "10-50"))
        memory2.add_recent_file(WorkingMemoryEntry("/test/file2.py", "Full read", "full"))
        
        # Full read is most recent, so all lines should be considered read
        should_read2, reason2 = memory2.should_read_file("/test/file2.py", 60, 100)
        assert should_read2 is False, (
            f"Lines 60-100 should be already read (full read is most recent). Got: {should_read2}"
        )
        assert "already read" in reason2.lower()
        assert "already read" in reason2.lower()

    def test_memory_should_read_file_multiple_partials_cover_range(self):
        """Test should_read_file when multiple partial reads collectively cover requested range."""
        memory = WorkingMemory(current_task="Test")
        
        # Add two partial reads that together cover lines 1-100
        memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "First read", "1-50"))
        memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Second read", "51-100"))
        
        # Request lines 1-100 (covered by both entries together)
        should_read, reason = memory.should_read_file("/test/file.py", 1, 100)
        
        # BUG: Currently returns True because no single entry covers 1-100
        # Should return False because entries 1-50 and 51-100 together cover 1-100
        assert should_read is False, (
            f"Lines 1-100 should be already read (covered by entries 1-50 and 51-100). Got: {should_read}, reason: {reason}"
        )
        assert "already read" in reason.lower()
        
        # Test with overlapping partial reads
        memory2 = WorkingMemory(current_task="Test")
        memory2.add_recent_file(WorkingMemoryEntry("/test/file2.py", "First read", "1-60"))
        memory2.add_recent_file(WorkingMemoryEntry("/test/file2.py", "Second read", "40-100"))
        
        # Request lines 1-100 (covered by overlapping entries)
        should_read2, reason2 = memory2.should_read_file("/test/file2.py", 1, 100)
        assert should_read2 is False, (
            f"Lines 1-100 should be already read (covered by overlapping entries 1-60 and 40-100). Got: {should_read2}"
        )
        assert "already read" in reason2.lower()
        
        # Test with three partial reads
        memory3 = WorkingMemory(current_task="Test")
        memory3.add_recent_file(WorkingMemoryEntry("/test/file3.py", "First read", "1-30"))
        memory3.add_recent_file(WorkingMemoryEntry("/test/file3.py", "Second read", "31-70"))
        memory3.add_recent_file(WorkingMemoryEntry("/test/file3.py", "Third read", "71-100"))
        
        # Request lines 1-100 (covered by three entries)
        should_read3, reason3 = memory3.should_read_file("/test/file3.py", 1, 100)
        assert should_read3 is False, (
            f"Lines 1-100 should be already read (covered by entries 1-30, 31-70, 71-100). Got: {should_read3}"
        )
        assert "already read" in reason3.lower()

    def test_memory_should_read_file_full_then_partial_bug(self):
        """Test that should_read_file correctly handles full read followed by partial read.
        
        When a file was read fully at any point, it should be considered fully read,
        regardless of more recent partial reads.
        """
        memory = WorkingMemory(current_task="Test")
        
        # Add old full read
        memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Old full read", "full"))
        
        # Add more recent partial read (this is the most recent entry)
        memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Recent partial read", "10-50"))
        
        # Request lines 1-100
        # The file was read fully in an older entry, so all lines should be considered read
        should_read, reason = memory.should_read_file("/test/file.py", 1, 100)
        
        assert should_read is False, (
            f"File was fully read in an older entry. "
            f"Should return False for lines 1-100. Got: {should_read}, reason: {reason}"
        )
        assert "already read" in reason.lower()

    def test_memory_should_read_file_path_normalization_bug(self):
        """Test that should_read_file normalizes file paths.
        
        BUG: Currently does exact string comparison, so './file.py' != 'file.py'
        even though they refer to the same file.
        """
        memory = WorkingMemory(current_task="Test")
        
        # Add entry with relative path './file.py'
        memory.add_recent_file(WorkingMemoryEntry("./file.py", "Test", "full"))
        
        # Check with different path representation 'file.py' (should match)
        should_read, reason = memory.should_read_file("file.py", 10, 50)
        
        # BUG: Returns True (should read) because paths don't match exactly
        # Should return False (file was read fully)
        assert should_read is False, (
            f"File './file.py' was read fully. "
            f"Checking 'file.py' should return False (same file). "
            f"Got: {should_read}, reason: {reason}"
        )
        assert "already read" in reason.lower()
        
        # Also test the reverse
        memory2 = WorkingMemory(current_task="Test")
        memory2.add_recent_file(WorkingMemoryEntry("file.py", "Test", "full"))
        
        should_read2, reason2 = memory2.should_read_file("./file.py", 10, 50)
        assert should_read2 is False, (
            f"File 'file.py' was read fully. "
            f"Checking './file.py' should return False (same file). "
            f"Got: {should_read2}, reason: {reason2}"
        )
        assert "already read" in reason2.lower()

    def test_memory_should_read_file_partial_range_specification_bug(self):
        """Test should_read_file bug with partial range specifications.
        
        BUG: When only start OR end is provided (not both), the method returns
        True immediately without checking if the requested partial range has
        been read.
        
        FIXED: Now provides more accurate error messages:
        - For start=X, end=None: "May need to read lines beyond {max_read_end}" or "Start line {start} beyond last read line {max_read_end}"
        - For start=None, end=Y: "May need to read lines before {min_read_start}" or "End line {end} before first read line {min_read_start}"
        """
        memory = WorkingMemory(current_task="Test")
        
        # Case 1: File read lines 10-50, request start=30, end=None (read from line 30 to EOF)
        memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "10-50"))
        should_read, reason = memory.should_read_file("/test/file.py", start=30)
        # Lines 30-50 HAVE been read (within 10-50), but we don't know about lines beyond 50
        # So should return True with "May need to read lines beyond 50"
        assert should_read is True, (
            f"Lines 30-EOF: we've read 30-50 but might need lines beyond 50. "
            f"Got: {should_read}, reason: {reason}"
        )
        assert "may need to read lines beyond" in reason.lower() or "beyond" in reason.lower()
        
        # Case 2: File read lines 10-50, request start=None, end=40 (read from beginning to line 40)
        should_read2, reason2 = memory.should_read_file("/test/file.py", end=40)
        # Lines 1-40: we've read 10-40 but haven't read lines 1-9
        # So should return True with "May need to read lines before 10"
        assert should_read2 is True, (
            f"Lines 1-40: we've read 10-40 but might need lines before 10. "
            f"Got: {should_read2}, reason: {reason2}"
        )
        assert "may need to read lines before" in reason2.lower() or "before" in reason2.lower()
        
        # Case 3: File read lines 10-50, request start=60, end=None (read from line 60 to EOF)
        should_read3, reason3 = memory.should_read_file("/test/file.py", start=60)
        # Lines 60-EOF have NOT been read (file only read up to 50), so should return True
        assert should_read3 is True, (
            f"Lines 60-EOF have NOT been read (file only read up to 50). "
            f"Got: {should_read3}, reason: {reason3}"
        )
        assert "start line 60 beyond last read line" in reason3.lower()
        
        # Case 4: File read lines 10-50, request start=None, end=5 (read from beginning to line 5)
        should_read4, reason4 = memory.should_read_file("/test/file.py", end=5)
        # Lines 1-5 have NOT been read (file read starts at 10), so should return True
        assert should_read4 is True, (
            f"Lines 1-5 have NOT been read (file read starts at 10). "
            f"Got: {should_read4}, reason: {reason4}"
        )
        assert "end line 5 before first read line" in reason4.lower()


class TestWorkingMemoryEntryValidation:
    """Test WorkingMemoryEntry validation edge cases."""

    def test_entry_validation_invalid_lines_read(self):
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

    def test_entry_validation_valid_lines_read(self):
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
        
        # Test whitespace-only string (should be valid)
        entry6 = WorkingMemoryEntry(
            path="/test/file.py",
            purpose="test",
            lines_read="   ",  # whitespace only
        )
        assert entry6.lines_read == "   "
        
        # Test string with spaces around commas
        entry7 = WorkingMemoryEntry(
            path="/test/file.py",
            purpose="test",
            lines_read="10-20 , 30-40",  # spaces around comma
        )
        assert entry7.lines_read == "10-20 , 30-40"
        
        # Test "full" with other parts (should be valid)
        entry8 = WorkingMemoryEntry(
            path="/test/file.py",
            purpose="test",
            lines_read="full,10-20",  # full with range
        )
        assert entry8.lines_read == "full,10-20"
        
        # Test string with empty parts (multiple commas)
        entry9 = WorkingMemoryEntry(
            path="/test/file.py",
            purpose="test",
            lines_read="10-20,,30-40",  # empty part between commas
        )
        assert entry9.lines_read == "10-20,,30-40"
        
        # Test string with trailing comma
        entry10 = WorkingMemoryEntry(
            path="/test/file.py",
            purpose="test",
            lines_read="10-20,",  # trailing comma
        )
        assert entry10.lines_read == "10-20,"
        
        # Test string with leading comma
        entry11 = WorkingMemoryEntry(
            path="/test/file.py",
            purpose="test",
            lines_read=",10-20",  # leading comma
        )
        assert entry11.lines_read == ",10-20"
        
        # Test string with valid and invalid parts (should be valid - invalid parts are skipped)
        entry12 = WorkingMemoryEntry(
            path="/test/file.py",
            purpose="test",
            lines_read="10-20,abc,30-40",  # valid, invalid, valid
        )
        assert entry12.lines_read == "10-20,abc,30-40"
        
        # Test string with valid range and invalid range (start > end)
        entry13 = WorkingMemoryEntry(
            path="/test/file.py",
            purpose="test",
            lines_read="10-20,50-10,30-40",  # valid, invalid (start > end), valid
        )
        assert entry13.lines_read == "10-20,50-10,30-40"
        
        # Test string with valid range and negative line numbers
        entry14 = WorkingMemoryEntry(
            path="/test/file.py",
            purpose="test",
            lines_read="10-20,-10-20,30-40",  # valid, invalid (negative), valid
        )
        assert entry14.lines_read == "10-20,-10-20,30-40"
        
        # Test string with valid range and zero line numbers
        entry15 = WorkingMemoryEntry(
            path="/test/file.py",
            purpose="test",
            lines_read="10-20,0-10,30-40",  # valid, invalid (zero), valid
        )
        assert entry15.lines_read == "10-20,0-10,30-40"
        
        # Test string with only invalid parts (should raise exception)
        # This tests line 188: if not has_valid_range and normalized:
        with pytest.raises(ValueError, match="Invalid lines_read"):
            WorkingMemoryEntry(
                path="/test/file.py",
                purpose="test",
                lines_read="0-10,abc,50-10",  # all invalid parts
            )
        
        # Test string with single invalid part (should raise exception)
        # This also tests line 188
        with pytest.raises(ValueError, match="Invalid lines_read"):
            WorkingMemoryEntry(
                path="/test/file.py",
                purpose="test",
                lines_read="0-10",  # single invalid part (zero start)
            )

    def test_entry_validation_lines_read_type_error(self):
        """Test validation of lines_read with wrong type."""
        # Test with non-string lines_read
        with pytest.raises(TypeError, match="lines_read must be a string or None"):
            WorkingMemoryEntry(
                path="/test/file.py",
                purpose="test",
                lines_read=123,  # type: ignore
            )
        
        # Test with list lines_read
        with pytest.raises(TypeError, match="lines_read must be a string or None"):
            WorkingMemoryEntry(
                path="/test/file.py",
                purpose="test",
                lines_read=["10-20"],  # type: ignore
            )

    def test_entry_validation_key_insights_type_error(self):
        """Test validation of key_insights with wrong type."""
        # Test with non-list key_insights
        with pytest.raises(TypeError, match="key_insights must be a list or None"):
            WorkingMemoryEntry(
                path="/test/file.py",
                purpose="test",
                lines_read="10-20",
                key_insights="not a list",  # type: ignore
            )
        
        # Test with dict key_insights
        with pytest.raises(TypeError, match="key_insights must be a list or None"):
            WorkingMemoryEntry(
                path="/test/file.py",
                purpose="test",
                lines_read="10-20",
                key_insights={"key": "value"},  # type: ignore
            )


class TestWorkingMemoryEdgeCases:
    """Test WorkingMemory edge cases."""

    def test_should_read_file_edge_cases(self):
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

    def test_update_problem_not_found(self):
        """Test update_problem when problem not found."""
        memory = WorkingMemory()
        problem = ProblemEntry(problem="test problem", status="open")
        memory.add_problem(problem)
        
        # Try to update a different problem
        updated = ProblemEntry(problem="different problem", status="resolved")
        with pytest.raises(ValueError, match="Problem 'different problem' not found"):
            memory.update_problem(updated)

    def test_add_problem_invalid_type(self):
        """Test add_problem with invalid type."""
        memory = WorkingMemory()
        with pytest.raises(TypeError, match="entry must be a ProblemEntry"):
            memory.add_problem("not a problem entry")  # type: ignore

    def test_update_problem_invalid_type(self):
        """Test update_problem with invalid type."""
        memory = WorkingMemory()
        problem = ProblemEntry(problem="test", status="open")
        memory.add_problem(problem)
        
        with pytest.raises(TypeError, match="updated must be a ProblemEntry"):
            memory.update_problem("not a problem entry")  # type: ignore


class TestLineRangeEdgeCases:
    """Test LineRange edge cases."""

    def test_line_range_from_str_edge_cases(self):
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
        
        # Test with non-string input
        assert LineRange.from_str(None) is None  # type: ignore
        assert LineRange.from_str(123) is None  # type: ignore
        assert LineRange.from_str(["10-20"]) is None  # type: ignore


class TestWorkingMemorySystemEdgeCases:
    """Test WorkingMemorySystem edge cases."""

    def test_get_current_memory_when_no_current_task(self):
        """Test get_current_memory when no current task."""
        system = WorkingMemorySystem()
        assert system.get_current_memory() is None
    
    def test_archive_current_memory_when_no_current_task(self):
        """Test archive_current_memory when no current task."""
        system = WorkingMemorySystem()
        with pytest.raises(ValueError, match="No current task to archive"):
            system.archive_current_memory(Path("/tmp"))


class TestWorkingMemorySystem:
    """Test WorkingMemorySystem class."""

    def test_system_creation(self):
        """Test creating working memory system."""
        system = WorkingMemorySystem()
        assert system.get_current_memory() is None
        assert system.memories == {}
        """Test creating working memory system."""
        system = WorkingMemorySystem()
        assert system.get_current_memory() is None
        assert system.memories == {}

    def test_create_memory(self):
        """Test creating a new memory."""
        system = WorkingMemorySystem()
        task_id = system.create_memory(
            task="Test task",
            objectives=["Goal 1", "Goal 2"],
        )
        
        memory = system.get_current_memory()
        assert memory is not None
        assert memory.current_task == "Test task"
        assert memory.task_objectives == ["Goal 1", "Goal 2"]
        assert system.current_task_id == task_id
        assert task_id in system.memories

    def test_switch_memory(self):
        """Test switching between memories."""
        system = WorkingMemorySystem()
        task_id1 = system.create_memory("Task 1", ["Goal 1"])
        memory1 = system.get_current_memory()
        
        task_id2 = system.create_memory("Task 2", ["Goal 2"])
        memory2 = system.get_current_memory()
        
        # Switch back to first task
        system.switch_memory(task_id1)
        assert system.get_current_memory() is memory1
        assert system.current_task_id == task_id1
        
        # Switch to second task
        system.switch_memory(task_id2)
        assert system.get_current_memory() is memory2
        assert system.current_task_id == task_id2

    def test_switch_memory_not_found(self):
        """Test switching to non-existent memory raises error."""
        system = WorkingMemorySystem()
        with pytest.raises(KeyError):
            system.switch_memory("non-existent-id")

    def test_archive_current_memory(self):
        """Test archiving current memory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            system = WorkingMemorySystem()
            task_id = system.create_memory("Test task", ["Goal 1"])
            memory = system.get_current_memory()
            assert memory is not None
            memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "full"))
            
            archive_path = Path(tmpdir)
            archived_file = system.archive_current_memory(archive_path)
            
            # Check file was created
            assert archived_file.exists()
            assert archived_file.name == f"working_memory_{task_id}.yaml"
            
            # Check memory was removed from system
            assert system.current_task_id is None
            assert system.get_current_memory() is None
            assert task_id not in system.memories

    def test_archive_current_memory_no_current(self):
        """Test archiving when no current memory raises error."""
        system = WorkingMemorySystem()
        with pytest.raises(ValueError):
            system.archive_current_memory(Path("/tmp"))


class TestHelperFunctions:
    """Test helper functions."""

    def test_normalize_path(self):
        """Test _normalize_path function."""
        from henchman.agents.working_memory import _normalize_path
        
        # Test empty path
        assert _normalize_path("") == ""
        
        # Test path with ~ (home directory)
        home = os.path.expanduser("~")
        assert _normalize_path("~/test/file.py") == os.path.join(home, "test", "file.py")
        
        # Test path with . and ..
        assert _normalize_path("./test/../file.py") == "file.py"
        
        # Test normal path
        assert _normalize_path("/test/file.py") == "/test/file.py"
        
        # Test Windows-style path (should normalize to forward slashes on Unix)
        if os.name == "nt":
            assert _normalize_path("C:\\test\\file.py") == "C:\\test\\file.py"
        else:
            # On Unix, backslashes are treated as part of the filename
            assert _normalize_path("C:\\test\\file.py") == "C:\\test\\file.py"

    def test_parse_line_range_valid(self):
        """Test parsing valid line range."""
        result = LineRange.from_str("10-50")
        assert result.start == 10
        assert result.end == 50

    def test_parse_line_range_invalid_format(self):
        """Test parsing invalid line range format."""
        result = LineRange.from_str("10:50")
        assert result is None

    def test_parse_line_range_invalid_numbers(self):
        """Test parsing line range with invalid numbers."""
        result = LineRange.from_str("abc-def")
        assert result is None

    def test_parse_line_range_single_number(self):
        """Test parsing single number as line range."""
        result = LineRange.from_str("10")
        assert result is None

    def test_parse_line_range_multiple_ranges(self):
        """Test parsing multiple ranges (comma-separated).
        
        BUG: LineRange.from_str doesn't support multiple ranges.
        We've added _parse_line_ranges method to handle multiple ranges.
        """
        # Test that LineRange.from_str still doesn't support multiple ranges
        result = LineRange.from_str("10-20,30-40")
        assert result is None  # LineRange.from_str doesn't support multiple ranges
        
        # Test that parse_line_ranges handles multiple ranges
        ranges = parse_line_ranges("10-20,30-40")
        assert len(ranges) == 2
        assert ranges[0].start == 10
        assert ranges[0].end == 20
        assert ranges[1].start == 30
        assert ranges[1].end == 40

    def test_line_range_overlaps_true(self):
        """Test LineRange.overlaps returns True for overlapping ranges."""
        r1 = LineRange(10, 50)
        assert r1.overlaps(LineRange(30, 70)) is True  # Partial overlap
        assert r1.overlaps(LineRange(20, 40)) is True  # Complete containment
        assert r1.overlaps(LineRange(5, 60)) is True   # Surrounding
        assert r1.overlaps(LineRange(50, 100)) is True # Touching at edge

    def test_line_range_overlaps_false(self):
        """Test LineRange.overlaps returns False for non-overlapping ranges."""
        r1 = LineRange(10, 50)
        assert r1.overlaps(LineRange(60, 100)) is False  # Completely separate
        assert r1.overlaps(LineRange(1, 5)) is False     # Separate before

    def test_line_range_invalid_start_gt_end(self):
        """Test that LineRange validates start <= end."""
        # LineRange should raise ValueError when start > end
        with pytest.raises(ValueError, match="Invalid LineRange: start .50. > end .10."):
            LineRange(50, 10)  # start=50, end=10 (invalid!)
        
        # Test that from_str also validates
        result = LineRange.from_str("50-10")
        assert result is None  # Should return None for invalid range

    def test_line_range_positive_line_numbers(self):
        """Test that LineRange validates line numbers are positive (1-indexed)."""
        # LineRange should raise ValueError for non-positive line numbers
        with pytest.raises(ValueError, match="Line numbers must be positive"):
            LineRange(0, 10)  # start=0 is invalid (1-indexed)
        
        with pytest.raises(ValueError, match="Line numbers must be positive"):
            LineRange(-5, 10)  # start=-5 is invalid
        
        with pytest.raises(ValueError, match="Line numbers must be positive"):
            LineRange(1, 0)  # end=0 is invalid (also start > end)
        
        with pytest.raises(ValueError, match="Line numbers must be positive"):
            LineRange(1, -5)  # end=-5 is invalid
        
        # Test that from_str also validates
        result = LineRange.from_str("0-10")
        assert result is None, "Should return None for line 0"
        
        result = LineRange.from_str("-5-10")
        assert result is None, "Should return None for negative line numbers"
        
        # Valid ranges should work
        assert LineRange(1, 10) is not None
        assert LineRange.from_str("1-10") is not None

    def test_memory_should_read_file_missing_return_bug(self):
        """Test should_read_file bug: missing return statement in end-only branch.
        
        BUG: When called with end=<number> and start=None (read from beginning to line X),
        the function falls through without returning, then crashes trying to create
        LineRange(None, end).
        """
        memory = WorkingMemory(current_task="Test")
        memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "10-50"))
        
        # Test case that triggers the bug: end=100, start=None
        # This should return (True, reason) but currently crashes
        should_read, reason = memory.should_read_file("/test/file.py", end=100)
        
        # Should return True because we want to read lines 1-100 but only read 10-50
        assert should_read is True, (
            f"Should return True when reading lines 1-100 but only read 10-50. "
            f"Got: {should_read}, reason: {reason}"
        )
        # Reason should indicate we need to read (line 100 is beyond last read line 50)
        assert "beyond" in reason.lower() or "before" in reason.lower() or "gap" in reason.lower(), (
            f"Reason should indicate need to read (line 100 beyond line 50 or before line 10). Got: {reason}"
        )
        
        # Also test with end=5 (before any read lines)
        should_read2, reason2 = memory.should_read_file("/test/file.py", end=5)
        assert should_read2 is True, (
            f"Should return True when reading lines 1-5 but read 10-50. "
            f"Got: {should_read2}, reason: {reason2}"
        )
        assert "before first read line" in reason2.lower() or "gap" in reason2.lower() or "beyond" in reason2.lower(), (
            f"Reason should indicate end line is before first read line. Got: {reason2}"
        )
        
        # Test with end=30 (within read range 10-50)
        should_read3, reason3 = memory.should_read_file("/test/file.py", end=30)
        assert should_read3 is True, (
            f"Should return True when reading lines 1-30 but only read 10-50 "
            f"(need lines 1-9). Got: {should_read3}, reason: {reason3}"
        )
        assert "may need to read lines before" in reason3.lower() or "before" in reason3.lower() or "beyond" in reason3.lower(), (
            f"Reason should indicate need to read lines before 10. Got: {reason3}"
        )

    def test_memory_should_read_file_lines_read_none(self):
        """Test should_read_file when lines_read is None (e.g., from deserialization).
        
        BUG: Currently raises AttributeError when lines_read is None.
        Should handle gracefully and return True with appropriate reason.
        """
        memory = WorkingMemory(current_task="Test")
        
        # Create an entry with lines_read=None (simulating deserialization from YAML)
        # We need to bypass the normal constructor to set lines_read=None
        from dataclasses import replace
        entry = WorkingMemoryEntry("/test/file.py", "Test", "full")
        entry_with_none = replace(entry, lines_read=None)  # type: ignore
        
        # Add to memory directly (not through add_recent_file which would normalize path)
        memory.recent_files.append(entry_with_none)
        
        # Call should_read_file - should NOT raise AttributeError
        # Should return True with appropriate reason
        should_read, reason = memory.should_read_file("/test/file.py", 10, 50)
        
        # Since lines_read is None (means "no lines read"), we should return True
        # with reason indicating no lines have been read
        assert should_read is True, (
            f"Should return True when lines_read is None (no lines read). "
            f"Got: {should_read}, reason: {reason}"
        )
        # lines_read=None is valid (means "no lines read"), same as lines_read=""
        assert "no lines have been read" in reason.lower(), (
            f"Reason should indicate no lines have been read. Got: {reason}"
        )

    def test_memory_should_read_file_full_with_invalid_line_numbers_bug(self):
        """Test should_read_file bug: invalid line numbers should be reported even when file was read fully.
        
        BUG: When file was read fully (lines_read='full') and invalid line numbers are provided
        (e.g., start=0, end=-1, or start > end), the method returns "File already read (full)"
        instead of reporting the line number validation error.
        
        Line number validation should happen BEFORE checking if file was read fully.
        """
        memory = WorkingMemory(current_task="Test")
        memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "full"))
        
        # Test 1: Invalid start line (0) - should report line number error, not "already read"
        should_read, reason = memory.should_read_file("/test/file.py", 0, 10)
        assert should_read is True, (
            f"Invalid line number start=0 should return True with error, "
            f"not False (file was read fully). Got: {should_read}, reason: {reason}"
        )
        assert "invalid" in reason.lower() or "positive" in reason.lower() or "must be positive" in reason.lower(), (
            f"Should report invalid line number error, not 'File already read (full)'. "
            f"Got reason: {reason}"
        )
        assert "already read" not in reason.lower(), (
            f"Should NOT say 'already read' when line numbers are invalid. Got: {reason}"
        )
        
        # Test 2: Invalid end line (0) - should report line number error
        should_read, reason = memory.should_read_file("/test/file.py", 1, 0)
        assert should_read is True
        assert "invalid" in reason.lower() or "positive" in reason.lower() or "must be positive" in reason.lower()
        assert "already read" not in reason.lower()
        
        # Test 3: Negative start line (-5) - should report line number error
        should_read, reason = memory.should_read_file("/test/file.py", -5, 10)
        assert should_read is True
        assert "invalid" in reason.lower() or "positive" in reason.lower() or "must be positive" in reason.lower()
        assert "already read" not in reason.lower()
        
        # Test 4: start > end (10 > 5) - should report line range error
        should_read, reason = memory.should_read_file("/test/file.py", 10, 5)
        assert should_read is True
        assert "invalid" in reason.lower() or "start.*>.*end" in reason.lower() or "greater than" in reason.lower()
        assert "already read" not in reason.lower()
        
        # Test 5: Valid line numbers should still return False (file read fully)
        should_read, reason = memory.should_read_file("/test/file.py", 10, 50)
        assert should_read is False
        assert "already read" in reason.lower()
        
        # Test 6: Partial range with invalid start (start=0, end=None)
        should_read, reason = memory.should_read_file("/test/file.py", start=0)
        assert should_read is True
        assert "invalid" in reason.lower() or "positive" in reason.lower() or "must be positive" in reason.lower()
        assert "already read" not in reason.lower()
        
        # Test 7: Partial range with invalid end (start=None, end=0)
        should_read, reason = memory.should_read_file("/test/file.py", end=0)
        assert should_read is True
        assert "invalid" in reason.lower() or "positive" in reason.lower() or "must be positive" in reason.lower()
        assert "already read" not in reason.lower()

    def test_memory_parse_line_ranges_unicode_dash_bug(self):
        """Test parse_line_ranges bug: doesn't handle Unicode dash characters.
        
        BUG: parse_line_ranges only splits on ASCII hyphen '-', not Unicode dash
        characters like en dash '–' (U+2013) or em dash '—' (U+2014).
        """
        
        # Test with ASCII hyphen (should work)
        result = parse_line_ranges("10-20")
        assert len(result) == 1
        assert result[0].start == 10
        assert result[0].end == 20
        
        # Test with en dash (U+2013) – should work now
        result = parse_line_ranges("10–20")  # en dash
        assert len(result) == 1
        assert result[0].start == 10
        assert result[0].end == 20
        
        # Test with em dash (U+2014) – should work now
        result = parse_line_ranges("10—20")  # em dash
        assert len(result) == 1
        assert result[0].start == 10
        assert result[0].end == 20
        
        # Test with multiple ranges using en dashes
        result = parse_line_ranges("10–20,30–40")  # en dashes
        assert len(result) == 2
        assert result[0].start == 10
        assert result[0].end == 20
        assert result[1].start == 30
        assert result[1].end == 40
        
        # Test with spaces and en dash
        result = parse_line_ranges("10 – 20")  # space, en dash, space
        assert len(result) == 1
        assert result[0].start == 10
        assert result[0].end == 20
        
        # Test with multiple ASCII hyphens (should work)
        result = parse_line_ranges("10-20,30-40")
        assert len(result) == 2
        assert result[0].start == 10
        assert result[0].end == 20
        assert result[1].start == 30
        assert result[1].end == 40
        
        # Test with figure dash (U+2012) – should work now
        result = parse_line_ranges("10‒20")  # figure dash U+2012
        assert len(result) == 1
        assert result[0].start == 10
        assert result[0].end == 20
        
        # Test with minus sign (U+2212) – should work now
        result = parse_line_ranges("10−20")  # minus sign U+2212
        assert len(result) == 1
        assert result[0].start == 10
        assert result[0].end == 20
        
        # Test with horizontal bar (U+2015) – should work now
        result = parse_line_ranges("10―20")  # horizontal bar U+2015
        assert len(result) == 1
        assert result[0].start == 10
        assert result[0].end == 20
    
    def test_memory_parse_line_ranges_invalid_parts_silently_ignored_bug(self):
        """Test parse_line_ranges: invalid parts are silently ignored.
        
        BUG: Invalid parts like "invalid-format" or "10-20-30" should be
        silently ignored, not cause errors.
        """
        # Test with invalid part in the middle
        result = parse_line_ranges("1-10,invalid-format,20-30")
        assert len(result) == 2  # Should parse 1-10 and 20-30, skip invalid-format
        assert result[0].start == 1
        assert result[0].end == 10
        assert result[1].start == 20
        assert result[1].end == 30
        
        # Test with invalid format (too many dashes)
        result = parse_line_ranges("10-20-30")
        assert len(result) == 0  # Should parse as invalid and return empty list
        
        # Test with valid format
        result = parse_line_ranges("1-10,20-30")
        assert len(result) == 2
        assert result[0].start == 1
        assert result[0].end == 10
        assert result[1].start == 20
        assert result[1].end == 30
        This is BETTER than returning empty list because it uses valid information.
        """
        from henchman.agents.working_memory import WorkingMemory
        
        # Test with mixed valid and invalid parts
        result = parse_line_ranges("1-10,invalid-format,20-30")
        # FIXED: Now returns [LineRange(1,10), LineRange(20,30)], skipping "invalid-format"
        # This is BETTER than returning empty list because we can use valid information
        assert len(result) == 2, f"Should skip invalid parts and return valid ranges, got {result}"
        assert result[0].start == 1 and result[0].end == 10
        assert result[1].start == 20 and result[1].end == 30
        
        # Test with multiple dashes (invalid) - should return empty list
        result = parse_line_ranges("10-20-30")
        # "10-20-30" has multiple dashes, can't parse as valid range
        assert result == [], f"Should return empty list for invalid format '10-20-30', got {result}"
        
        # Test with valid format only
        result = parse_line_ranges("1-10,20-30")
        assert len(result) == 2
        assert result[0].start == 1 and result[0].end == 10
        assert result[1].start == 20 and result[1].end == 30

    def test_memory_parse_line_ranges_underscore_bug(self):
        """Test _parse_line_ranges bug: incorrectly parses underscores as valid line numbers.
        
        BUG: Python's int() function accepts underscores in integer literals (e.g., int("10_20") = 1020).
        So "10_20" is incorrectly parsed as line 1020 instead of being rejected as invalid input.
        """
        from henchman.agents.working_memory import WorkingMemory
        
        # Test with underscore (should be rejected, not parsed as 1020)
        result = parse_line_ranges("10_20")
        # BUG: Currently returns [LineRange(1020, 1020)] because int("10_20") = 1020
        # Should return [] because "10_20" is not a valid line range format
        assert result == [], f"Should reject '10_20' as invalid format, got {result}"
        
        # Test with valid number with underscores (Python allows int("1_000_000"))
        result = parse_line_ranges("1_000_000")
        # BUG: Currently returns [LineRange(1000000, 1000000)]
        # Should return [] because "1_000_000" is not a valid line number format
        assert result == [], f"Should reject '1_000_000' as invalid format, got {result}"
        
        # Test mixed: valid range and invalid underscore
        result = parse_line_ranges("10-20,30_40")
        # Should return only [LineRange(10, 20)], skipping "30_40"
        assert len(result) == 1, f"Should skip invalid '30_40' and return only valid ranges, got {result}"
        assert result[0].start == 10 and result[0].end == 20
        
        # Test with other invalid characters
        result = parse_line_ranges("10.5")
        # Should return [] because "10.5" is not a valid integer
        assert result == [], f"Should reject '10.5' as invalid format, got {result}"
        
        # Test with letters
        result = parse_line_ranges("abc")
        # Should return []
        assert result == [], f"Should reject 'abc' as invalid format, got {result}"
        
        # Test with valid input (should still work)
        result = parse_line_ranges("10-20")
        assert len(result) == 1
        assert result[0].start == 10 and result[0].end == 20
        
        # Test with valid single line
        result = parse_line_ranges("42")
        assert len(result) == 1
        assert result[0].start == 42 and result[0].end == 42
