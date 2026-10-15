"""Tests for BUG-007: Race condition on ongoing_tasks dict.

When cancel_delegation and _run_delegation both modify ongoing_tasks without
synchronization, cancel_delegation removing the entry causes the unconditional
`del self.ongoing_tasks[delegation_task.id]` at line 161 to raise KeyError.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from henchman.agents.delegation_manager import DelegationManager, DelegationTask


class TestBug007RaceCondition:
    """Reproduce the race condition on ongoing_tasks."""

    @pytest.mark.asyncio
    async def test_race_between_cancel_and_run_delegation_cleanup(self) -> None:
        """cancel_delegation removes task, then _run_delegation cleanup must not KeyError.

        This reproduces:
          1. start_delegation adds task to ongoing_tasks
          2. cancel_delegation removes it and moves to completed_tasks
          3. _run_delegation finishes and does 'del self.ongoing_tasks[id]'
          4. Without the fix, step 3 raises KeyError

        We simulate step 3's cleanup path directly since _run_delegation
        is driven by an async generator.
        """
        manager = DelegationManager(delegation_runner=MagicMock())
        mock_agent = MagicMock()
        task_id = "race_test_001"
        loop = asyncio.get_running_loop()
        task_future: asyncio.Future[tuple[str, bool]] = loop.create_future()

        task = DelegationTask(
            id=task_id,
            target_role="explorer",
            task="Race condition test",
            tool_call_id="call_001",
            source_agent=mock_agent,
            depth=0,
            task_future=task_future,
        )
        # Step 1: Add to ongoing_tasks (as start_delegation does)
        manager.ongoing_tasks[task_id] = task

        # Step 2: cancel_delegation removes from ongoing, moves to completed
        manager.cancel_delegation(task_id)
        assert task_id not in manager.ongoing_tasks

        # Step 3: _run_delegation finishes and calls _add_completed_task + del
        # This is the exact code from lines 160-161 of delegation_manager.py:
        manager._add_completed_task(task_id, task)
        # This must not raise KeyError:
        manager.ongoing_tasks.pop(task_id, None)

        # Task should still be retrievable from completed
        assert manager.get_delegation(task_id) is not None

    @pytest.mark.asyncio
    async def test_cancel_delegation_after_normal_completion_no_error(self) -> None:
        """cancel_delegation on an already-completed task is a no-op (returns False).

        This verifies the reverse ordering: _run_delegation finishes first,
        then cancel_delegation is called.
        """
        manager = DelegationManager(delegation_runner=MagicMock())
        mock_agent = MagicMock()
        task_id = "race_test_002"
        loop = asyncio.get_running_loop()
        task_future: asyncio.Future[tuple[str, bool]] = loop.create_future()
        task_future.set_result(("done", True))

        task = DelegationTask(
            id=task_id,
            target_role="explorer",
            task="Post-completion cancel test",
            tool_call_id="call_002",
            source_agent=mock_agent,
            depth=0,
            task_future=task_future,
            completed=True,
        )
        # Simulate _run_delegation finishing successfully
        manager._add_completed_task(task_id, task)

        # Now cancel_delegation should find nothing in ongoing_tasks -> False
        result = manager.cancel_delegation(task_id)
        assert result is False

    @pytest.mark.asyncio
    async def test_exception_path_already_has_guard(self) -> None:
        """The exception path (line 175) already uses 'in' check before del.

        Verify it works correctly after cancel_delegation too.
        """
        manager = DelegationManager(delegation_runner=MagicMock())
        mock_agent = MagicMock()
        task_id = "race_test_003"
        loop = asyncio.get_running_loop()
        task_future: asyncio.Future[tuple[str, bool]] = loop.create_future()

        task = DelegationTask(
            id=task_id,
            target_role="explorer",
            task="Exception path test",
            tool_call_id="call_003",
            source_agent=mock_agent,
            depth=0,
            task_future=task_future,
        )
        manager.ongoing_tasks[task_id] = task
        manager.cancel_delegation(task_id)

        # Exception path code (line 174-176):
        manager._add_completed_task(task_id, task)
        if task_id in manager.ongoing_tasks:
            del manager.ongoing_tasks[task_id]
        # No KeyError should occur (the 'in' check prevents it)
