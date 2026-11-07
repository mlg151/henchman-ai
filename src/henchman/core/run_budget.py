"""Process-lifetime accounting shared by every provider attempt in one run.

Reserve before dispatch, claim the reservation with ``start``, then reconcile
cumulative observations. A request ID names one actual provider attempt; retries
need new IDs under the same operation ID. This module performs no network calls,
model routing, persistence, metric sampling, or cancellation of remote billing.
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from decimal import Decimal
from fractions import Fraction
from threading import RLock
from typing import TYPE_CHECKING, Literal, Protocol
from uuid import uuid4

from henchman.providers.usage import TokenPricing, UsageReport

if TYPE_CHECKING:
    from henchman.core.run_budget_state import LedgerState

StopReason = Literal[
    "request_limit", "token_limit", "time_limit", "money_limit", "unknown_price", "currency_mismatch",
]
RequestState = Literal["reserved", "started", "finished", "cancelled"]
CacheMode = Literal["none", "read", "write", "any"]


def _count(value: int, name: str, *, positive: bool = False) -> None:
    if type(value) is not int or value < int(positive):
        raise ValueError(f"{name} must be a {'positive' if positive else 'nonnegative'} integer")


def _money(value: Decimal, name: str) -> None:
    if not isinstance(value, Decimal) or not value.is_finite() or value < 0:
        raise ValueError(f"{name} must be a finite nonnegative Decimal")


def _currency(value: str) -> None:
    if not isinstance(value, str) or len(value) != 3 or not value.isascii() or not value.isalpha() or not value.isupper():
        raise ValueError("currency must be a three-letter uppercase code")


def _identifier(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be nonempty")


def _exact_decimal(value: Fraction) -> Decimal:
    """Convert finite base-ten arithmetic without consulting Decimal's context.

    All operands originate as finite decimals, integer token counts, and /1000.
    Their reduced denominators therefore contain only factors of two and five.
    Constructing a Decimal tuple preserves every digit even under low precision,
    rounding traps, or widely separated price exponents.
    """
    denominator = value.denominator
    twos = fives = 0
    while denominator % 2 == 0:
        denominator //= 2
        twos += 1
    while denominator % 5 == 0:
        denominator //= 5
        fives += 1
    if denominator != 1:
        raise ValueError("Money arithmetic must have a finite decimal expansion")
    scale = max(twos, fives)
    coefficient = abs(value.numerator) * 2 ** (scale - twos) * 5 ** (scale - fives)
    return Decimal((int(value.numerator < 0), Decimal(coefficient).as_tuple().digits, -scale))


def _money_total(values: Iterable[Decimal]) -> Decimal:
    return _exact_decimal(sum((Fraction(value) for value in values), Fraction(0)))


@dataclass(frozen=True)
class BudgetLimits:
    """Optional hard admission limits; zero remains an explicit limit."""

    max_requests: int | None = None
    max_tokens: int | None = None
    max_seconds: float | None = None
    max_cost: Decimal | None = None
    currency: str = "USD"

    def __post_init__(self) -> None:
        for name in ("max_requests", "max_tokens"):
            value = getattr(self, name)
            if value is not None:
                _count(value, name)
        if self.max_seconds is not None and (
            type(self.max_seconds) not in (int, float) or not math.isfinite(self.max_seconds) or self.max_seconds < 0
        ):
            raise ValueError("max_seconds must be finite and nonnegative")
        if self.max_cost is not None:
            _money(self.max_cost, "max_cost")
        _currency(self.currency)


@dataclass(frozen=True)
class RequestEstimate:
    """Estimated input and a caller-enforced output cap, with a price snapshot.

    ``cache_mode`` declares applicable cache pricing. The default assumes both
    reads and writes can occur. Strict money admission rejects any missing
    applicable rate and reserves the highest applicable input rate.
    """

    prompt_tokens: int
    max_output_tokens: int
    pricing: TokenPricing | None = None
    cache_mode: CacheMode = "any"

    def __post_init__(self) -> None:
        _count(self.prompt_tokens, "prompt_tokens")
        _count(self.max_output_tokens, "max_output_tokens", positive=True)
        if self.cache_mode not in ("none", "read", "write", "any"):
            raise ValueError("Invalid cache_mode")

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.max_output_tokens


@dataclass(frozen=True)
class ReportedCost:
    """Cumulative provider-reported billing in its explicit currency."""

    amount: Decimal
    currency: str

    def __post_init__(self) -> None:
        _money(self.amount, "reported cost")
        _currency(self.currency)


@dataclass(frozen=True)
class RequestRecord:
    """An immutable view that separates observed usage from conservative holds."""

    run_id: str
    request_id: str
    operation_id: str
    agent_id: str | None
    provider: str | None
    model: str | None
    estimate: RequestEstimate
    state: RequestState
    dispatched: bool
    usage: UsageReport
    settled_tokens: int | None
    held_tokens: int
    cost_currency: str | None
    held_cost: Decimal | None
    settled_estimated_cost: Decimal | None
    reported_costs: tuple[ReportedCost, ...]
    settled_reported_costs: tuple[ReportedCost, ...]
    accounted_cost: Decimal | None
    cost_uncertain: bool

    @property
    def accounted_tokens(self) -> int:
        return (self.settled_tokens or 0) + self.held_tokens


@dataclass(frozen=True)
class CurrencyTotals:
    """Money observations and holds; different currencies are never added."""

    currency: str
    held_cost: Decimal | None
    settled_estimated_cost: Decimal | None
    reported_cost: Decimal | None
    settled_reported_cost: Decimal | None
    unknown_cost_requests: int


@dataclass(frozen=True)
class BudgetSnapshot:
    """Run state, remaining admission capacity, and explicit accounting limits."""

    run_id: str
    limits: BudgetLimits
    records: tuple[RequestRecord, ...]
    consumed_requests: int
    reserved_requests: int
    settled_tokens: int
    held_tokens: int
    unknown_dispatched_requests: int
    unknown_cost_requests: int
    elapsed_seconds: float
    remaining_requests: int | None
    remaining_tokens: int | None
    remaining_seconds: float | None
    remaining_cost: Decimal | None
    money: tuple[CurrencyTotals, ...]
    stop_reason: StopReason | None
    accounting_lifetime: Literal["process", "durable"] = "process"
    accounting_error: str | None = None


class BudgetControlError(RuntimeError):
    """Accounting control failures must not trigger provider retries or fallbacks."""


class BudgetAccountingError(BudgetControlError):
    """Durable accounting is unavailable or cannot safely authorize continuation."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"Run accounting prevented dispatch: {reason}")


