"""User interruption is bound to the selected live child conversation."""

from __future__ import annotations

import asyncio
import sys
from dataclasses import replace

import pytest
from textual.widgets import Button, OptionList

from henchman.agents.subagents import subagent_actor
from henchman.cli.work_inspection import WorkInspection
from tests.cli.test_textual_work import opened
from tests.cli.test_textual_work import work as work_fixture
from tests.cli.test_work_command import frontend, render

work = work_fixture


async def test_interrupt_joins_selected_running_agent(work):
    inspection = WorkInspection(frontend(work))
    identity = work.records[0].conversation_id
    record = work.agents.get(identity)
    worker = work.agents._conversations[identity].task
    result = await inspection.interrupt_agent(identity, expected=record, expected_worker=worker)
    assert result.cancelled and result.status == "done"
    assert worker is not None and worker.done()
    assert work.agents.get(work.records[2].conversation_id).status == "waiting_for_input"


async def test_interrupt_does_not_stop_separately_owned_project_tasks(work):
    task = await work.service.start_task(argv=[sys.executable, "-c", "import time; time.sleep(30)"])
    work.tasks.append(task.task_id)
    process = work.service._runtime.processes[task.task_id]
    identity = work.records[0].conversation_id
    conversation = work.agents._conversations[identity]
    result = await WorkInspection(frontend(work)).interrupt_agent(
        identity, expected=conversation.record, expected_worker=conversation.task,
    )
    assert result.cancelled and process.returncode is None


@pytest.mark.parametrize("change", ["record", "session", "selection"])
async def test_interrupt_refuses_stale_agent_before_dispatch(work, change):
    inspection = WorkInspection(frontend(work))
    identity = work.records[0].conversation_id
    conversation = work.agents._conversations[identity]
    record, worker = conversation.record, conversation.task
    selected = True

    def selection_current():
        if not selected:
            raise ValueError("selection changed")

    def changed():
        nonlocal selected
        if change == "record":
            conversation.record = replace(record, output="new observation")
        elif change == "session":
            work.manager.set_session(work.manager.create_session(work.manager.current.project_hash), history_agent=work.actor)
        else:
            selected = False

    with pytest.raises(ValueError, match="changed"):
        await inspection.interrupt_agent(identity, expected=record, expected_worker=worker,
                                         selection_current=selection_current, on_requested=changed)
    assert worker is not None and not worker.done()


async def test_interrupt_waits_for_child_cleanup_even_if_caller_cancelled(work, monkeypatch):
    inspection = WorkInspection(frontend(work))
    identity = work.records[0].conversation_id
    conversation = work.agents._conversations[identity]
    original = work.agents.cancel
    entered, release = asyncio.Event(), asyncio.Event()

    async def delayed(target):
        entered.set()
        await release.wait()
        return await original(target)

    monkeypatch.setattr(work.agents, "cancel", delayed)
    request = asyncio.create_task(inspection.interrupt_agent(identity, expected=conversation.record,
                                                               expected_worker=conversation.task))
    await asyncio.wait_for(entered.wait(), 5)
    request.cancel()
    await asyncio.sleep(0)
    assert not request.done()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await request
    assert conversation.task is not None and conversation.task.done()


@pytest.mark.parametrize("textual", [False, True])
async def test_command_stops_exact_waiting_agent(work, textual):
    identity = work.records[2].conversation_id
    text = await render(work, ["stop", "agent", identity], runtime=frontend(work, textual=textual))
    assert identity in text and "cancelled" in text.lower()
    assert work.agents.get(identity).cancelled
    assert work.agents.get(work.records[0].conversation_id).status == "running"


@pytest.mark.parametrize("size", [(80, 24), (120, 40)])
async def test_textual_stops_selected_waiting_agent(work, size):
    identity = work.records[2].conversation_id
    async with work.app.run_test(size=size) as pilot:
        try:
            screen = await opened(work, pilot)
            options = screen.query_one(OptionList)
            options.highlighted = next(i for i, row in enumerate(screen._rows) if row.identity == identity)
            await pilot.pause()
            screen.action_inspect()
            await screen._action_task
            assert not screen.query_one("#work-stop", Button).disabled
            await pilot.press("f6")
            await screen._action_task
            assert work.agents.get(identity).cancelled
            assert work.agents.get(work.records[0].conversation_id).status == "running"
        finally:
            work.app.core_context = None


