"""Background accounting failures stop the whole run without becoming task data."""

import asyncio
from collections.abc import AsyncIterator

import pytest
from tests.agents.test_agent_budget_scope import AccountingProvider
from tests.agents.test_background_subagents import manager_for

from henchman.agents.orchestrator import Orchestrator
from henchman.core.events import AgentEvent, EventType
from henchman.core.run_budget import BudgetAccountingError, BudgetControlError, BudgetExceeded
from henchman.providers.base import FinishReason, StreamChunk, ToolCall
from henchman.providers.runtime_budget import (
    budget_attempt,
    current_run_budget,
    prepare_budget_operation,
)


@pytest.mark.parametrize("error", [BudgetAccountingError("invalid usage"), BudgetExceeded("token_limit")])
@pytest.mark.parametrize("notification_path", ["waiting", "draining", "cleared"])
async def test_control_failure_survives_notification_paths(error, notification_path):
    release = asyncio.Event()

    async def runner(_agent, _prompt) -> AsyncIterator[AgentEvent]:
        yield AgentEvent(EventType.CONTENT, "partial child evidence")
        await release.wait()
        raise error

    manager = manager_for(runner)
    record = manager.spawn("task", role="reviewer", system_prompt="child", tools=[])
    try:
        if notification_path == "waiting":
            waiting = asyncio.create_task(manager.wait_for_notification())
            await asyncio.sleep(0)
            release.set()
            with pytest.raises(BudgetControlError) as raised:
                await asyncio.wait_for(waiting, 1)
        else:
            release.set()
            await asyncio.sleep(0)
            if notification_path == "cleared":
                manager.clear_notifications()
            with pytest.raises(BudgetControlError) as raised:
                manager.drain_notifications()
        assert raised.value is error
        if notification_path == "waiting":
            assert waiting.cancelling() == 0
        assert manager.get(record.conversation_id).output == "partial child evidence"
        assert manager.get(record.conversation_id).status == "errored"
        await manager.cancel_all()
        manager.clear_notifications()
        with pytest.raises(BudgetControlError) as again:
            manager.drain_notifications()
        assert again.value is error
    finally:
        await manager.close()


async def test_only_explicit_new_run_resets_failure_after_workers_join():
    error = BudgetExceeded("request_limit")
    sibling_closed = asyncio.Event()

    async def runner(_agent, prompt) -> AsyncIterator[AgentEvent]:
        if prompt == "fail":
            raise error
        if prompt == "wait":
            try:
                await asyncio.Event().wait()
            finally:
                sibling_closed.set()
        yield AgentEvent(EventType.CONTENT, "new run")

    manager = manager_for(runner)
    sibling = manager.spawn("wait", role="reviewer", system_prompt="child", tools=[])
    await asyncio.sleep(0)
    failed = manager.spawn("fail", role="reviewer", system_prompt="child", tools=[])
    try:
        with pytest.raises(BudgetControlError) as raised:
            await manager.wait_for_notification()
        assert raised.value is error
        with pytest.raises(BudgetControlError):
            manager.spawn("new", role="reviewer", system_prompt="child", tools=[])
        with pytest.raises(BudgetControlError):
            await manager.send_message(failed.conversation_id, "retry")
        await manager.prepare_for_run()
        assert sibling_closed.is_set()
        assert manager.get(sibling.conversation_id).cancelled
        assert manager.drain_notifications() == []
        manager.spawn("new", role="reviewer", system_prompt="child", tools=[])
        notification = await asyncio.wait_for(manager.wait_for_notification(), 1)
        assert notification.message == "new run"
    finally:
        await manager.close()


class BackgroundFailureProvider(AccountingProvider):
    """Instrumented local transport with a failed child and blocked parent."""

    def __init__(self, *, blocked_parent: bool):
        super().__init__()
        self.blocked_parent = blocked_parent
        self.error = BudgetAccountingError("child transport accounting invalid")
        self.parent_started = asyncio.Event()
        self.release_child = asyncio.Event()
        self.sibling_started = asyncio.Event()
        self.sibling_closed = asyncio.Event()
        self.parent_closed = asyncio.Event()

    async def chat_completion_stream(self, messages, tools=None, **kwargs):
        scope = current_run_budget()
        assert scope is not None
        system = messages[0].content or ""
        if system == "failing child":
            yield StreamChunk(content="partial child evidence")
            await self.sibling_started.wait()
            if self.blocked_parent:
                await self.parent_started.wait()
            else:
                await self.release_child.wait()
            raise self.error
        if system == "waiting sibling":
            self.sibling_started.set()
            try:
                await asyncio.Event().wait()
            finally:
                self.sibling_closed.set()
            return
        operation = prepare_budget_operation(self, {
            "model": self.default_model, "messages": [m.content for m in messages], **kwargs,
        })
        with budget_attempt(operation) as attempt:
            assert attempt is not None
            attempt.start()
            self.calls += 1
            if self.calls == 1:
                chunk = StreamChunk(tool_calls=[
                    ToolCall(f"spawn-{i}", "invoke_subagent", {
                        "task": "review", "role": "reviewer", "system_prompt": prompt, "tools": [],
                    }) for i, prompt in enumerate(("failing child", "waiting sibling"))
                ], finish_reason=FinishReason.TOOL_CALLS, usage={"total_tokens": 3})
                attempt.observe(chunk)
                yield chunk
            else:
                self.parent_started.set()
                if self.blocked_parent:
                    try:
                        await asyncio.Event().wait()
                    finally:
                        self.parent_closed.set()
                yield StreamChunk(content="should not finish", finish_reason=FinishReason.STOP)


@pytest.mark.parametrize("blocked_parent", [False, True])
async def test_child_control_failure_stops_parent_and_siblings(blocked_parent):
    provider = BackgroundFailureProvider(blocked_parent=blocked_parent)
    orchestrator = Orchestrator(provider)

    async def approve(_request):
        return True

    orchestrator.tool_registry.set_confirmation_handler(approve)
    events = []

    async def collect():
        async for event in orchestrator.run("Review"):
            events.append(event)
            if (not blocked_parent and event.type == EventType.TOOL_CALL_RESULT
                and event.data.get("tool_call_id") == "spawn-1"):
                provider.release_child.set()
                await asyncio.sleep(0)
                await asyncio.sleep(0)

    try:
        with pytest.raises(BudgetControlError) as raised:
            await asyncio.wait_for(collect(), 1)
        assert raised.value is provider.error
        assert provider.calls == (2 if blocked_parent else 1)
        assert provider.sibling_closed.is_set()
        if blocked_parent:
            assert provider.parent_closed.is_set()
            assert orchestrator.last_budget_scope.ledger.snapshot().unknown_dispatched_requests == 1
        assert current_run_budget() is None
        assert orchestrator._public_run_active is False
        assert orchestrator.last_completion_status.value == "failed"
        assert not any(event.type == EventType.AGENT_COMPLETED for event in events)
        failed = next(record for record in orchestrator.subagents.list()
                      if record.system_prompt == "failing child")
        assert failed.output == "partial child evidence"
        assert failed.status == "errored"
        assert not orchestrator.subagents.has_running_work()
    finally:
        await orchestrator.aclose()
