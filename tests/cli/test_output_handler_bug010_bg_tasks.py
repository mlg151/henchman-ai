"""Tests for BUG-010: _safe_create_task accumulates unreferenceable tasks.

_safe_create_task creates asyncio.Task each call without storing a reference.
_start_rag_indexing calls it each turn, spawning duplicate indexing tasks
without deduplication or cleanup.
"""

from __future__ import annotations

import asyncio
from contextlib import suppress
from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest

from henchman.cli.output_handler import OutputHandler


class TestBug010BackgroundTasks:
    """Verify background tasks from _safe_create_task are managed properly."""

    @pytest.mark.asyncio
    async def test_multiple_calls_should_not_accumulate_tasks(self) -> None:
        """Multiple calls to _start_rag_indexing should cancel previous task."""
        # Simulate a slow-indexing RAG system
        rag_system = MagicMock()
        rag_system.index_async = AsyncMock()
        rag_system.index_async.return_value = "indexed"
        # Simulate is_indexing property
        type(rag_system).is_indexing = PropertyMock(return_value=False)

        handler = _make_handler(rag_system=rag_system)

        # First call creates task
        handler._start_rag_indexing()

        # Let it start running
        await asyncio.sleep(0.01)

        # Verify a task reference exists
        assert hasattr(handler, "_rag_index_task")
        first_task = handler._rag_index_task
        assert isinstance(first_task, asyncio.Task)

        # Second call should cancel previous and create new
        handler._start_rag_indexing()
        await asyncio.sleep(0.01)

        second_task = handler._rag_index_task
        assert isinstance(second_task, asyncio.Task)

        # First task should have been cancelled or completed
        assert first_task.done()

        # Clean up
        if not second_task.done():
            second_task.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await second_task

    @pytest.mark.asyncio
    async def test_start_rag_indexing_cancels_existing_task(self) -> None:
        """If a previous RAG indexing task is still running, cancel it before
        creating a new one (deduplication)."""
        async def never_ending() -> str:
            await asyncio.sleep(3600)
            return "done"

        rag_system = MagicMock()
        rag_system.index_async = never_ending
        type(rag_system).is_indexing = PropertyMock(return_value=False)

        handler = _make_handler(rag_system=rag_system)

        # Call indexing once
        handler._start_rag_indexing()
        await asyncio.sleep(0.01)

        first_task = handler._rag_index_task
        assert not first_task.done()

        # Call it again before first finishes
        handler._start_rag_indexing()
        await asyncio.sleep(0.01)

        # First task should be cancelled/done
        assert first_task.done()

        second_task = handler._rag_index_task
        assert not second_task.done()

        # Clean up
        second_task.cancel()
        with suppress(asyncio.CancelledError, Exception):
            await second_task

    @pytest.mark.asyncio
    async def test_background_task_can_be_awaited_on_shutdown(self) -> None:
        """The stored background task reference should allow awaiting on shutdown."""
        async def slow_index() -> str:
            await asyncio.sleep(0.5)
            return "done"

        rag_system = MagicMock()
        rag_system.index_async = slow_index
        type(rag_system).is_indexing = PropertyMock(return_value=False)

        handler = _make_handler(rag_system=rag_system)

        handler._start_rag_indexing()

        # Test that we can cancel and await the task on shutdown
        task = handler._rag_index_task
        assert not task.done()

        task.cancel()
        with suppress(asyncio.CancelledError, Exception):
            await task

        assert task.done()

    @pytest.mark.asyncio
    async def test_first_call_creates_task(self) -> None:
        """First call to _start_rag_indexing should create and store a task."""
        rag_system = MagicMock()
        rag_system.index_async = AsyncMock()
        rag_system.index_async.return_value = "done"
        type(rag_system).is_indexing = PropertyMock(return_value=False)

        handler = _make_handler(rag_system=rag_system)
        assert not hasattr(handler, "_rag_index_task")

        handler._start_rag_indexing()
        await asyncio.sleep(0.01)

        task = handler._rag_index_task
        assert isinstance(task, asyncio.Task)

        # Clean up
        if not task.done():
            task.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await task

    @pytest.mark.asyncio
    async def test_no_rag_system_skips(self) -> None:
        """When rag_system is None, _start_rag_indexing should do nothing."""
        handler = _make_handler(rag_system=None)
        handler._start_rag_indexing()
        assert not hasattr(handler, "_rag_index_task")


def _make_handler(**overrides: object) -> OutputHandler:
    """Create an OutputHandler with mock dependencies."""
    from henchman.cli.session_manager import ReplSessionManager
    from henchman.cli.tool_manager import ToolManager
    from henchman.cli.ui_renderer import UIRenderer
    from henchman.core.session import Session
    from henchman.providers.base import ModelProvider

    renderer = MagicMock(spec=UIRenderer)
    tool_manager = MagicMock(spec=ToolManager)
    session_manager = MagicMock(spec=ReplSessionManager)
    mock_session = MagicMock(spec=Session)
    mock_session.plan_mode = False
    session_manager.current = mock_session
    provider = MagicMock(spec=ModelProvider)

    return OutputHandler(
        renderer=renderer,
        tool_manager=tool_manager,
        session_manager=session_manager,
        provider=provider,
        **overrides,
    )
