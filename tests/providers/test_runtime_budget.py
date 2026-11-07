"""Actual SDK transports share explicit run budgets without network requests."""

import asyncio
import json
from collections.abc import AsyncIterator
from decimal import Decimal
from importlib import import_module
from types import ModuleType
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from anthropic import AsyncAnthropic
from openai import AsyncOpenAI, RateLimitError

from henchman.core.run_budget import BudgetExceeded, BudgetLimits, RunBudgetLedger
from henchman.providers.anthropic import AnthropicProvider
from henchman.providers.base import Message, ToolDeclaration
from henchman.providers.openai_compat import OpenAICompatibleProvider
from henchman.providers.runtime_budget import RunBudgetScope, current_run_budget, use_run_budget
from henchman.providers.usage import TokenPricing


def compatible_body(*, usage: bool = True) -> bytes:
    chunks = [{
        "id": "completion-1", "object": "chat.completion.chunk", "created": 1,
        "model": "test-model", "choices": [{"index": 0, "delta": {"content": "Done"}, "finish_reason": "stop"}],
    }]
    if usage:
        chunks.append({
            "id": "completion-1", "object": "chat.completion.chunk", "created": 1,
            "model": "test-model", "choices": [],
            "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12},
        })
    return ("".join(f"data: {json.dumps(chunk)}\n\n" for chunk in chunks) + "data: [DONE]\n\n").encode()


def native_body(*, usage: bool = True) -> bytes:
    events: list[dict[str, Any]] = [{
        "type": "message_start", "message": {
            "id": "message-1", "type": "message", "role": "assistant", "model": "test-model",
            "content": [], "stop_reason": None, "stop_sequence": None,
            "usage": {"input_tokens": 10, "output_tokens": 0},
        },
    }, {
        "type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""},
    }, {
        "type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "Done"},
    }, {
        "type": "content_block_stop", "index": 0,
    }, {
        "type": "message_delta", "delta": {"stop_reason": "end_turn", "stop_sequence": None},
        "usage": {"output_tokens": 2} if usage else None,
    }, {"type": "message_stop"}]
    if not usage:
        events = [event for event in events if event["type"] != "message_delta"]
    return "".join(f"event: {event['type']}\ndata: {json.dumps(event)}\n\n" for event in events).encode()


class Transport:
    def __init__(self, native: bool, http: ModuleType = httpx) -> None:
        self.native = native
        self.http = http
        self.requests: list[dict[str, Any]] = []
        self.statuses: list[int] = []
        self.usage = True
        self.wait = False
        self.started = asyncio.Event()

    async def __call__(self, request: Any) -> Any:
        self.requests.append(json.loads(request.content))
        self.started.set()
        if self.wait:
            await asyncio.Event().wait()
        status = self.statuses.pop(0) if self.statuses else 200
        if status != 200:
            return self.http.Response(status, json={"error": {"type": "rate_limit_error", "message": "retry"}})
        body = native_body(usage=self.usage) if self.native else compatible_body(usage=self.usage)
        return self.http.Response(200, content=body, headers={"content-type": "text/event-stream"})


@pytest.fixture(params=["compatible", "anthropic"])
async def sdk_transport(request: pytest.FixtureRequest) -> AsyncIterator[tuple[Any, Transport]]:
    native = request.param == "anthropic"
    provider = AnthropicProvider(api_key="test") if native else OpenAICompatibleProvider("test", "https://test.invalid", "test-model")
    # Fresh wheel installs may use Anthropic's httpx2 SDK while the lock uses
    # httpx. Match the client's actual transport types without pinning the SDK.
    http_module = next(
        cls.__module__.partition(".")[0] for cls in type(provider._client._client).__mro__
        if cls.__module__.partition(".")[0] in {"httpx", "httpx2"}
    )
    http = import_module(http_module)
    await provider._client.close()
    transport = Transport(native, http)
    http_client = http.AsyncClient(transport=http.MockTransport(transport))
    factory = AsyncAnthropic if native else AsyncOpenAI
    provider._client = factory(api_key="test", base_url="https://test.invalid", http_client=http_client)
    if native:
        provider._rate_limiter.wait_for_capacity = AsyncMock()
    try:
        yield provider, transport
    finally:
        await provider._client.close()


async def consume(provider: Any, **kwargs: Any) -> list[Any]:
    return [chunk async for chunk in provider.chat_completion_stream([Message("user", "Go")], **kwargs)]


