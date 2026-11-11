"""Explicit, task-local accounting for supported provider transport attempts.

Use ``use_run_budget(RunBudgetScope(ledger, ...))`` around stream consumption.
Child tasks inherit their creating scope; capture ``current_run_budget()`` to
rebind later work explicitly. Providers capture one scope per logical operation,
so changing a caller's scope cannot move an in-flight attempt to another run.

An active scope disables hidden SDK retries. Compatible requests make one
attempt; Anthropic's existing explicit retries reserve independently. Without a
scope, provider behavior is unchanged; this module creates no implicit ledger.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from henchman.providers.request_budget import estimate_serialized_input, validate_output_tokens
from henchman.providers.usage import TokenPricing, UsageReport

if TYPE_CHECKING:
    from henchman.core.run_budget import CacheMode, RequestEstimate, RunBudgetAccounting
    from henchman.providers.base import ModelProvider, StreamChunk

PricingResolver = Callable[[str, str], TokenPricing | None]


@dataclass(frozen=True)
class RunBudgetScope:
    """Capture one ledger, actor and explicit provider/model price resolver.

    ``default_output_tokens`` only supplies a missing output limit. Explicit
    request limits, including incompatible or invalid ones, are never replaced.
    No price resolver means unknown pricing, even for a local provider.
    """

    ledger: RunBudgetAccounting
    agent_id: str | None = None
    pricing_resolver: PricingResolver | None = None
    default_output_tokens: int = 4096
    cache_mode: CacheMode = "any"

    def __post_init__(self) -> None:
        validate_output_tokens(self.default_output_tokens)
        if self.agent_id is not None and (not isinstance(self.agent_id, str) or not self.agent_id.strip()):
            raise ValueError("agent_id must be nonempty")
        if self.cache_mode not in ("none", "read", "write", "any"):
            raise ValueError("Invalid cache_mode")

    def for_agent(self, agent_id: str | None) -> RunBudgetScope:
        """Retain the run and pricing policy while attributing another actor."""
        return replace(self, agent_id=agent_id)


_scope: ContextVar[RunBudgetScope | None] = ContextVar("henchman_run_budget", default=None)


def current_run_budget() -> RunBudgetScope | None:
    """Capture the current scope for explicit later activation."""
    return _scope.get()


@contextmanager
def use_run_budget(scope: RunBudgetScope | None) -> Iterator[RunBudgetScope | None]:
    """Activate a captured scope (or its absence) and restore it on every exit."""
    token = _scope.set(scope)
    try:
        yield scope
    finally:
        _scope.reset(token)


@dataclass(frozen=True)
class BudgetOperation:
    """One request operation whose retries share identity and a price snapshot."""

    scope: RunBudgetScope
    operation_id: str
    provider: str
    model: str
    estimate: RequestEstimate


def prepare_budget_operation(
    provider: ModelProvider, params: dict[str, Any], *, output_fields: tuple[str, ...] = ("max_tokens",),
) -> BudgetOperation | None:
    """Capture accounting for effective wire options and enforce its output cap.

    Only known model-input fields enter the estimator; credentials, endpoints,
    headers, and arbitrary extension metadata are never tokenized or recorded.
    Input estimates retain the existing provider/template approximation limits.
    """
    scope = current_run_budget()
    if scope is None:
        return None
    # Detach the entire request graph before estimating or awaiting capacity.
    # Caller-owned schemas/options may change while this operation is in flight.
    detached = deepcopy(params)
    params.clear()
    params.update(detached)
    configured_name = getattr(provider, "_accounting_provider_name", None)
    name = configured_name if isinstance(configured_name, str) and configured_name.strip() else provider.name
    # Import lazily: providers are also imported while core.run_budget initializes.
    from henchman.core.run_budget import RequestEstimate

    extra = params.get("extra_body")
    if extra is None:
        extra = {}
    if not isinstance(extra, dict):
        raise ValueError("Budget accounting requires an object for extra_body")
    if {"messages", "tools", "system"}.intersection(extra):
        raise ValueError("Budget accounting cannot override input fields in extra_body")
    effective = {**params, **extra}
    if effective.get("stream", True) is not True or effective.get("n", 1) != 1:
        raise ValueError("Budget accounting requires one streamed completion")
    fields = [field for field in output_fields if field in effective]
    if len(fields) > 1:
        raise ValueError("Configure only one output token cap")
    field = fields[0] if fields else output_fields[0]
    cap = validate_output_tokens(effective[field] if fields else scope.default_output_tokens)
    if not fields:
        params[field] = cap
    model = effective.get("model")
    if not isinstance(model, str) or not model.strip():
        raise ValueError("Budget accounting requires an explicit model")
    payload = {
        key: effective[key] for key in (
            "messages", "system", "tools", "response_format", "tool_choice", "functions", "function_call",
        ) if key in effective
    }
    pricing = scope.pricing_resolver(name, model) if scope.pricing_resolver is not None else None
    estimate = RequestEstimate(
        estimate_serialized_input(payload, model=model), cap, pricing=pricing,
        cache_mode=scope.cache_mode,
    )
    return BudgetOperation(scope, uuid4().hex, name, model, estimate)


@dataclass
class BudgetAttempt:
    """Observe one actual SDK attempt without treating early usage as final."""

    operation: BudgetOperation
    request_id: str
    _started: bool = False
    _finished: bool = False
    _final_usage: UsageReport | None = None

    def start(self) -> None:
        """Recheck limits immediately before the transport can dispatch."""
        if not self.operation.scope.ledger.start(self.request_id):
            raise RuntimeError("Provider attempt was already claimed")
        self._started = True

    def observe(self, chunk: StreamChunk) -> None:
        if chunk.finish_reason is not None:
            self._finished = True
        if chunk.usage is not None:
            report = UsageReport(**chunk.usage, source=chunk.usage_source or "unknown")
            self.operation.scope.ledger.reconcile(self.request_id, report)
            if self._finished and report.source == "reported":
                self._final_usage = report

    def complete(self) -> None:
        self.operation.scope.ledger.reconcile(self.request_id, self._final_usage, final=True)


@contextmanager
def budget_attempt(operation: BudgetOperation | None) -> Iterator[BudgetAttempt | None]:
    """Claim one dispatch and retain uncertain consumption on any interruption."""
    if operation is None:
        yield None
        return
    ledger = operation.scope.ledger
    record = ledger.reserve(
        operation.estimate, operation_id=operation.operation_id,
        agent_id=operation.scope.agent_id, provider=operation.provider, model=operation.model,
    )
    attempt = BudgetAttempt(operation, record.request_id)
    try:
        yield attempt
    except BaseException:
        ledger.cancel(record.request_id)
        raise
    else:
        if not attempt._started:
            ledger.cancel(record.request_id)
            raise RuntimeError("Provider attempt ended without dispatch")
        attempt.complete()
