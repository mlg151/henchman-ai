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
        assert problem.status == "open"  # Should not be updated
        assert problem.resolution == ""

    def test_memory_should_read_file_new_file(self):
        """Test should_read_file for a new file."""
        memory = WorkingMemory(current_task="Test")
        should_read, reason = memory.should_read_file("/new/file.py", 1, 100)
        
        assert should_read is True
        assert "not in recent files" in reason

    def test_memory_should_read_file_with_multiple_entries(self):
        """Test should_read_file when there are multiple files in recent_files."""
        memory = WorkingMemory(current_task="Test")
        # Add multiple files
        memory.add_recent_file(WorkingMemoryEntry("/test/file1.py", "Test", "1-50"))
        memory.add_recent_file(WorkingMemoryEntry("/test/file2.py", "Test", "1-100"))
        memory.add_recent_file(WorkingMemoryEntry("/test/file3.py", "Test", "full"))
        
        # Check for file2 (should skip file1 with continue, find file2)
        should_read, reason = memory.should_read_file("/test/file2.py", 60, 150)
        
        # file2 was read lines 1-100, we want 60-150 (overlapping)
        assert should_read is False
        assert "overlapping lines" in reason

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
        
        assert should_read is False
        assert "already read" in reason

    def test_memory_should_read_file_overlapping_lines(self):
        """Test should_read_file for overlapping lines."""
        memory = WorkingMemory(current_task="Test")
        memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "10-50"))
        should_read, reason = memory.should_read_file("/test/file.py", 30, 70)
        
        assert should_read is False
        assert "overlapping lines" in reason

    def test_memory_should_read_file_different_lines(self):
        """Test should_read_file for different lines."""
        memory = WorkingMemory(current_task="Test")
        memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "10-50"))
        should_read, reason = memory.should_read_file("/test/file.py", 60, 100)
        
        assert should_read is True
        assert "different lines" in reason

    def test_memory_should_read_file_full_read(self):
        """Test should_read_file when file was read fully (lines_read='full')."""
        memory = WorkingMemory(current_task="Test")
        memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "full"))
        should_read, reason = memory.should_read_file("/test/file.py", 10, 50)
        
        assert should_read is True
        assert "different lines than previously read" in reason.lower()

    def test_memory_should_read_file_invalid_lines_read(self):
        """Test should_read_file when lines_read is not a valid range."""
        memory = WorkingMemory(current_task="Test")
        # Add with invalid lines_read format
        memory.add_recent_file(WorkingMemoryEntry("/test/file.py", "Test", "invalid-format"))
        should_read, reason = memory.should_read_file("/test/file.py", 10, 50)
        
        assert should_read is True
        assert "different lines than previously read" in reason.lower()

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


class TestWorkingMemorySystem:
    """Test WorkingMemorySystem class."""

    def test_system_creation(self):
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
