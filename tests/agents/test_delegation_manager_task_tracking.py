"""Tests for delegation task tracking (BUG-006).

BUG-006: Background delegation Task not tracked -- cannot be cancelled or
awaited on shutdown.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from henchman.agents.delegation_manager import (
    DelegationManager,
    DelegationTask,
)
from henchman.providers.base import ToolCall

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


# ===========================================================================
# Fixtures
# ===========================================================================


@pytest.fixture
def mock_runner() -> MagicMock:
    """Create a mock DelegationRunner."""
    runner = MagicMock()
    runner.run_delegation = MagicMock(return_value=iter([]))
    return runner


@pytest.fixture
def manager(mock_runner: MagicMock) -> DelegationManager:
    """Create a DelegationManager with mock runner."""
    return DelegationManager(delegation_runner=mock_runner)


@pytest.fixture
def mock_tool_call() -> ToolCall:
    """Create a minimal ToolCall for delegation."""
    return ToolCall(
        id="call_1",
        name="delegate_work",
        arguments={
            "agent": "explorer",
            "task": "Find important files",
            "brief": {},
        },
    )


@pytest.fixture
def mock_agent() -> MagicMock:
    """Create a mock Agent."""
    agent = MagicMock()
    return agent


# ===========================================================================
# Tests for BUG-006
# ===========================================================================


class TestDelegationTaskTracking:
    """Tests that start_delegation properly tracks the asyncio task."""

    @pytest.mark.asyncio
    async def test_start_delegation_stores_asyncio_task(
        self,
        manager: DelegationManager,
        mock_agent: MagicMock,
        mock_tool_call: ToolCall,
    ) -> None:
        """start_delegation must store the asyncio.Task on DelegationTask.asyncio_task.

        Without this, the task cannot be cancelled or awaited on shutdown.
        """
        # The run_delegation on the mock runner returns an empty async generator
        # that completes immediately, so the task completes quickly.
        async def _empty_gen() -> AsyncIterator[object]:
            return
            yield  # pragma: no cover

        manager.delegation_runner.run_delegation = MagicMock(
            return_value=_empty_gen(),
        )

        task_id = await manager.start_delegation(
            source_agent=mock_agent,
            tool_call=mock_tool_call,
            depth=0,
        )

        # The ongoing task should exist
        assert task_id in manager.ongoing_tasks
        delegation_task = manager.ongoing_tasks[task_id]

        # The asyncio_task attribute should be set (not None)
        assert delegation_task.asyncio_task is not None, (
            "start_delegation must store the asyncio.Task reference"
        )
        assert isinstance(delegation_task.asyncio_task, asyncio.Task), (
            "asyncio_task must be an asyncio.Task"
        )

        # Clean up: wait for the task to complete
        delegation_task.asyncio_task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await delegation_task.asyncio_task

    @pytest.mark.asyncio
    async def test_ongoing_task_can_be_cancelled_via_asyncio_task(
        self,
        manager: DelegationManager,
        mock_agent: MagicMock,
        mock_tool_call: ToolCall,
    ) -> None:
        """The stored asyncio.Task must be cancellable."""
        # Create a delegation runner that produces a long-running stream
        async def _long_running() -> AsyncIterator[object]:
            await asyncio.sleep(10)
            yield None  # pragma: no cover

        manager.delegation_runner.run_delegation = MagicMock(
            return_value=_long_running(),
        )

        task_id = await manager.start_delegation(
            source_agent=mock_agent,
            tool_call=mock_tool_call,
            depth=0,
        )

        delegation_task = manager.ongoing_tasks[task_id]

        # The task should be running
        assert delegation_task.asyncio_task is not None
        assert not delegation_task.asyncio_task.done()

        # Cancel the task directly (as shutdown code would)
        delegation_task.asyncio_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await delegation_task.asyncio_task

        assert delegation_task.asyncio_task.done()

    @pytest.mark.asyncio
    async def test_cancel_delegation_cancels_asyncio_task(
        self,
        manager: DelegationManager,
        mock_agent: MagicMock,
        mock_tool_call: ToolCall,
    ) -> None:
        """cancel_delegation must cancel the asyncio.Task, not just task_future.

        Previously it only cancelled task_future, meaning the _run_delegation
        coroutine continued running in the background.
        """
        # Create a delegation runner that never completes
        async def _never_completes() -> AsyncIterator[object]:
            while True:
                await asyncio.sleep(10)
                yield None  # pragma: no cover

        manager.delegation_runner.run_delegation = MagicMock(
            return_value=_never_completes(),
        )

        task_id = await manager.start_delegation(
            source_agent=mock_agent,
            tool_call=mock_tool_call,
            depth=0,
        )

        delegation_task = manager.ongoing_tasks[task_id]
        assert delegation_task.asyncio_task is not None
        assert not delegation_task.asyncio_task.done()

        # Cancel the delegation via the manager method
        result = manager.cancel_delegation(task_id)
        assert result is True

        # Yield control so the event loop delivers CancelledError to the task
        await asyncio.sleep(0)

        # The task should now be done (cancelled)
        assert delegation_task.asyncio_task.done(), (
            "cancel_delegation should have cancelled the asyncio task"
        )

        # The task should have been cancelled (CancelledError raised inside)
        assert delegation_task.asyncio_task.cancelled(), (
            "The asyncio task should be in cancelled state"
        )

        # Verify the task was moved out of ongoing
        assert task_id not in manager.ongoing_tasks

    @pytest.mark.asyncio
    async def test_delegation_task_dataclass_has_asyncio_task_field(
        self,
    ) -> None:
        """DelegationTask must have an asyncio_task field."""
        assert hasattr(DelegationTask, "asyncio_task"), (
            "DelegationTask must have asyncio_task field"
        )

        # Test default value is None
        loop = asyncio.new_event_loop()
        try:
            task_future: asyncio.Future[tuple[str, bool]] = loop.create_future()
            task = DelegationTask(
                id="test_1",
                target_role="explorer",
                task="Test",
                tool_call_id="call_1",
                source_agent=MagicMock(),
                depth=0,
                task_future=task_future,
            )
            assert task.asyncio_task is None, (
                "asyncio_task should default to None"
            )
        finally:
            loop.close()

    @pytest.mark.asyncio
    async def test_cancel_delegation_still_cancels_task_future(
        self,
        manager: DelegationManager,
        mock_agent: MagicMock,
        mock_tool_call: ToolCall,
    ) -> None:
        """cancel_delegation must still cancel task_future for backward compat."""
        async def _never_completes() -> AsyncIterator[object]:
            while True:
                await asyncio.sleep(10)
                yield None  # pragma: no cover

        manager.delegation_runner.run_delegation = MagicMock(
            return_value=_never_completes(),
        )

        task_id = await manager.start_delegation(
            source_agent=mock_agent,
            tool_call=mock_tool_call,
            depth=0,
        )

        delegation_task = manager.ongoing_tasks[task_id]

        # Both futures should be pending
        assert not delegation_task.task_future.done()
        assert not delegation_task.asyncio_task.done()

        manager.cancel_delegation(task_id)

        # Yield control so the event loop delivers CancelledError to the task
        await asyncio.sleep(0)

        # Both should now be done
        assert delegation_task.task_future.done()
        assert delegation_task.asyncio_task.done()
        assert delegation_task.asyncio_task.cancelled()
