"""Task interruption uses held project owners and never adopts stored PIDs."""
from __future__ import annotations

import asyncio
import sys
from io import StringIO
from threading import Event
from types import SimpleNamespace

import pytest
from rich.console import Console
from textual.widgets import Button, OptionList

from henchman.cli.work_inspection import WorkInspection
from tests.cli.test_textual_work import opened
from tests.cli.test_textual_work import work as work_fixture
from tests.cli.test_work_command import frontend, render

work = work_fixture


async def test_interrupt_joins_the_exact_owned_task(work):
    record = await work.service.start_task(argv=[sys.executable, '-c', 'import time; time.sleep(30)'])
    work.tasks.append(record.task_id)
    current = work.service.get_task(record.task_id)
    process = work.service._runtime.processes[record.task_id]
    final = await WorkInspection(frontend(work)).interrupt_task(record.task_id, expected_revision=current.revision)
    assert final.status == 'stopped'
    assert process.returncode is not None
    assert record.task_id not in work.service._runtime.monitors


async def test_interrupt_refuses_stale_revision_without_stopping_process(work):
    record = await work.service.start_task(argv=[sys.executable, '-c', 'import time; time.sleep(30)'])
    work.tasks.append(record.task_id)
    current = work.service.get_task(record.task_id)
    work.service.update_task(record.task_id, title='changed since selection')
    with pytest.raises(ValueError, match='changed'):
        await WorkInspection(frontend(work)).interrupt_task(record.task_id, expected_revision=current.revision)
    assert work.service._runtime.processes[record.task_id].returncode is None


async def test_interrupt_rechecks_owner_after_acknowledgement(work, monkeypatch):
    record = await work.service.start_task(argv=[sys.executable, '-c', 'import time; time.sleep(30)'])
    work.tasks.append(record.task_id)
    current = work.service.get_task(record.task_id)
    inspection = WorkInspection(frontend(work))
    original = work.service.get_task
    reads = []

    def observed(identity):
        reads.append(identity)
        return original(identity)

    monkeypatch.setattr(work.service, 'get_task', observed)

    def changed():
        work.manager.set_session(work.manager.create_session(work.manager.current.project_hash), history_agent=work.actor)

    with pytest.raises(ValueError, match='changed'):
        await inspection.interrupt_task(record.task_id, expected_revision=current.revision, on_requested=changed)
    assert reads == [record.task_id]
    assert work.service._runtime.processes[record.task_id].returncode is None


async def test_interrupt_rechecks_external_revision_after_acknowledgement(work):
    from henchman.advanced.task_store import TaskStore

    record = await work.service.start_task(argv=[sys.executable, '-c', 'import time; time.sleep(30)'])
    work.tasks.append(record.task_id)
    current = work.service.get_task(record.task_id)
    inspection = WorkInspection(frontend(work))

    def changed():
        other = TaskStore(work.service._index_path)
        raw = next(item for item in other.read() if item['task_id'] == record.task_id)
        other.replace(dict(raw, title='external change'), expected_revision=raw['revision'])

    with pytest.raises(ValueError, match='changed'):
        await inspection.interrupt_task(record.task_id, expected_revision=current.revision, on_requested=changed)
    assert work.service._runtime.processes[record.task_id].returncode is None


async def test_interrupt_refuses_unknown_stored_pid(work, monkeypatch):
    from tests.advanced.test_task_store import record as saved_record

    store = work.service._store
    raw = store.create(saved_record())
    raw = store.replace(dict(raw, status='started', started_at=raw['created_at']), expected_revision=raw['revision'], owner_id='owner-a')
    raw = store.replace(dict(raw, status='running', pid=987654), expected_revision=raw['revision'], owner_id='owner-a')
    monkeypatch.setattr(work.service, 'stop_task', lambda *_: pytest.fail('Adopted an unowned PID'))
    with pytest.raises(ValueError, match='owned'):
        await WorkInspection(frontend(work)).interrupt_task(raw['task_id'], expected_revision=raw['revision'])