class BudgetExceeded(BudgetControlError):
    """Admission was denied before a new provider attempt could start."""

    def __init__(self, reason: StopReason) -> None:
        self.reason = reason
        super().__init__(f"Run budget prevented dispatch: {reason}")


class RunBudgetAccounting(Protocol):
    """Admission and reconciliation contract shared by memory and durable stores."""

    @property
    def run_id(self) -> str: ...

    @property
    def limits(self) -> BudgetLimits: ...

    def reserve(self, estimate: RequestEstimate, *, request_id: str | None = None,
                operation_id: str | None = None, agent_id: str | None = None,
                provider: str | None = None, model: str | None = None) -> RequestRecord: ...

    def start(self, request_id: str) -> bool: ...

    def reconcile(self, request_id: str, usage: UsageReport | None = None, *,
                  final: bool = False, reported_cost: ReportedCost | None = None) -> RequestRecord: ...

    def cancel(self, request_id: str) -> RequestRecord: ...

    def snapshot(self) -> BudgetSnapshot: ...


@dataclass
class _Entry:
    request_id: str
    operation_id: str
    agent_id: str | None
    provider: str | None
    model: str | None
    estimate: RequestEstimate
    state: RequestState = "reserved"
    dispatched: bool = False
    usage: UsageReport = field(default_factory=UsageReport)
    final_usage: bool = False
    billings: dict[str, Decimal] = field(default_factory=dict)
    final_billings: set[str] = field(default_factory=set)