async def test_attempts_settle_cumulative_usage_and_enforce_exact_wire_cap(sdk_transport) -> None:
    provider, transport = sdk_transport
    ledger = RunBudgetLedger(limits=BudgetLimits(max_requests=1))
    with use_run_budget(RunBudgetScope(ledger, agent_id="worker")):
        await consume(provider, max_tokens=7)
        with pytest.raises(BudgetExceeded, match="request_limit"):
            await consume(provider, max_tokens=7)
    snapshot = ledger.snapshot()
    assert len(transport.requests) == 1
    assert transport.requests[0]["max_tokens"] == snapshot.records[0].estimate.max_output_tokens == 7
    assert snapshot.consumed_requests == 1 and snapshot.settled_tokens == 12
    assert snapshot.held_tokens == 0 and snapshot.unknown_dispatched_requests == 0
    assert snapshot.records[0].agent_id == "worker"
    assert provider._client.max_retries == 2  # The reusable client was not mutated.


def test_transport_adapters_declare_run_budget_support() -> None:
    assert OpenAICompatibleProvider.supports_run_budget is True
    assert AnthropicProvider.supports_run_budget is True


async def test_unknown_final_usage_does_not_promote_earlier_partial_usage(sdk_transport) -> None:
    provider, transport = sdk_transport
    transport.usage = False
    ledger = RunBudgetLedger()
    with use_run_budget(RunBudgetScope(ledger)):
        await consume(provider, max_tokens=7)
    snapshot = ledger.snapshot()
    assert snapshot.unknown_dispatched_requests == 1
    assert snapshot.settled_tokens == 0 and snapshot.held_tokens > 0


async def test_unknown_money_prevents_transport_and_zero_price_allows_it(sdk_transport) -> None:
    provider, transport = sdk_transport
    ledger = RunBudgetLedger(limits=BudgetLimits(max_cost=Decimal(0)))
    with use_run_budget(RunBudgetScope(ledger)), pytest.raises(BudgetExceeded, match="unknown_price"):
        await consume(provider)
    assert transport.requests == []
    seen = []

    def price(name: str, model: str) -> TokenPricing:
        seen.append((name, model))
        return TokenPricing.uniform(0)

    with use_run_budget(RunBudgetScope(ledger, pricing_resolver=price)):
        await consume(provider, model="explicit-model", max_tokens=7)
    assert seen == [(provider.name, "explicit-model")]
    assert ledger.snapshot().remaining_cost == 0