async def test_interrupt_refuses_a_task_owned_by_another_event_loop(work):
    record = await work.service.start_task(argv=[sys.executable, '-c', 'import time; time.sleep(30)'])
    work.tasks.append(record.task_id)
    current = work.service.get_task(record.task_id)
    runtime = work.service._runtime
    original = runtime.waiters[record.task_id]
    other_loop = asyncio.new_event_loop()
    runtime.waiters[record.task_id] = other_loop.create_future()
    try:
        with pytest.raises(ValueError, match='owned'):
            await WorkInspection(frontend(work)).interrupt_task(record.task_id, expected_revision=current.revision)
        assert runtime.processes[record.task_id].returncode is None
    finally:
        runtime.waiters[record.task_id] = original
        other_loop.close()


async def test_concurrent_stop_does_not_signal_owned_process_twice(work, monkeypatch):
    record = await work.service.start_task(argv=[sys.executable, '-c', 'import time; time.sleep(30)'])
    work.tasks.append(record.task_id)
    current = work.service.get_task(record.task_id)
    original = work.service._terminate_process
    entered, release = asyncio.Event(), asyncio.Event()
    calls = []

    async def delayed(process):
        calls.append(process)
        entered.set()
        await release.wait()
        await original(process)

    monkeypatch.setattr(work.service, '_terminate_process', delayed)
    first = asyncio.create_task(WorkInspection(frontend(work)).interrupt_task(record.task_id, expected_revision=current.revision))
    second = None
    try:
        await asyncio.wait_for(entered.wait(), 5)
        second = asyncio.create_task(WorkInspection(frontend(work)).interrupt_task(record.task_id, expected_revision=current.revision))
        with pytest.raises(ValueError, match='stopp'):
            await asyncio.wait_for(asyncio.shield(second), 5)
        assert len(calls) == 1
        release.set()
        assert (await first).status == 'stopped'
    finally:
        release.set()
        await asyncio.gather(first, return_exceptions=True)
        if second is not None:
            await asyncio.gather(second, return_exceptions=True)


async def test_session_change_during_lookup_refuses_before_interrupt(work, monkeypatch):
    record = await work.service.start_task(argv=[sys.executable, '-c', 'import time; time.sleep(30)'])
    work.tasks.append(record.task_id)
    current = work.service.get_task(record.task_id)
    inspection = WorkInspection(frontend(work))
    entered, release = Event(), Event()
    original = work.service.get_task

    def blocked(identity):
        entered.set()
        assert release.wait(10)
        return original(identity)

    monkeypatch.setattr(work.service, 'get_task', blocked)
    task = asyncio.create_task(inspection.interrupt_task(record.task_id, expected_revision=current.revision))
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        work.manager.set_session(work.manager.create_session(work.manager.current.project_hash), history_agent=work.actor)
        release.set()
        with pytest.raises(ValueError, match='changed'):
            await task
        assert work.service._runtime.processes[record.task_id].returncode is None
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)


async def test_interruption_of_caller_waits_for_owned_stop(work, monkeypatch):
    record = await work.service.start_task(argv=[sys.executable, '-c', 'import time; time.sleep(30)'])
    work.tasks.append(record.task_id)
    current = work.service.get_task(record.task_id)
    original = work.service.stop_task
    entered, release = asyncio.Event(), asyncio.Event()

    async def delayed(identity):
        entered.set()
        await release.wait()
        return await original(identity)

    monkeypatch.setattr(work.service, 'stop_task', delayed)
    task = None
    try:
        task = asyncio.create_task(WorkInspection(frontend(work)).interrupt_task(record.task_id, expected_revision=current.revision))
        await asyncio.wait_for(entered.wait(), 5)
        task.cancel('first')
        await asyncio.sleep(0)
        task.cancel('second')
        assert not task.done()
        release.set()
        with pytest.raises(asyncio.CancelledError) as error:
            await task
        assert error.value.args == ('first',)
        assert record.task_id not in work.service._runtime.processes
    finally:
        release.set()
        if task is not None:
            await asyncio.gather(task, return_exceptions=True)