def _reservation_cost(estimate: RequestEstimate) -> Decimal | None:
    pricing = estimate.pricing
    if pricing is None or pricing.output_per_1k is None:
        return None
    rates = [pricing.input_per_1k]
    if estimate.cache_mode in ("read", "any"):
        rates.append(pricing.cache_read_per_1k)
    if estimate.cache_mode in ("write", "any"):
        rates.append(pricing.cache_write_per_1k)
    if estimate.prompt_tokens and any(rate is None for rate in rates):
        return None
    input_rate = max(Decimal(str(rate)) for rate in rates if rate is not None) if estimate.prompt_tokens else Decimal(0)
    return _exact_decimal((
        estimate.prompt_tokens * Fraction(input_rate)
        + estimate.max_output_tokens * Fraction(str(pricing.output_per_1k))
    ) / 1000)


def _usage_cost(usage: UsageReport, pricing: TokenPricing | None) -> Decimal | None:
    if pricing is None or usage.source == "unknown" or usage.prompt_tokens is None or usage.completion_tokens is None:
        return None
    if usage.total_tokens != usage.prompt_tokens + usage.completion_tokens:
        return None
    return _observed_cost(usage, pricing)


def _observed_cost(usage: UsageReport, pricing: TokenPricing | None) -> Decimal | None:
    """Price known components only; this lower bound never settles missing usage."""
    if pricing is None:
        return None
    cached, created = usage.cached_tokens or 0, usage.cache_creation_tokens or 0
    parts = (
        (max(0, (usage.prompt_tokens or 0) - cached - created), pricing.input_per_1k),
        (usage.completion_tokens or 0, pricing.output_per_1k),
        (cached, pricing.cache_read_per_1k),
        (created, pricing.cache_write_per_1k),
    )
    if any(count and rate is None for count, rate in parts):
        return None
    return _exact_decimal(sum((Fraction(count) * Fraction(str(rate)) / 1000 for count, rate in parts if count), Fraction(0)))


def _observed_tokens(usage: UsageReport) -> int:
    return max(usage.total_tokens or 0, (usage.prompt_tokens or 0) + (usage.completion_tokens or 0))


def _merge_usage(previous: UsageReport, incoming: UsageReport | None) -> UsageReport:
    """Keep cumulative maxima and never relabel estimates as reported counts."""
    if incoming is None or incoming.source == "unknown":
        return previous
    if previous.source == "reported" and incoming.source != "reported":
        return previous
    if previous.source != incoming.source:
        return incoming
    counts = previous.to_counts()
    for name, count in incoming.to_counts().items():
        counts[name] = max(counts.get(name, 0), count)
    if "prompt_tokens" in counts and "completion_tokens" in counts:
        counts["total_tokens"] = max(counts.get("total_tokens", 0), counts["prompt_tokens"] + counts["completion_tokens"])
    return UsageReport(**counts, source=incoming.source)


