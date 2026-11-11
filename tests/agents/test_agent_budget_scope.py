"""Agent continuations retain accounting without leaking scope to consumers."""

import asyncio
from collections.abc import AsyncIterator

import pytest

from henchman.agents.identity import AgentIdentity
from henchman.core.agent import Agent
from henchman.core.run_budget import BudgetExceeded, BudgetLimits, RunBudgetLedger
from henchman.providers.base import FinishReason, Message, ModelProvider, StreamChunk
from henchman.providers.runtime_budget import (
    RunBudgetScope,
    budget_attempt,
    current_run_budget,
    prepare_budget_operation,
    use_run_budget,
)
from henchman.utils.compaction import MessageSummarizer


class AccountingProvider(ModelProvider):
    """Offline instrumented transport with observable dispatch and cleanup."""

    supports_run_budget = True
    name = "test"
    default_model = "test-model"

    def __init__(self):
        self.calls = 0
        self.scopes = []
        self.closed_scopes = []

    async def chat_completion_stream(self, messages, tools=None, **kwargs) -> AsyncIterator[StreamChunk]:
        params = {"model": self.default_model, "messages": [m.content for m in messages], **kwargs}
        operation = prepare_budget_operation(self, params)
        self.scopes.append(current_run_budget())
        with budget_attempt(operation) as attempt:
            if attempt is not None:
                attempt.start()
            self.calls += 1
            try:
                yield StreamChunk(content="partial")
                chunk = StreamChunk(finish_reason=FinishReason.STOP, usage={"total_tokens": 3})
                if attempt is not None:
                    attempt.observe(chunk)
                yield chunk
            finally:
                self.closed_scopes.append(current_run_budget())


def make_agent(provider):
    return Agent(provider, identity=AgentIdentity("worker-7", "Worker", "coder", "Test"))


async def test_agent_scope_covers_preparation_and_restores_consumer(monkeypatch):
    provider = AccountingProvider()
    agent = make_agent(provider)
    parent = RunBudgetScope(RunBudgetLedger(), agent_id="parent")
    preparation_scopes = []
    original = agent._prepare_stream_context

    async def prepare():
        preparation_scopes.append(current_run_budget())
        return await original()

    monkeypatch.setattr(agent, "_prepare_stream_context", prepare)
    with use_run_budget(parent):
        async for _ in agent.run("go"):
            assert current_run_budget() is parent
    assert current_run_budget() is None
    assert preparation_scopes[0].agent_id == "worker-7"
    assert provider.scopes[0].agent_id == "worker-7"
    assert parent.ledger.snapshot().records[0].agent_id == "worker-7"


async def test_continuation_outside_original_scope_cannot_refund_budget():
    provider = AccountingProvider()
    agent = make_agent(provider)
    scope = RunBudgetScope(RunBudgetLedger(limits=BudgetLimits(max_requests=1)))
    with use_run_budget(scope):
        _ = [event async for event in agent.run("go")]
    with pytest.raises(BudgetExceeded, match="request_limit"):
        _ = [event async for event in agent.continue_with_tool_results()]
    assert provider.calls == 1
    assert current_run_budget() is None


async def test_continuation_rejects_switching_to_a_fresh_ledger():
    provider = AccountingProvider()
    agent = make_agent(provider)
    with use_run_budget(RunBudgetScope(RunBudgetLedger())):
        _ = [event async for event in agent.run("go")]
    with use_run_budget(RunBudgetScope(RunBudgetLedger())), pytest.raises(RuntimeError, match="different run"):
        _ = [event async for event in agent.continue_with_tool_results()]
    assert provider.calls == 1


async def test_generator_closed_in_another_task_restores_scope_and_keeps_hold():
    provider = AccountingProvider()
    agent = make_agent(provider)
    original = RunBudgetScope(RunBudgetLedger(), agent_id="parent")
    unrelated = RunBudgetScope(RunBudgetLedger(), agent_id="other")
    with use_run_budget(original):
        stream = agent.run("go")
        await anext(stream)
        assert current_run_budget() is original

    async def close():
        with use_run_budget(unrelated):
            await stream.aclose()
            assert current_run_budget() is unrelated

    await asyncio.create_task(close())
    assert provider.closed_scopes[0].ledger is original.ledger
    assert provider.closed_scopes[0].agent_id == "worker-7"
    assert original.ledger.snapshot().unknown_dispatched_requests == 1
    assert not unrelated.ledger.snapshot().records


@pytest.mark.parametrize("summary", [False, True])
async def test_unsupported_provider_is_rejected_before_any_dispatch(summary):
    provider = AccountingProvider()
    provider.supports_run_budget = False
    with use_run_budget(RunBudgetScope(RunBudgetLedger())), pytest.raises(RuntimeError, match="accounting"):
        if summary:
            await MessageSummarizer(provider).summarize([Message("user", "old context")])
        else:
            _ = [event async for event in make_agent(provider).run("go")]
    assert provider.calls == 0


async def test_new_unscoped_turn_does_not_reuse_an_old_turn_budget():
    provider = AccountingProvider()
    agent = make_agent(provider)
    with use_run_budget(RunBudgetScope(RunBudgetLedger(limits=BudgetLimits(max_requests=1)))):
        _ = [event async for event in agent.run("first")]
    _ = [event async for event in agent.run("second")]
    assert provider.calls == 2
    assert provider.scopes[-1] is None