async def test_cancel_during_final_lookup_does_not_start_stop(work, monkeypatch):
    record = await work.service.start_task(argv=[sys.executable, '-c', 'import time; time.sleep(30)'])
    work.tasks.append(record.task_id)
    current = work.service.get_task(record.task_id)
    original = work.service.get_task
    entered, release = Event(), Event()
    calls = 0

    def blocked(identity):
        nonlocal calls
        calls += 1
        if calls == 2:
            entered.set()
            assert release.wait(10)
        return original(identity)

    monkeypatch.setattr(work.service, 'get_task', blocked)
    task = asyncio.create_task(WorkInspection(frontend(work)).interrupt_task(record.task_id, expected_revision=current.revision))
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        task.cancel('cancel before stop')
        await asyncio.sleep(0)
        assert not task.done()
        release.set()
        with pytest.raises(asyncio.CancelledError) as error:
            await task
        assert error.value.args == ('cancel before stop',)
        assert work.service._runtime.processes[record.task_id].returncode is None
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.parametrize('size', [(80, 24), (120, 40)])
async def test_textual_stop_uses_inspected_task_and_preserves_draft(work, size):
    from henchman.cli.textual_widgets import HenchmanTextArea

    record = await work.service.start_task(argv=[sys.executable, '-c', 'import time; time.sleep(30)'])
    work.tasks.append(record.task_id)
    process = work.service._runtime.processes[record.task_id]
    async with work.app.run_test(size=size) as pilot:
        composer = work.app.query_one(HenchmanTextArea)
        composer.load_text('draft remains')
        try:
            screen = await opened(work, pilot)
            screen.query_one(OptionList).highlighted = next(i for i, row in enumerate(screen._rows) if row.identity == record.task_id)
            await pilot.pause()
            screen.action_inspect()
            await screen._action_task
            assert not screen.query_one('#work-stop', Button).disabled
            await pilot.press('f6')
            await screen._action_task
            assert process.returncode is not None
            assert work.service.get_task(record.task_id).status == 'stopped'
            assert 'cleanup' in screen._status.lower()
            assert composer.text == 'draft remains'
        finally:
            work.app.core_context = None


async def test_textual_stop_refuses_changed_task_revision(work):
    record = await work.service.start_task(argv=[sys.executable, '-c', 'import time; time.sleep(30)'])
    work.tasks.append(record.task_id)
    async with work.app.run_test() as pilot:
        try:
            screen = await opened(work, pilot)
            screen.query_one(OptionList).highlighted = next(i for i, row in enumerate(screen._rows) if row.identity == record.task_id)
            await pilot.pause()
            screen.action_inspect()
            await screen._action_task
            work.service.update_task(record.task_id, title='changed after inspection')
            screen.action_stop_task()
            await screen._action_task
            assert 'changed' in screen._status.lower()
            assert work.service._runtime.processes[record.task_id].returncode is None
        finally:
            work.app.core_context = None


async def test_textual_stop_refuses_selection_change_during_lookup(work, monkeypatch):
    record = await work.service.start_task(argv=[sys.executable, '-c', 'import time; time.sleep(30)'])
    work.tasks.append(record.task_id)
    entered, release = Event(), Event()
    original = work.service.get_task

    def blocked(identity):
        entered.set()
        assert release.wait(10)
        return original(identity)

    async with work.app.run_test() as pilot:
        try:
            screen = await opened(work, pilot)
            options = screen.query_one(OptionList)
            options.highlighted = next(i for i, row in enumerate(screen._rows) if row.identity == record.task_id)
            await pilot.pause()
            screen.action_inspect()
            await screen._action_task
            monkeypatch.setattr(work.service, 'get_task', blocked)
            screen.action_stop_task()
            assert await asyncio.to_thread(entered.wait, 5)
            options.highlighted = 0
            await pilot.pause()
            release.set()
            await screen._action_task
            assert 'changed' in screen._status.lower()
            assert work.service._runtime.processes[record.task_id].returncode is None
        finally:
            release.set()
            work.app.core_context = None