def _record(run_id: str, entry: _Entry) -> RequestRecord:
    released = entry.state == "cancelled" and not entry.dispatched
    settled = _observed_tokens(entry.usage) if entry.final_usage else None
    held_tokens = 0 if released or settled is not None else max(entry.estimate.total_tokens, _observed_tokens(entry.usage))
    pricing = entry.estimate.pricing
    currency = pricing.currency if pricing is not None else next(iter(entry.billings)) if len(entry.billings) == 1 else None
    estimated = _usage_cost(entry.usage, pricing) if entry.final_usage else None
    reservation = _reservation_cost(entry.estimate)
    billing = entry.billings.get(currency) if currency is not None else None
    mismatched = any(key != currency for key in entry.billings)
    final_billing = billing if currency in entry.final_billings else None
    settled_cost = final_billing if final_billing is not None else estimated
    observed_cost = _observed_cost(entry.usage, pricing)
    overrun = (
        _observed_tokens(entry.usage) > entry.estimate.total_tokens
        or (entry.usage.prompt_tokens or 0) > entry.estimate.prompt_tokens
        or (entry.usage.completion_tokens or 0) > entry.estimate.max_output_tokens
    )
    unresolved_observation = final_billing is None and (
        (entry.usage.source != "unknown" and observed_cost is None)
        or (overrun and _usage_cost(entry.usage, pricing) is None)
    )
    held_cost: Decimal | None
    accounted_cost: Decimal | None
    if released:
        held_cost, accounted_cost = Decimal(0), Decimal(0)
    elif settled_cost is not None and not mismatched:
        held_cost = Decimal(0)
        accounted_cost = max(settled_cost, billing or Decimal(0))
    else:
        held_cost = max(reservation, observed_cost or Decimal(0), billing or Decimal(0)) if reservation is not None else None
        accounted_cost = held_cost
    uncertain = not released and (
        accounted_cost is None or (entry.final_usage and settled_cost is None)
        or mismatched or unresolved_observation
    )
    return RequestRecord(
        run_id, entry.request_id, entry.operation_id, entry.agent_id, entry.provider, entry.model,
        entry.estimate, entry.state, entry.dispatched, entry.usage, settled, held_tokens,
        currency, held_cost, estimated,
        tuple(ReportedCost(amount, key) for key, amount in sorted(entry.billings.items())),
        tuple(ReportedCost(entry.billings[key], key) for key in sorted(entry.final_billings)),
        accounted_cost, uncertain,
    )


@dataclass
class _CurrencyAccumulator:
    held: Decimal | None = Decimal(0)
    estimated: Decimal | None = None
    reported: Decimal | None = None
    settled_reported: Decimal | None = None
    unknown: int = 0


def _currency_totals(records: tuple[RequestRecord, ...]) -> tuple[CurrencyTotals, ...]:
    totals: dict[str, _CurrencyAccumulator] = {}
    for record in records:
        if record.state == "cancelled" and not record.dispatched:
            continue
        currencies = {billing.currency for billing in record.reported_costs}
        if record.cost_currency is not None:
            currencies.add(record.cost_currency)
            row = totals.setdefault(record.cost_currency, _CurrencyAccumulator())
            row.held = _money_total((row.held, record.held_cost)) if row.held is not None and record.held_cost is not None else None
            if record.settled_estimated_cost is not None:
                row.estimated = _money_total((row.estimated or Decimal(0), record.settled_estimated_cost))
        for billing in record.reported_costs:
            row = totals.setdefault(billing.currency, _CurrencyAccumulator())
            row.reported = _money_total((row.reported or Decimal(0), billing.amount))
            if billing.currency != record.cost_currency and record.cost_uncertain:
                row.held = None
        for billing in record.settled_reported_costs:
            row = totals[billing.currency]
            row.settled_reported = _money_total((row.settled_reported or Decimal(0), billing.amount))
        for currency in currencies:
            totals[currency].unknown += record.cost_uncertain
    return tuple(
        CurrencyTotals(key, row.held, row.estimated, row.reported, row.settled_reported, row.unknown)
        for key, row in sorted(totals.items())
    )


