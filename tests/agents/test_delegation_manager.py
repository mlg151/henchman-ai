"""Tests for delegation_manager.py - covers new async delegation system."""

from __future__ import annotations

import asyncio
from collections import OrderedDict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from henchman.agents.delegation_manager import (
    MAX_COMPLETED_TASKS,
    DelegationManager,
    DelegationTask,
)


class TestDelegationTask:
    """Tests for DelegationTask dataclass."""

    def test_delegation_task_creation(self) -> None:
        """Test DelegationTask can be created with required fields."""
        mock_agent = MagicMock()
        mock_future: asyncio.Future[tuple[str, bool]] = asyncio.Future()

        task = DelegationTask(
            id="test_1",
            target_role="explorer",
            task="Find files",
            tool_call_id="call_123",
            source_agent=mock_agent,
            depth=0,
            task_future=mock_future,
        )

        assert task.id == "test_1"
        assert task.target_role == "explorer"
        assert task.task == "Find files"
        assert task.depth == 0
        assert task.completed is False
        assert task.error is None
        assert len(task.output_buffer) == 0

    def test_delegation_task_output_buffer_bounded(self) -> None:
        """Test output_buffer has maxlen=100."""
        mock_agent = MagicMock()
        mock_future: asyncio.Future[tuple[str, bool]] = asyncio.Future()

        task = DelegationTask(
            id="test_1",
            target_role="explorer",
            task="Find files",
            tool_call_id="call_123",
            source_agent=mock_agent,
            depth=0,
            task_future=mock_future,
        )

        # Fill beyond maxlen
        for i in range(150):
            task.output_buffer.append(f"line_{i}")

        # Should be bounded to 100
        assert len(task.output_buffer) == 100
        assert "line_50" in task.output_buffer  # First entries should be evicted
        assert "line_149" in task.output_buffer  # Last entries should remain


class TestDelegationManager:
    """Tests for DelegationManager class."""

    @pytest.fixture
    def mock_runner(self) -> MagicMock:
        """Create a mock DelegationRunner."""
        runner = MagicMock()
        runner.run_delegation = MagicMock(return_value=iter([]))
        return runner

    @pytest.fixture
    def manager(self, mock_runner: MagicMock) -> DelegationManager:
        """Create a DelegationManager with mock runner."""
        return DelegationManager(delegation_runner=mock_runner)

    def test_init(self, manager: DelegationManager, mock_runner: MagicMock) -> None:
        """Test DelegationManager initialization."""
        assert manager.delegation_runner is mock_runner
        assert isinstance(manager.completed_tasks, OrderedDict)
        assert len(manager.completed_tasks) == 0
        assert manager._task_counter == 0

    def test_get_delegation_not_found(self, manager: DelegationManager) -> None:
        """Test get_delegation returns None for unknown task."""
        result = manager.get_delegation("nonexistent")
        assert result is None

    def test_get_ongoing_delegations_empty(self, manager: DelegationManager) -> None:
        """Test get_ongoing_delegations returns empty list when no tasks."""
        result = manager.get_ongoing_delegations()
        assert result == []

    def test_completed_tasks_bounded(self, manager: DelegationManager) -> None:
        """Test completed_tasks respects MAX_COMPLETED_TASKS limit."""
        mock_agent = MagicMock()

        # Patch MAX_COMPLETED_TASKS to a smaller value for testing
        with patch("henchman.agents.delegation_manager.MAX_COMPLETED_TASKS", 100):
            # Add more tasks than the limit
            for i in range(110):
                task_id = f"task_{i}"
                mock_future: asyncio.Future[tuple[str, bool]] = asyncio.Future()
                mock_future.set_result((f"result_{i}", True))

                task = DelegationTask(
                    id=task_id,
                    target_role="explorer",
                    task=f"Task {i}",
                    tool_call_id=f"call_{i}",
                    source_agent=mock_agent,
                    depth=0,
                    task_future=mock_future,
                    completed=True,
                )
                manager._add_completed_task(task_id, task)

            # Should be bounded to 100
            assert len(manager.completed_tasks) == 100

            # Oldest should be evicted
            assert "task_0" not in manager.completed_tasks
            assert "task_10" in manager.completed_tasks  # Within last 100

    def test_add_completed_task_eviction_logging(self, manager: DelegationManager) -> None:
        """Test that eviction is logged."""
        mock_agent = MagicMock()
        mock_logger = MagicMock()

        with patch("henchman.agents.delegation_manager.logger", mock_logger):
            # Add tasks beyond limit
            for i in range(MAX_COMPLETED_TASKS + 5):
                task_id = f"task_{i}"
                mock_future: asyncio.Future[tuple[str, bool]] = asyncio.Future()
                mock_future.set_result((f"result_{i}", True))

                task = DelegationTask(
                    id=task_id,
                    target_role="explorer",
                    task=f"Task {i}",
                    tool_call_id=f"call_{i}",
                    source_agent=mock_agent,
                    depth=0,
                    task_future=mock_future,
                    completed=True,
                )
                manager._add_completed_task(task_id, task)

        # Should have logged evictions
        assert mock_logger.debug.called