async def test_closing_inspector_joins_inflight_stop(work, monkeypatch):
    record = await work.service.start_task(argv=[sys.executable, '-c', 'import time; time.sleep(30)'])
    work.tasks.append(record.task_id)
    original = work.service.stop_task
    entered, release = asyncio.Event(), asyncio.Event()

    async def delayed(identity):
        entered.set()
        await release.wait()
        return await original(identity)

    async with work.app.run_test() as pilot:
        try:
            screen = await opened(work, pilot)
            screen.query_one(OptionList).highlighted = next(i for i, row in enumerate(screen._rows) if row.identity == record.task_id)
            await pilot.pause()
            screen.action_inspect()
            await screen._action_task
            monkeypatch.setattr(work.service, 'stop_task', delayed)
            screen.action_stop_task()
            await asyncio.wait_for(entered.wait(), 5)
            assert 'waiting' in screen._status.lower()
            closing = asyncio.create_task(screen.action_back())
            await asyncio.sleep(0)
            assert not closing.done()
            release.set()
            await asyncio.wait_for(closing, 10)
            assert record.task_id not in work.service._runtime.processes
            assert screen._action_task.done()
        finally:
            release.set()
            work.app.core_context = None


@pytest.mark.parametrize('textual', [False, True])
async def test_work_command_stops_exact_owned_task(work, textual):
    record = await work.service.start_task(argv=[sys.executable, '-c', 'import time; time.sleep(30)'])
    work.tasks.append(record.task_id)
    process = work.service._runtime.processes[record.task_id]
    text = await render(work, ['stop', 'task', record.task_id], runtime=frontend(work, textual=textual))
    assert record.task_id in text and 'stopped' in text.lower()
    assert 'requested' in text.lower() and 'cleanup' in text.lower()
    assert process.returncode is not None


async def test_work_command_does_not_adopt_recovered_pid(work, monkeypatch):
    from tests.advanced.test_task_store import record as saved_record

    store = work.service._store
    raw = store.create(saved_record())
    raw = store.replace(dict(raw, status='started', started_at=raw['created_at']), expected_revision=raw['revision'], owner_id='owner-a')
    raw = store.replace(dict(raw, status='running', pid=987654), expected_revision=raw['revision'], owner_id='owner-a')
    monkeypatch.setattr(work.service, 'stop_task', lambda *_: pytest.fail('Adopted an unowned PID'))
    text = await render(work, ['stop', 'task', raw['task_id']])
    assert 'owned' in text.lower()
    assert 'requested' not in text.lower()
    assert raw['task_id'] not in work.service._runtime.processes


async def test_stop_command_routes_as_control_without_starting_work(work):
    from henchman.cli.command_processor import CommandProcessor
    from henchman.cli.workflow import command_route, command_starts_work

    record = await work.service.start_task(argv=[sys.executable, '-c', 'import time; time.sleep(30)'])
    work.tasks.append(record.task_id)
    command = f'/work stop task {record.task_id}'
    output = StringIO()
    handler = SimpleNamespace(renderer=SimpleNamespace(console=Console(file=output)),
                              error=lambda text: pytest.fail(text), muted=lambda *_: None)
    processor = CommandProcessor(handler, SimpleNamespace(registry=work.registry), work.manager, work.app.provider)
    assert command_route(command) == 'control' and not command_starts_work(command)
    assert await processor.handle_command(command, work.actor, frontend(work))
    assert 'stopped' in output.getvalue().lower()
    assert record.task_id not in work.service._runtime.processes