class RunBudgetLedger:
    """Atomic, unsampled request accounting shared across threads and async tasks."""

    def __init__(
        self, *, run_id: str | None = None, limits: BudgetLimits | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._run_id = run_id if run_id is not None else uuid4().hex
        _identifier(self.run_id, "run_id")
        self._limits = limits if limits is not None else BudgetLimits()
        self._clock = clock
        self._started_at = clock()
        if not math.isfinite(self._started_at):
            raise ValueError("clock must return finite monotonic time")
        self._elapsed_seconds = 0.0
        self._lock = RLock()
        self._entries: dict[str, _Entry] = {}
        self._last_stop: StopReason | None = None

    @property
    def run_id(self) -> str:
        return self._run_id

    @property
    def limits(self) -> BudgetLimits:
        return self._limits

    @property
    def monotonic_origin(self) -> float:
        """Read this ledger's clock origin without rebasing it during persistence."""
        return self._started_at

    def export_state(self) -> LedgerState:
        """Capture source observations and finality without copying locks or clocks."""
        from henchman.core.run_budget_state import AttemptState, LedgerState

        with self._lock:
            attempts = tuple(AttemptState(
                e.request_id, e.operation_id, e.agent_id, e.provider, e.model, e.estimate,
                e.state, e.dispatched, e.usage, e.final_usage,
                tuple(ReportedCost(amount, currency) for currency, amount in sorted(e.billings.items())),
                tuple(sorted(e.final_billings)),
            ) for e in self._entries.values())
            return LedgerState(self.run_id, self.limits, attempts, self._elapsed(), self._last_stop)

    @classmethod
    def from_state(cls, state: LedgerState, *, clock: Callable[[], float] = time.monotonic) -> RunBudgetLedger:
        """Restore validated source state, retaining elapsed time and uncertainty."""
        from henchman.core.run_budget_state import LedgerState

        if not isinstance(state, LedgerState):
            raise ValueError("Expected validated LedgerState")
        ledger = cls(run_id=state.run_id, limits=state.limits, clock=clock)
        ledger._started_at -= state.elapsed_seconds
        ledger._elapsed_seconds = state.elapsed_seconds
        ledger._last_stop = state.last_stop
        ledger._entries = {e.request_id: _Entry(
            e.request_id, e.operation_id, e.agent_id, e.provider, e.model, e.estimate,
            e.state, e.dispatched, e.usage, e.final_usage,
            {b.currency: b.amount for b in e.billings}, set(e.final_billings),
        ) for e in state.attempts}
        return ledger

    def _elapsed(self) -> float:
        now = self._clock()
        if not math.isfinite(now):
            raise ValueError("clock must return finite monotonic time")
        self._elapsed_seconds = max(self._elapsed_seconds, now - self._started_at)
        return self._elapsed_seconds

    def _money_problem(self, records: tuple[RequestRecord, ...]) -> StopReason | None:
        if self.limits.max_cost is None:
            return None
        for record in records:
            if record.state == "cancelled" and not record.dispatched:
                continue
            pricing = record.estimate.pricing
            if (pricing is not None and pricing.currency != self.limits.currency) or any(b.currency != self.limits.currency for b in record.reported_costs):
                return "currency_mismatch"
            if record.cost_uncertain:
                return "unknown_price"
        return None

    def _check(self, records: tuple[RequestRecord, ...]) -> None:
        limits = self.limits
        reason: StopReason | None = None
        if limits.max_seconds is not None and self._elapsed() >= limits.max_seconds:
            reason = "time_limit"
        elif limits.max_requests is not None and sum(r.dispatched or r.state == "reserved" for r in records) > limits.max_requests:
            reason = "request_limit"
        elif limits.max_tokens is not None and sum(r.accounted_tokens for r in records) > limits.max_tokens:
            reason = "token_limit"
        else:
            reason = self._money_problem(records)
            if reason is None and limits.max_cost is not None:
                amount = _money_total(r.accounted_cost or Decimal(0) for r in records)
                if amount > limits.max_cost:
                    reason = "money_limit"
        if reason is not None:
            self._last_stop = reason
            raise BudgetExceeded(reason)

    def reserve(
        self, estimate: RequestEstimate, *, request_id: str | None = None,
        operation_id: str | None = None, agent_id: str | None = None,
        provider: str | None = None, model: str | None = None,
    ) -> RequestRecord:
        """Atomically reserve capacity; repeated identical IDs do not reserve twice."""
        request_id = request_id if request_id is not None else uuid4().hex
        operation_id = operation_id if operation_id is not None else request_id
        for name, value in (("request_id", request_id), ("operation_id", operation_id), ("agent_id", agent_id), ("provider", provider), ("model", model)):
            if value is not None:
                _identifier(value, name)
        with self._lock:
            existing = self._entries.get(request_id)
            if existing is not None:
                if (existing.estimate, existing.operation_id, existing.agent_id, existing.provider, existing.model) != (estimate, operation_id, agent_id, provider, model):
                    raise ValueError("Request ID already exists with different reservation metadata")
                return _record(self.run_id, existing)
            entry = _Entry(request_id, operation_id, agent_id, provider, model, estimate)
            records = tuple(_record(self.run_id, e) for e in (*self._entries.values(), entry))
            self._check(records)
            self._entries[request_id] = entry
            self._last_stop = None
            return records[-1]

    def start(self, request_id: str) -> bool:
        """Claim exactly one dispatch; expired or overdrawn reservations are released."""
        with self._lock:
            entry = self._entries[request_id]
            if entry.state != "reserved":
                return False
            try:
                self._check(tuple(_record(self.run_id, e) for e in self._entries.values()))
            except BudgetExceeded:
                entry.state = "cancelled"
                raise
            entry.state, entry.dispatched = "started", True
            self._last_stop = None
            return True

    def reconcile(
        self, request_id: str, usage: UsageReport | None = None, *, final: bool = False,
        reported_cost: ReportedCost | None = None,
    ) -> RequestRecord:
        """Reconcile cumulative snapshots, retaining unknown final consumption.

        ``final=True`` settles tokens only when this observation contains reported
        total usage. A terminal event without usage cannot promote an earlier
        partial snapshot into a final total. Late final reports can settle a
        cancelled dispatch; lower/duplicate cumulative observations never refund it.
        """
        with self._lock:
            entry = self._entries[request_id]
            if not entry.dispatched:
                raise ValueError("Cannot reconcile a request that was not dispatched")
            merged = _merge_usage(entry.usage, usage)
            entry.usage = merged
            if final:
                if entry.state != "cancelled":
                    entry.state = "finished"
                if usage is not None and usage.source == "reported" and usage.total_tokens is not None:
                    entry.final_usage = True
            if reported_cost is not None:
                previous = entry.billings.get(reported_cost.currency, Decimal(0))
                entry.billings[reported_cost.currency] = max(previous, reported_cost.amount)
                if final:
                    entry.final_billings.add(reported_cost.currency)
            self._last_stop = None
            return _record(self.run_id, entry)

    def cancel(self, request_id: str) -> RequestRecord:
        """Release an undispatched reservation; retain uncertain dispatched usage."""
        with self._lock:
            entry = self._entries[request_id]
            if entry.state != "finished":
                entry.state = "cancelled"
            self._last_stop = None
            return _record(self.run_id, entry)

    def snapshot(self) -> BudgetSnapshot:
        """Return a detached state view without inventing missing usage or currency."""
        with self._lock:
            records = tuple(_record(self.run_id, e) for e in self._entries.values())
            consumed = sum(r.dispatched for r in records)
            reserved = sum(r.state == "reserved" for r in records)
            settled = sum(r.settled_tokens or 0 for r in records)
            held = sum(r.held_tokens for r in records)
            money = _currency_totals(records)
            problem = self._money_problem(records)
            elapsed = self._elapsed()
            limits = self.limits
            remaining_cost = None
            if limits.max_cost is not None and problem is None and self._last_stop not in ("unknown_price", "currency_mismatch"):
                accounted = _money_total(r.accounted_cost or Decimal(0) for r in records)
                remaining_cost = max(Decimal(0), _exact_decimal(Fraction(limits.max_cost) - Fraction(accounted)))
            reason = problem or self._last_stop
            if limits.max_seconds is not None and elapsed >= limits.max_seconds:
                reason = "time_limit"
            elif limits.max_requests is not None and consumed + reserved > limits.max_requests:
                reason = "request_limit"
            elif limits.max_tokens is not None and settled + held > limits.max_tokens:
                reason = "token_limit"
            elif problem is None and limits.max_cost is not None and _money_total(r.accounted_cost or Decimal(0) for r in records) > limits.max_cost:
                reason = "money_limit"
            return BudgetSnapshot(
                self.run_id, limits, records, consumed, reserved, settled, held,
                sum(r.dispatched and r.settled_tokens is None for r in records),
                sum(r.cost_uncertain for r in records), elapsed,
                max(0, limits.max_requests - consumed - reserved) if limits.max_requests is not None else None,
                max(0, limits.max_tokens - settled - held) if limits.max_tokens is not None else None,
                max(0.0, limits.max_seconds - elapsed) if limits.max_seconds is not None else None,
                remaining_cost, money, reason,
            )