class TestDelegationManagerSync:
    """Sync tests for DelegationManager (most methods are not async)."""

    @pytest.fixture
    def mock_runner(self) -> MagicMock:
        """Create a mock DelegationRunner."""
        runner = MagicMock()
        runner.run_delegation = AsyncMock(return_value=iter([]))
        return runner

    @pytest.fixture
    def manager(self, mock_runner: MagicMock) -> DelegationManager:
        """Create a DelegationManager with mock runner."""
        return DelegationManager(delegation_runner=mock_runner)

    @pytest.mark.asyncio
    async def test_wait_for_delegation_timeout(self, manager: DelegationManager) -> None:
        """Test wait_for_delegation times out for unknown task."""
        mock_agent = MagicMock()

        # Create a task but don't complete it
        task_id = "timeout_test"
        mock_future: asyncio.Future[tuple[str, bool]] = asyncio.Future()
        # Don't set result - will cause timeout

        task = DelegationTask(
            id=task_id,
            target_role="explorer",
            task="Test task",
            tool_call_id="call_123",
            source_agent=mock_agent,
            depth=0,
            task_future=mock_future,
        )
        manager.ongoing_tasks[task_id] = task

        # Should timeout
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(
                manager.wait_for_delegation(task_id, timeout=0.1),
                timeout=1.0,
            )

    def test_cancel_delegation_not_found(self, manager: DelegationManager) -> None:
        """Test cancel_delegation returns False for unknown task."""
        result = manager.cancel_delegation("nonexistent")
        assert result is False

    def test_cancel_delegation_success(self, manager: DelegationManager) -> None:
        """Test cancel_delegation marks task as completed."""
        mock_agent = MagicMock()
        task_id = "cancel_test"

        task = DelegationTask(
            id=task_id,
            target_role="explorer",
            task="Test task",
            tool_call_id="call_123",
            source_agent=mock_agent,
            depth=0,
            task_future=asyncio.Future(),
        )
        manager.ongoing_tasks[task_id] = task

        result = manager.cancel_delegation(task_id)
        assert result is True
        assert task.completed is True
        assert task.error == "Cancelled by user"

    def test_tail_delegation_output_not_found(self, manager: DelegationManager) -> None:
        """Test tail_delegation_output returns error for unknown task."""
        result = manager.tail_delegation_output("nonexistent")
        assert "not found" in result

    def test_tail_delegation_output(self, manager: DelegationManager) -> None:
        """Test tail_delegation_output returns last N lines."""
        mock_agent = MagicMock()
        task_id = "tail_test"
        mock_future: asyncio.Future[tuple[str, bool]] = asyncio.Future()
        mock_future.set_result(("done", True))

        task = DelegationTask(
            id=task_id,
            target_role="explorer",
            task="Test task",
            tool_call_id="call_123",
            source_agent=mock_agent,
            depth=0,
            task_future=mock_future,
            completed=True,
        )

        # Add some output
        for i in range(50):
            task.output_buffer.append(f"output line {i}")

        manager.completed_tasks[task_id] = task

        # Get last 10 lines
        result = manager.tail_delegation_output(task_id, lines=10)
        assert "output line 40" in result
        assert "output line 49" in result

    def test_submit_delegation_result_not_found(self, manager: DelegationManager) -> None:
        """Test submit_delegation_result returns False for unknown task."""
        result = manager.submit_delegation_result("nonexistent")
        assert result is False

    def test_submit_delegation_result_incomplete(self, manager: DelegationManager) -> None:
        """Test submit_delegation_result returns False for incomplete task."""
        mock_agent = MagicMock()
        task_id = "incomplete_test"
        mock_future: asyncio.Future[tuple[str, bool]] = asyncio.Future()
        # Don't set result - task is not done

        task = DelegationTask(
            id=task_id,
            target_role="explorer",
            task="Test task",
            tool_call_id="call_123",
            source_agent=mock_agent,
            depth=0,
            task_future=mock_future,
        )
        manager.completed_tasks[task_id] = task

        result = manager.submit_delegation_result(task_id)
        assert result is False


class TestMaxCompletedTasksConstant:
    """Tests for MAX_COMPLETED_TASKS constant."""

    def test_max_completed_tasks_value(self) -> None:
        """Verify MAX_COMPLETED_TASKS is 10000."""
        assert MAX_COMPLETED_TASKS == 10000

    def test_max_completed_tasks_is_int(self) -> None:
        """Verify MAX_COMPLETED_TASKS is an integer."""
        assert isinstance(MAX_COMPLETED_TASKS, int)
        assert MAX_COMPLETED_TASKS > 0
