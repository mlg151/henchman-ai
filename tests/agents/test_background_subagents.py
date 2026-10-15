"""Independent dynamic conversations, scoped messages, and reactive lifecycle updates."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

import pytest

from henchman.agents.subagents import BackgroundSubagentManager, subagent_actor
from henchman.core.events import AgentEvent, EventType


def manager_for(runner: Any, *, max_output_chars: int = 32768) -> BackgroundSubagentManager:
    return BackgroundSubagentManager(
        factory=lambda role, prompt, tools, conversation_id: {
            "role": role,
            "prompt": prompt,
            "tools": tools,
            "id": conversation_id,
        },
        runner=runner,
        available_tools=lambda _actor: ["read_file", "invoke_subagent", "send_message"],
        max_output_chars=max_output_chars,
    )


async def completed(manager: BackgroundSubagentManager) -> Any:
    return await asyncio.wait_for(manager.wait_for_notification(), timeout=1)


async def test_spawn_returns_without_waiting_and_conversations_are_independent() -> None:
    release = asyncio.Event()
    started: list[str] = []

    async def runner(_agent: Any, _prompt: str) -> AsyncIterator[AgentEvent]:
        started.append(_agent["id"])
        await release.wait()
        yield AgentEvent(EventType.CONTENT, _prompt)

    manager = manager_for(runner)
    try:
        first = manager.spawn(
            "first", role="researcher", system_prompt="custom", tools=["read_file"]
        )
        second = manager.spawn("second", role="researcher", system_prompt="other", tools=[])
        assert first.conversation_id != second.conversation_id
        assert first.status == "running"
        await asyncio.sleep(0)
        assert set(started) == {first.conversation_id, second.conversation_id}
        release.set()
        await completed(manager)
        await completed(manager)
        assert manager.get(first.conversation_id).output == "first"
        assert manager.get(second.conversation_id).output == "second"
        assert not manager.has_running_work()
    finally:
        await manager.close()


async def test_followups_are_fifo_without_overlapping_runs_and_preserve_conversation() -> None:
    release = asyncio.Event()
    active = 0
    seen: list[tuple[int, str]] = []

    async def runner(_agent: Any, _prompt: str) -> AsyncIterator[AgentEvent]:
        nonlocal active
        active += 1
        assert active == 1
        seen.append((id(_agent), _prompt))
        await release.wait()
        active -= 1
        yield AgentEvent(EventType.CONTENT, _prompt)

    manager = manager_for(runner)
    try:
        record = manager.spawn("initial", role="role", system_prompt="system", tools=[])
        await manager.send_message(record.conversation_id, "queued")
        release.set()
        await completed(manager)
        await completed(manager)
        assert [item[1] for item in seen] == ["initial", "queued"]
        assert len({item[0] for item in seen}) == 1
        assert manager.get(record.conversation_id).status == "done"
        await manager.send_message(record.conversation_id, "followup")
        await completed(manager)
        assert seen[-1] == (seen[0][0], "followup")
    finally:
        await manager.close()


async def test_waiting_for_input_notifies_parent_and_resumes_on_message() -> None:
    async def runner(_agent: Any, _prompt: str) -> AsyncIterator[AgentEvent]:
        answer = await manager.request_input("Which file?")
        yield AgentEvent(EventType.CONTENT, f"Answer: {answer}")

    manager = manager_for(runner)
    try:
        record = manager.spawn("task", role="reviewer", system_prompt="review", tools=[])
        notification = await completed(manager)
        assert notification.status == "waiting_for_input"
        assert notification.message == "Which file?"
        assert manager.get(record.conversation_id).status == "waiting_for_input"
        await manager.send_message(record.conversation_id, "main.py")
        assert (await completed(manager)).status == "done"
        assert manager.get(record.conversation_id).output == "Answer: main.py"
    finally:
        await manager.close()


async def test_errors_and_cancellation_are_recorded_and_shutdown_joins_workers() -> None:
    async def runner(_agent: Any, _prompt: str) -> AsyncIterator[AgentEvent]:
        if _prompt == "error":
            raise ValueError("failed child")
        await asyncio.Event().wait()
        yield AgentEvent(EventType.CONTENT, "never")

    manager = manager_for(runner)
    failed = manager.spawn("error", role="role", system_prompt="system", tools=[])
    assert (await completed(manager)).status == "errored"
    assert "failed child" in (manager.get(failed.conversation_id).error or "")
    waiting = manager.spawn("wait", role="role", system_prompt="system", tools=[])
    cancelled = await manager.cancel(waiting.conversation_id)
    assert cancelled.status == "done"
    assert cancelled.cancelled
    last = manager.spawn("wait", role="role", system_prompt="system", tools=[])
    await manager.close()
    assert manager.get(last.conversation_id).cancelled
    assert not manager.has_running_work()
    with pytest.raises(RuntimeError, match="closed"):
        manager.spawn("late", role="role", system_prompt="system", tools=[])


async def test_explicit_error_events_do_not_report_success() -> None:
    async def runner(_agent: Any, _prompt: str) -> AsyncIterator[AgentEvent]:
        yield AgentEvent(EventType.ERROR, "provider unavailable")

    manager = manager_for(runner)
    try:
        record = manager.spawn("task", role="role", system_prompt="system", tools=[])
        assert (await completed(manager)).status == "errored"
        assert manager.get(record.conversation_id).error == "provider unavailable"
    finally:
        await manager.close()


async def test_tool_escalation_is_rejected_before_factory_runs() -> None:
    async def runner(_agent: Any, _prompt: str) -> AsyncIterator[AgentEvent]:
        yield AgentEvent(EventType.CONTENT, "done")

    manager = manager_for(runner)
    try:
        with pytest.raises(ValueError, match="outside"):
            manager.spawn("task", role="role", system_prompt="system", tools=["shell"])
        assert manager.list() == []
    finally:
        await manager.close()


async def test_children_can_message_parent_but_cannot_control_siblings() -> None:
    async def runner(_agent: Any, _prompt: str) -> AsyncIterator[AgentEvent]:
        await asyncio.Event().wait()
        yield AgentEvent(EventType.CONTENT, "never")

    manager = manager_for(runner)
    try:
        child = manager.spawn("task", role="role", system_prompt="system", tools=["send_message"])
        sibling = manager.spawn("task", role="role", system_prompt="system", tools=[])
        with subagent_actor(child.conversation_id):
            await manager.send_message("tech_lead", "Need assistance")
            assert manager.list() == []
            with pytest.raises(PermissionError):
                manager.get(sibling.conversation_id)
            with pytest.raises(PermissionError):
                await manager.cancel(sibling.conversation_id)
            with pytest.raises(PermissionError):
                await manager.send_message(sibling.conversation_id, "interfere")
            with pytest.raises(PermissionError):
                manager.spawn("nested", role="role", system_prompt="system", tools=[])
        notification = await completed(manager)
        assert notification.message == "Need assistance"
        assert notification.conversation_id == child.conversation_id
    finally:
        await manager.close()


async def test_nested_agents_inherit_only_delegated_tools_and_notify_their_parent() -> None:
    async def runner(_agent: Any, _prompt: str) -> AsyncIterator[AgentEvent]:
        yield AgentEvent(EventType.CONTENT, _prompt)

    manager = manager_for(runner)
    try:
        child = manager.spawn(
            "task",
            role="role",
            system_prompt="system",
            tools=["invoke_subagent", "read_file"],
        )
        with subagent_actor(child.conversation_id):
            with pytest.raises(ValueError, match="outside"):
                manager.spawn("nested", role="role", system_prompt="system", tools=["send_message"])
            nested = manager.spawn(
                "nested", role="role", system_prompt="system", tools=["read_file"]
            )
            assert manager.get(nested.conversation_id).parent_id == child.conversation_id
            notification = await asyncio.wait_for(manager.wait_for_notification(), 1)
            assert notification.conversation_id == nested.conversation_id
    finally:
        await manager.close()


async def test_output_and_retained_events_are_bounded() -> None:
    async def runner(_agent: Any, _prompt: str) -> AsyncIterator[AgentEvent]:
        for _ in range(100):
            yield AgentEvent(EventType.CONTENT, "x" * 1000)

    manager = manager_for(runner, max_output_chars=80)
    try:
        record = manager.spawn("task", role="role", system_prompt="system", tools=[])
        await completed(manager)
        record = manager.get(record.conversation_id)
        assert len(record.output) <= 80
        assert record.output_truncated
        assert len(record.events) <= 32
        assert all(len(str(event.data)) <= 80 for event in record.events)
        assert len(manager.drain_notifications()) == 0
    finally:
        await manager.close()


async def test_cancel_joins_descendants_and_reset_stays_reusable() -> None:
    async def runner(_agent: Any, _prompt: str) -> AsyncIterator[AgentEvent]:
        await asyncio.Event().wait()
        yield AgentEvent(EventType.CONTENT, "never")

    manager = manager_for(runner)
    try:
        child = manager.spawn(
            "task",
            role="role",
            system_prompt="system",
            tools=["invoke_subagent"],
        )
        with subagent_actor(child.conversation_id):
            nested = manager.spawn("nested", role="role", system_prompt="system", tools=[])
            with pytest.raises(PermissionError):
                await manager.close()
        await manager.cancel(child.conversation_id)
        assert manager.get(nested.conversation_id).cancelled
        assert not manager.has_running_work()
        manager.clear_notifications()
        assert not manager.drain_notifications()
        replacement = manager.spawn("new", role="role", system_prompt="system", tools=[])
        await manager.cancel_all()
        assert manager.get(replacement.conversation_id).cancelled
    finally:
        await manager.close()


async def test_nested_spawn_rechecks_live_tool_availability() -> None:
    async def runner(_agent: Any, _prompt: str) -> AsyncIterator[AgentEvent]:
        yield AgentEvent(EventType.CONTENT, "done")

    scope = ["invoke_subagent", "read_file"]
    manager = BackgroundSubagentManager(
        factory=lambda *args: args,
        runner=runner,
        available_tools=lambda _actor: scope,
    )
    try:
        child = manager.spawn("task", role="role", system_prompt="system", tools=scope.copy())
        scope.remove("read_file")
        with subagent_actor(child.conversation_id), pytest.raises(ValueError, match="outside"):
            manager.spawn("nested", role="role", system_prompt="system", tools=["read_file"])
    finally:
        await manager.close()


async def test_failed_run_discards_queued_work_before_explicit_recovery() -> None:
    release = asyncio.Event()
    seen: list[str] = []

    async def runner(_agent: Any, prompt: str) -> AsyncIterator[AgentEvent]:
        seen.append(prompt)
        if prompt == "fail":
            await release.wait()
            raise ValueError("failed")
        yield AgentEvent(EventType.CONTENT, prompt)

    manager = manager_for(runner)
    try:
        child = manager.spawn("fail", role="role", system_prompt="system", tools=[])
        await manager.send_message(child.conversation_id, "stale queued request")
        release.set()
        assert (await completed(manager)).status == "errored"
        await manager.send_message(child.conversation_id, "recover")
        assert (await completed(manager)).status == "done"
        assert seen == ["fail", "recover"]
    finally:
        await manager.close()


async def test_cancelling_worker_cannot_spawn_orphan_from_its_cleanup() -> None:
    started = asyncio.Event()
    rejected = False

    async def runner(_agent: Any, _prompt: str) -> AsyncIterator[AgentEvent]:
        nonlocal rejected
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            try:
                manager.spawn("orphan", role="role", system_prompt="system", tools=[])
            except RuntimeError:
                rejected = True
        yield AgentEvent(EventType.CONTENT, "never")

    manager = manager_for(runner)
    try:
        child = manager.spawn(
            "task", role="role", system_prompt="system", tools=["invoke_subagent"]
        )
        await asyncio.wait_for(started.wait(), 1)
        await manager.cancel(child.conversation_id)
        assert rejected
        assert len(manager.list()) == 1
        assert not manager.has_running_work()
    finally:
        await manager.close()