async def test_cancelled_transport_keeps_consumed_reservation(sdk_transport) -> None:
    provider, transport = sdk_transport
    transport.wait = True
    ledger = RunBudgetLedger(limits=BudgetLimits(max_requests=1))
    with use_run_budget(RunBudgetScope(ledger)):
        task = asyncio.create_task(consume(provider, max_tokens=7))
        await asyncio.wait_for(transport.started.wait(), 2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    snapshot = ledger.snapshot()
    assert snapshot.consumed_requests == 1 and snapshot.unknown_dispatched_requests == 1
    assert snapshot.records[0].state == "cancelled" and snapshot.held_tokens > 0


async def test_early_consumer_close_keeps_usage_unknown(sdk_transport) -> None:
    provider, _ = sdk_transport
    ledger = RunBudgetLedger()
    with use_run_budget(RunBudgetScope(ledger)):
        stream = provider.chat_completion_stream([Message("user", "Go")], max_tokens=7)
        await anext(stream)
        await stream.aclose()
    assert ledger.snapshot().unknown_dispatched_requests == 1
    assert ledger.snapshot().records[0].state == "cancelled"


async def test_child_task_retains_original_scope_and_nested_scope_restores(sdk_transport) -> None:
    provider, _ = sdk_transport
    first, second = RunBudgetLedger(), RunBudgetLedger()
    scope = RunBudgetScope(first, agent_id="original")
    gate = asyncio.Event()

    async def delayed() -> None:
        await gate.wait()
        assert current_run_budget() is scope
        await consume(provider, max_tokens=7)

    with use_run_budget(scope):
        task = asyncio.create_task(delayed())
    assert current_run_budget() is None
    with use_run_budget(RunBudgetScope(second)):
        gate.set()
        await task
    assert first.snapshot().consumed_requests == 1
    assert second.snapshot().records == ()


@pytest.mark.parametrize("sdk_transport", ["compatible"], indirect=True)
async def test_compatible_scope_disables_hidden_sdk_retries(sdk_transport) -> None:
    provider, transport = sdk_transport
    transport.statuses = [429, 200]
    ledger = RunBudgetLedger()
    with use_run_budget(RunBudgetScope(ledger)), pytest.raises(RateLimitError):
        await consume(provider)
    assert len(transport.requests) == ledger.snapshot().consumed_requests == 1


@pytest.mark.parametrize("sdk_transport", ["anthropic"], indirect=True)
async def test_native_retries_reserve_new_attempts_under_one_operation(sdk_transport) -> None:
    provider, transport = sdk_transport
    transport.statuses = [429, 200]
    ledger = RunBudgetLedger(limits=BudgetLimits(max_requests=2))
    with use_run_budget(RunBudgetScope(ledger)), patch("henchman.providers.anthropic.asyncio.sleep", new_callable=AsyncMock):
        await consume(provider, max_tokens=7)
    snapshot = ledger.snapshot()
    assert len(transport.requests) == snapshot.consumed_requests == 2
    assert len({record.request_id for record in snapshot.records}) == 2
    assert len({record.operation_id for record in snapshot.records}) == 1
    assert snapshot.unknown_dispatched_requests == 1 and snapshot.settled_tokens == 12


@pytest.mark.parametrize("sdk_transport", ["anthropic"], indirect=True)
async def test_native_retry_cannot_bypass_request_limit(sdk_transport) -> None:
    provider, transport = sdk_transport
    transport.statuses = [429, 200]
    ledger = RunBudgetLedger(limits=BudgetLimits(max_requests=1))
    with (
        use_run_budget(RunBudgetScope(ledger)),
        patch("henchman.providers.anthropic.asyncio.sleep", new_callable=AsyncMock),
        pytest.raises(BudgetExceeded, match="request_limit"),
    ):
        await consume(provider, max_tokens=7)
    assert len(transport.requests) == 1


@pytest.mark.parametrize("sdk_transport", ["compatible"], indirect=True)
async def test_compatible_fallback_cap_and_extra_body_cap_match_reservation(sdk_transport) -> None:
    provider, transport = sdk_transport
    ledger = RunBudgetLedger()
    with use_run_budget(RunBudgetScope(ledger, default_output_tokens=19)):
        await consume(provider)
        await consume(provider, extra_body={"max_completion_tokens": 11})
    assert transport.requests[0]["max_tokens"] == ledger.snapshot().records[0].estimate.max_output_tokens == 19
    assert transport.requests[1]["max_completion_tokens"] == ledger.snapshot().records[1].estimate.max_output_tokens == 11
    assert "max_tokens" not in transport.requests[1]


@pytest.mark.parametrize("cap", [None, 0, -1, True, "8"])
async def test_invalid_explicit_cap_never_dispatches(sdk_transport, cap: object) -> None:
    provider, transport = sdk_transport
    with use_run_budget(RunBudgetScope(RunBudgetLedger())), pytest.raises(ValueError, match="positive integer"):
        await consume(provider, max_tokens=cap)
    assert transport.requests == []


@pytest.mark.parametrize("sdk_transport", ["anthropic"], indirect=True)
async def test_native_cancellation_while_waiting_releases_undispatched_reservation(sdk_transport) -> None:
    provider, transport = sdk_transport
    waiting = asyncio.Event()

    async def wait(_tokens: int) -> None:
        waiting.set()
        await asyncio.Event().wait()

    provider._rate_limiter.wait_for_capacity = wait
    ledger = RunBudgetLedger(limits=BudgetLimits(max_requests=1))
    with use_run_budget(RunBudgetScope(ledger)):
        task = asyncio.create_task(consume(provider, max_tokens=7))
        await asyncio.wait_for(waiting.wait(), 2)
        assert ledger.snapshot().reserved_requests == 1
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert transport.requests == []
    assert ledger.snapshot().consumed_requests == 0
    assert ledger.snapshot().remaining_requests == 1 and ledger.snapshot().held_tokens == 0


@pytest.mark.parametrize("sdk_transport", ["anthropic"], indirect=True)
async def test_expired_scope_denies_before_rate_limit_wait(sdk_transport) -> None:
    provider, transport = sdk_transport
    ledger = RunBudgetLedger(limits=BudgetLimits(max_seconds=0))
    with use_run_budget(RunBudgetScope(ledger)), pytest.raises(BudgetExceeded, match="time_limit"):
        await consume(provider)
    provider._rate_limiter.wait_for_capacity.assert_not_called()
    assert transport.requests == []


async def test_summary_drains_usage_and_shares_the_run_request_limit(sdk_transport) -> None:
    from henchman.utils.compaction import MessageSummarizer

    provider, transport = sdk_transport
    ledger = RunBudgetLedger(limits=BudgetLimits(max_requests=1))
    with use_run_budget(RunBudgetScope(ledger, agent_id="summary-owner")):
        assert await MessageSummarizer(provider).summarize([Message("user", "Earlier task")]) == "Done"
        with pytest.raises(BudgetExceeded, match="request_limit"):
            await MessageSummarizer(provider).summarize([Message("user", "More history")])
    assert len(transport.requests) == 1 and ledger.snapshot().settled_tokens == 12
    assert ledger.snapshot().records[0].agent_id == "summary-owner"


async def test_configured_provider_identity_is_used_only_for_accounting(sdk_transport) -> None:
    provider, transport = sdk_transport
    provider._accounting_provider_name = "configured-backend"
    ledger = RunBudgetLedger(limits=BudgetLimits(max_cost=Decimal(0)))

    def price(name: str, model: str) -> TokenPricing | None:
        return TokenPricing.uniform(0) if (name, model) == ("configured-backend", "chosen-model") else None

    with use_run_budget(RunBudgetScope(ledger, pricing_resolver=price)):
        await consume(provider, model="chosen-model", max_tokens=7)
    assert ledger.snapshot().records[0].provider == "configured-backend"
    assert "_accounting_provider_name" not in transport.requests[0]


async def test_configured_decimal_prices_reach_the_ledger_losslessly(sdk_transport) -> None:
    provider, _ = sdk_transport
    rate = Decimal("0.12345678901234567890123456789")
    ledger = RunBudgetLedger(limits=BudgetLimits(max_cost=Decimal(1)))
    scope = RunBudgetScope(ledger, pricing_resolver=lambda _provider, _model: TokenPricing.uniform(rate))
    with use_run_budget(scope):
        await consume(provider, max_tokens=7)
    record = ledger.snapshot().records[0]
    assert record.estimate.pricing.input_per_1k is rate
    assert record.accounted_cost == Decimal("0.00148148146814814814681481481468")


async def test_concurrent_tasks_share_one_dispatch_budget(sdk_transport) -> None:
    provider, transport = sdk_transport
    ledger = RunBudgetLedger(limits=BudgetLimits(max_requests=1))
    with use_run_budget(RunBudgetScope(ledger)):
        results = await asyncio.gather(consume(provider, max_tokens=7), consume(provider, max_tokens=7), return_exceptions=True)
    assert len(transport.requests) == 1
    assert sum(isinstance(result, BudgetExceeded) for result in results) == 1
    assert ledger.snapshot().consumed_requests == 1


@pytest.mark.parametrize("sdk_transport", ["anthropic"], indirect=True)
async def test_reserved_wire_options_are_detached_before_rate_limit_wait(sdk_transport) -> None:
    provider, transport = sdk_transport
    entered, release = asyncio.Event(), asyncio.Event()

    async def wait(_tokens: int) -> None:
        entered.set()
        await release.wait()

    provider._rate_limiter.wait_for_capacity = wait
    extra = {"max_tokens": 7, "model": "priced-model"}
    schema = {"type": "object", "properties": {"path": {"enum": ["original"]}}}
    tools = [ToolDeclaration("inspect", "Inspect path", schema)]
    ledger = RunBudgetLedger()
    with use_run_budget(RunBudgetScope(ledger)):
        task = asyncio.create_task(consume(provider, extra_body=extra, tools=tools))
        await asyncio.wait_for(entered.wait(), 2)
        extra.update(max_tokens=7000, model="changed-model")
        schema["properties"]["path"]["enum"].append("changed")
        release.set()
        await task
    record = ledger.snapshot().records[0]
    assert transport.requests[0]["max_tokens"] == record.estimate.max_output_tokens == 7
    assert transport.requests[0]["model"] == record.model == "priced-model"
    assert transport.requests[0]["tools"][0]["input_schema"]["properties"]["path"]["enum"] == ["original"]


@pytest.mark.parametrize("sdk_transport", ["anthropic"], indirect=True)
async def test_retries_reuse_detached_wire_options(sdk_transport) -> None:
    provider, transport = sdk_transport
    transport.statuses = [429, 200]
    extra = {"max_tokens": 7, "model": "priced-model"}

    async def backoff(_seconds: float) -> None:
        extra.update(max_tokens=7000, model="changed-model")

    ledger = RunBudgetLedger()
    with use_run_budget(RunBudgetScope(ledger)), patch("henchman.providers.anthropic.asyncio.sleep", side_effect=backoff):
        await consume(provider, extra_body=extra)
    assert [request["max_tokens"] for request in transport.requests] == [7, 7]
    assert [request["model"] for request in transport.requests] == ["priced-model", "priced-model"]
