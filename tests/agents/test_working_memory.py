"""Tests for working memory system."""

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
        """Test updating a problem that doesn't exist (should do nothing)."""
        memory = WorkingMemory(current_task="Test")
        memory.add_problem(ProblemEntry("Test failing", "open", ""))
        # Try to update a non-existent problem
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
        
        # BUG: File was only partially read (lines 10-50), but calling without line range
        # means "should I read the whole file?" Answer should be YES because we haven't
        # read lines 1-9 or 51-end.
        # Current buggy behavior returns False
        assert should_read is True, "File was only partially read (10-50), should read whole file when no line range specified"
        assert "not fully read" in reason.lower() or "partial" in reason.lower() or "need to read" in reason.lower()

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
        # Add with invalid lines_read format
        memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "invalid-format"))
        should_read, reason = memory.should_read_file("/test/file.py", 10, 50)
        
        assert should_read is True
        assert "invalid lines_read format" in reason.lower()

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
        
        # get_file_insights should return insights from MOST RECENT entry
        insights = memory.get_file_insights("/test/file.py")
        # BUG: Currently returns ["Old insight 1", "Old insight 2"] from first entry
        # Should return ["New insight 1", "New insight 2", "New insight 3"] from most recent
        assert insights == ["New insight 1", "New insight 2", "New insight 3"], (
            f"Bug: get_file_insights returns {insights}, expected insights from most recent entry. "
            "Should use reversed(self.recent_files) like should_read_file does."
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
        
        # Test with mixed case "Full"
        memory2 = WorkingMemory(current_task="Test")
        memory2.add_recent_file(WorkingMemoryEntry("/test/file2.py", "Test", "Full"))
        should_read2, reason2 = memory2.should_read_file("/test/file2.py", 10, 50)
        
        assert should_read2 is False, "File read fully (Full) should return False for any line range"
        assert "already read" in reason2.lower()
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
        """Test should_read_file when file was read fully then partially (bug fix)."""
        memory = WorkingMemory(current_task="Test")
        
        # Full read (older)
        memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Full read", "full"))
        # Partial read (newer) 
        memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Partial read", "10-50"))
        
        # Test 1: Lines in partial read (10-50) - should be False
        should_read, reason = memory.should_read_file("/test/file.py", 20, 40)
        assert should_read is False, f"Lines 20-40 should be already read (in partial read). Got: {should_read}"
        assert "already read" in reason.lower()
        
        # Test 2: Lines NOT in partial read but in full read (60-100) - BUG: currently returns True
        should_read, reason = memory.should_read_file("/test/file.py", 60, 100)
        # This should be False because file was read fully earlier
        assert should_read is False, (
            f"BUG: Lines 60-100 should be already read (in full read). Got: {should_read}, reason: {reason}. "
            "File was read fully earlier, so any lines should be considered already read."
        )
        assert "already read" in reason.lower()
        
        # Test 3: Lines spanning both (1-100) - should be False
        should_read, reason = memory.should_read_file("/test/file.py", 1, 100)
        assert should_read is False, f"Lines 1-100 should be already read (in full read). Got: {should_read}"
        assert "already read" in reason.lower()
        
        # Test 4: Reverse order (partial then full) - should work correctly
        memory2 = WorkingMemory(current_task="Test")
        memory2.add_recent_file(WorkingMemoryEntry("/test/file2.py", "Partial read", "10-50"))
        memory2.add_recent_file(WorkingMemoryEntry("/test/file2.py", "Full read", "full"))
        
        should_read2, reason2 = memory2.should_read_file("/test/file2.py", 60, 100)
        assert should_read2 is False, f"Lines 60-100 should be already read (full read is most recent). Got: {should_read2}"
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
