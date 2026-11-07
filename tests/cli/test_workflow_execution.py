"""Interrupt settles only after the actual input worker's cleanup is joined."""

import asyncio

import pytest

from henchman.cli.workflow import execute_workflow_input
from tests.core.test_session_workflow import controller


async def test_cancel_keeps_authority_until_worker_cleanup_finishes(tmp_path):
    runtime, _, _ = controller(tmp_path)
    runtime.submit("running")
    runtime.submit("pending")
    dispatch = runtime.next_input()
    started, cleaning, release = asyncio.Event(), asyncio.Event(), asyncio.Event()

    async def work():
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cleaning.set()
            await release.wait()

    task = asyncio.create_task(execute_workflow_input(runtime, dispatch, work))
    await started.wait()
    task.cancel()
    await cleaning.wait()
    assert runtime.has_active_dispatch()
    assert runtime.report().state.inputs[0].state == "started"
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not runtime.has_active_dispatch()
    assert runtime.report().state.inputs[0].state == "outcome_unknown"
    assert runtime.next_input() is None


async def test_known_failure_preserves_pending_input_for_next_turn(tmp_path):
    runtime, _, _ = controller(tmp_path)
    runtime.submit("failed")
    runtime.submit("next")
    dispatch = runtime.next_input()

    async def fail():
        raise RuntimeError("known failure")

    with pytest.raises(RuntimeError):
        await execute_workflow_input(runtime, dispatch, fail)
    assert runtime.report().state.inputs[0].outcome == "failure"
    assert runtime.next_input().text == "next"
