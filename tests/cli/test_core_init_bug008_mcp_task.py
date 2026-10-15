"""Tests for BUG-008: Fire-and-forget create_task for MCP connection.

initialize_mcp in core_init.py creates a fire-and-forget task that cannot
be awaited on shutdown. The fix stores the task on CoreContext so that
shutdown code can await/cancel it.
"""

from __future__ import annotations

import asyncio
from contextlib import suppress
from unittest.mock import AsyncMock, MagicMock

import pytest

from henchman.cli.core_init import CoreContext, initialize_mcp
from henchman.mcp.manager import McpManager


class TestBug008McpInitTask:
    """Verify the MCP init task is stored and can be awaited."""

    @pytest.mark.asyncio
    async def test_initialize_mcp_stores_task_on_context(self) -> None:
        """initialize_mcp should store the background task on context.background_tasks."""
        mcp_manager = MagicMock(spec=McpManager)
        mcp_manager.clients = {}  # Empty dict -- triggers connection
        mcp_manager.connect_all = AsyncMock()
        mcp_manager.get_all_tools = MagicMock(return_value=[])

        context = _make_mock_context()
        context.mcp_manager = mcp_manager
        context.tool_registry = MagicMock()

        initialize_mcp(context)

        # Verify a background task was stored
        assert len(context.background_tasks) > 0
        task = next(iter(context.background_tasks))
        assert isinstance(task, asyncio.Task)
        assert not task.done()

        # Clean up
        task.cancel()
        with suppress(asyncio.CancelledError, Exception):
            await task

    @pytest.mark.asyncio
    async def test_initialize_mcp_skips_when_already_connected(self) -> None:
        """When mcp_manager has clients, initialize_mcp should not create a task."""
        mcp_manager = MagicMock(spec=McpManager)
        mcp_manager.clients = {"existing": MagicMock()}  # Already has clients

        context = _make_mock_context()
        context.mcp_manager = mcp_manager
        context.tool_registry = MagicMock()

        initialize_mcp(context)

        # No task should be created
        assert len(context.background_tasks) == 0

    @pytest.mark.asyncio
    async def test_initialize_mcp_noop_when_no_mcp_manager(self) -> None:
        """When mcp_manager is None, initialize_mcp should do nothing."""
        context = _make_mock_context()
        context.mcp_manager = None

        initialize_mcp(context)

        assert len(context.background_tasks) == 0

    @pytest.mark.asyncio
    async def test_background_tasks_can_be_awaited_on_shutdown(self) -> None:
        """Background tasks stored on CoreContext can be awaited during shutdown."""
        mcp_manager = MagicMock(spec=McpManager)
        mcp_manager.clients = {}
        mcp_manager.connect_all = AsyncMock()
        mcp_manager.get_all_tools = MagicMock(return_value=[])

        context = _make_mock_context()
        context.mcp_manager = mcp_manager
        context.tool_registry = MagicMock()

        initialize_mcp(context)

        # Simulate shutdown: await all background tasks
        tasks = list(context.background_tasks)
        # Allow the mock connection to complete so the task finishes
        await asyncio.sleep(0.01)

        for task in tasks:
            if not task.done():
                task.cancel()

        await asyncio.gather(*tasks, return_exceptions=True)

        # All tasks should be done now (either completed or cancelled)
        for task in tasks:
            assert task.done()

    @pytest.mark.asyncio
    async def test_background_task_failure_does_not_crash(self) -> None:
        """If the MCP connection task fails, it should be catchable, not crash."""
        mcp_manager = MagicMock(spec=McpManager)
        mcp_manager.clients = {}
        mcp_manager.connect_all = AsyncMock(side_effect=RuntimeError("MCP failed"))
        mcp_manager.get_all_tasks = MagicMock(return_value=[])
        mcp_manager.get_all_tools = MagicMock(return_value=[])

        context = _make_mock_context()
        context.mcp_manager = mcp_manager
        context.tool_registry = MagicMock()

        initialize_mcp(context)

        # Let the task run to completion (it will fail with RuntimeError)
        await asyncio.sleep(0.05)

        tasks = list(context.background_tasks)
        # The task should have completed (with exception, but still done)
        for task in tasks:
            if not task.done():
                task.cancel()

        await asyncio.gather(*tasks, return_exceptions=True)
        for task in tasks:
            assert task.done()


def _make_mock_context() -> MagicMock:
    """Create a MagicMock that supports background_tasks set."""
    m = MagicMock(spec=CoreContext)
    # Dataclass fields with defaults don't appear in spec lookups,
    # so we must attach background_tasks explicitly.
    m.background_tasks = set()
    return m
