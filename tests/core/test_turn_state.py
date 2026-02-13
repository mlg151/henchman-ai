"""Tests for turn state tracking and loop protection."""

from henchman.core.turn import TurnState, TurnSummary
from henchman.tools.base import ToolResult


class TestTurnState:
    """Tests for TurnState dataclass."""

    def test_default_values(self) -> None:
        """TurnState should have sensible defaults."""
        state = TurnState()
        assert state.start_index == -1  # No protection by default
        assert state.tool_call_ids == set()
        assert state.tool_count == 0
        assert state.iteration == 0
        assert state.protected_tokens == 0
        assert state.files_modified == set()
        assert state.errors_seen == []
        assert state.recent_result_hashes == []

    def test_reset(self) -> None:
        """Reset should clear turn state and set new start index."""
        state = TurnState()
        state.tool_count = 5
        state.iteration = 3
        state.tool_call_ids.add("tc_123")
        state.files_modified.add("/path/to/file.py")
        state.errors_seen.append("some error")

        state.reset(new_start_index=10)

        assert state.start_index == 10
        assert state.tool_call_ids == set()
        assert state.tool_count == 0
        assert state.iteration == 0
        assert state.files_modified == set()
        assert state.errors_seen == []

    def test_record_tool_call(self) -> None:
        """Record tool call should track IDs and detect patterns."""
        state = TurnState()

        # Record first tool call
        state.record_tool_call("tc_001", "read_file", {"path": "/src/main.py"})
        assert "tc_001" in state.tool_call_ids
        assert state.tool_count == 1

        # Record another with file modification (write_file tracks automatically)
        state.record_tool_call("tc_002", "write_file", {"path": "/src/output.py"})
        assert "/src/output.py" in state.files_modified

        # Record with error result
        error_result = ToolResult(content="Error", success=False, error="permission denied")
        state.record_tool_call("tc_003", "shell", {"command": "rm -rf /"}, result=error_result)
        assert "permission denied" in state.errors_seen

    def test_increment_iteration(self) -> None:
        """Iteration increment should update counter."""
        state = TurnState()
        assert state.iteration == 0

        state.increment_iteration()
        assert state.iteration == 1

        state.increment_iteration()
        assert state.iteration == 2

    def test_is_making_progress(self) -> None:
        """Progress detection based on file modifications and tool calls."""
        state = TurnState()

        # No progress initially
        assert not state.is_making_progress()

        # File modification counts as progress
        state.files_modified.add("/path/file.py")
        assert state.is_making_progress()

        # Reset
        state.reset(new_start_index=0)

        # Multiple diverse results count as progress
        for i in range(5):
            result = ToolResult(content=f"unique content {i}")
            state.record_tool_call(f"tc_{i}", "read_file", {"path": f"/file{i}.py"}, result=result)
        assert state.is_making_progress()

    def test_is_spinning_consecutive_duplicates(self) -> None:
        """Detect spinning from consecutive duplicate calls."""
        state = TurnState()

        # First call - use write_file since read operations are now more lenient
        state.record_tool_call("tc_001", "write_file", {"path": "/same/file.py", "content": "test"})
        assert not state.is_spinning()

        # Same call signature
        state.record_tool_call("tc_002", "write_file", {"path": "/same/file.py", "content": "test"})
        assert not state.is_spinning()  # Need 4+ duplicates now (consecutive_duplicates >= 3)

        state.record_tool_call("tc_003", "write_file", {"path": "/same/file.py", "content": "test"})
        assert not state.is_spinning()  # Still need one more

        state.record_tool_call("tc_004", "write_file", {"path": "/same/file.py", "content": "test"})
        assert state.is_spinning()  # 4 consecutive = _consecutive_duplicates = 3

    def test_is_spinning_repeated_results(self) -> None:
        """Detect spinning from repeated result hashes."""
        state = TurnState()

        # Need at least 6 results with 4+ same hashes to trigger this check now
        same_result = ToolResult(content="same content")
        for i in range(6):
            state.record_tool_call(
                f"tc_{i}", "read_file", {"path": f"/file{i}.py"}, result=same_result
            )

        assert state.is_spinning()

    def test_get_adaptive_limit(self) -> None:
        """Adaptive limit should adjust based on progress/spinning."""
        state = TurnState()
        base = 25

        # Base limit
        assert state.get_adaptive_limit(base) == base

        # Progress increases limit
        state.files_modified.add("/file.py")
        assert state.get_adaptive_limit(base) > base

        # Reset and test spinning decreases limit
        state.reset(new_start_index=0)
        state._consecutive_duplicates = 3  # 4+ consecutive calls (threshold increased)
        assert state.get_adaptive_limit(base) < base

    def test_get_status_string(self) -> None:
        """Status string should contain relevant info."""
        state = TurnState()
        state.iteration = 3
        state.tool_count = 5
        state.protected_tokens = 1000
        state.files_modified.add("/path/file.py")

        status = state.get_status_string(base_limit=25)

        assert "3" in status  # iteration
        assert "5" in status  # tool count
        assert "progress" in status  # should show progress due to file modification

    def test_is_approaching_limit(self) -> None:
        """Should detect when approaching iteration limit."""
        state = TurnState()
        base = 25

        # Not at limit initially
        assert not state.is_approaching_limit(base)

        # Past 75% threshold
        state.iteration = 20
        assert state.is_approaching_limit(base)

    def test_is_at_limit(self) -> None:
        """Should detect when at iteration limit."""
        state = TurnState()
        base = 25

        # Not at limit initially
        assert not state.is_at_limit(base)

        # At limit
        state.iteration = 25
        assert state.is_at_limit(base)


class TestTurnSummary:
    """Tests for TurnSummary dataclass."""

    def test_basic_creation(self) -> None:
        """TurnSummary should store turn information."""
        summary = TurnSummary(
            turn_number=1,
            summary_text="Created API endpoint files",
            files_modified=["/src/api.py", "/tests/test_api.py"],
            tool_count=10,
            timestamp="2026-01-23T10:30:00Z",
        )

        assert summary.turn_number == 1
        assert summary.tool_count == 10
        assert len(summary.files_modified) == 2
        assert "API endpoint" in summary.summary_text