async def test_textual_refuses_changed_agent_observation(work):
    identity = work.records[0].conversation_id
    conversation = work.agents._conversations[identity]
    async with work.app.run_test() as pilot:
        try:
            screen = await opened(work, pilot)
            options = screen.query_one(OptionList)
            options.highlighted = next(i for i, row in enumerate(screen._rows) if row.identity == identity)
            await pilot.pause()
            screen.action_inspect()
            await screen._action_task
            conversation.record = replace(conversation.record, output="updated evidence")
            screen.action_stop_task()
            await screen._action_task
            assert "changed" in screen._status.lower()
            assert conversation.task is not None and not conversation.task.done()
        finally:
            work.app.core_context = None


async def test_interrupt_refuses_when_a_stop_is_already_active(work):
    inspection = WorkInspection(frontend(work))
    identity = work.records[0].conversation_id
    conversation = work.agents._conversations[identity]
    work.agents._cancelling.add(identity)
    try:
        with pytest.raises(ValueError, match="already stopping"):
            await inspection.interrupt_agent(identity, expected=conversation.record,
                                             expected_worker=conversation.task)
        assert conversation.task is not None and not conversation.task.done()
    finally:
        work.agents._cancelling.remove(identity)


@pytest.mark.parametrize("scope", ["selected", "descendant"])
async def test_interrupt_refuses_worker_already_cancelling_outside_manager(work, scope):
    inspection = WorkInspection(frontend(work))
    identity = work.records[0].conversation_id
    conversation = work.agents._conversations[identity]
    target = conversation if scope == "selected" else work.agents._conversations[work.records[2].conversation_id]
    original, original_record = target.task, target.record
    if scope == "descendant":
        target.record = replace(original_record, parent_id=identity)
    started, cleaning, release = asyncio.Event(), asyncio.Event(), asyncio.Event()

    async def worker_body():
        started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cleaning.set()
            await release.wait()
            raise

    worker = asyncio.create_task(worker_body())
    target.task = worker
    request = None
    try:
        await started.wait()
        worker.cancel()
        await cleaning.wait()
        request = asyncio.create_task(inspection.interrupt_agent(identity, expected=conversation.record,
                                                                 expected_worker=conversation.task))
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert request.done(), "A second stop must refuse before joining someone else's cleanup"
        with pytest.raises(ValueError, match="already stopping"):
            await request
        assert not worker.done()
    finally:
        release.set()
        if request is not None:
            await asyncio.gather(request, return_exceptions=True)
        await asyncio.gather(worker, return_exceptions=True)
        target.task, target.record = original, original_record


async def test_interrupt_refuses_while_descendant_cleanup_is_active(work):
    inspection = WorkInspection(frontend(work))
    identity, descendant = (work.records[i].conversation_id for i in (0, 2))
    conversation = work.agents._conversations[identity]
    nested = work.agents._conversations[descendant]
    original = nested.record
    nested.record = replace(original, parent_id=identity)
    work.agents._cancelling.add(descendant)
    try:
        with pytest.raises(ValueError, match="already stopping"):
            await inspection.interrupt_agent(identity, expected=conversation.record,
                                             expected_worker=conversation.task)
        assert conversation.task is not None and not conversation.task.done()
    finally:
        work.agents._cancelling.remove(descendant)
        nested.record = original


async def test_interrupt_joins_descendants_and_discards_pending_followups(work):
    parent = work.records[0].conversation_id
    parent_conversation = work.agents._conversations[parent]
    parent_conversation.record = replace(parent_conversation.record, tools=("invoke_subagent",))
    work.agents._available_tools = lambda _: ["invoke_subagent"]
    with subagent_actor(parent):
        child = work.agents.spawn("run", role="nested", system_prompt="nested", tools=[])
    await asyncio.sleep(0)
    await work.agents.send_message(parent, "pending follow-up")
    assert not parent_conversation.inbox.empty()
    nested = work.agents._conversations[child.conversation_id]
    result = await WorkInspection(frontend(work)).interrupt_agent(
        parent, expected=parent_conversation.record, expected_worker=parent_conversation.task,
    )
    assert result.cancelled and parent_conversation.inbox.empty()
    assert nested.task is not None and nested.task.done() and nested.record.cancelled
    assert work.agents.get(work.records[2].conversation_id).status == "waiting_for_input"
