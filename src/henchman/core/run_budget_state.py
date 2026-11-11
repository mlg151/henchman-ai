"""Validated, versioned accounting state independent of storage or live locks."""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Any, cast

from henchman.core.run_budget import (
    BudgetLimits,
    ReportedCost,
    RequestEstimate,
    RequestState,
    StopReason,
    _identifier,
)
from henchman.providers.usage import TokenPricing, UsageReport

_STOPS = {"request_limit", "token_limit", "time_limit", "money_limit", "unknown_price", "currency_mismatch"}


@dataclass(frozen=True)
class AttemptState:
    """Original reservation and cumulative observations, including finality."""

    request_id: str
    operation_id: str
    agent_id: str | None
    provider: str | None
    model: str | None
    estimate: RequestEstimate
    state: RequestState
    dispatched: bool
    usage: UsageReport
    final_usage: bool
    billings: tuple[ReportedCost, ...]
    final_billings: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in ("request_id", "operation_id", "agent_id", "provider", "model"):
            value = getattr(self, name)
            if value is not None or name in ("request_id", "operation_id"):
                _identifier(value, name)
        if not isinstance(self.estimate, RequestEstimate) or not isinstance(self.usage, UsageReport):
            raise ValueError("Invalid accounting estimate or usage")
        if self.state not in ("reserved", "started", "finished", "cancelled"):
            raise ValueError("Invalid accounting attempt state")
        if type(self.dispatched) is not bool or type(self.final_usage) is not bool:
            raise ValueError("Accounting flags must be booleans")
        if self.state == "reserved" and self.dispatched:
            raise ValueError("Reserved attempt cannot already be dispatched")
        if self.state in ("started", "finished") and not self.dispatched:
            raise ValueError("Started attempt must be dispatched")
        if not self.dispatched and (self.usage != UsageReport() or self.final_usage or self.billings or self.final_billings):
            raise ValueError("Undispatched attempt cannot have observations")
        if self.final_usage and (self.usage.source != "reported" or self.usage.total_tokens is None):
            raise ValueError("Final usage needs reported total tokens")
        if (self.final_usage or self.final_billings) and self.state not in ("finished", "cancelled"):
            raise ValueError("Final observations need a terminal attempt")
        if not isinstance(self.billings, tuple) or not all(isinstance(b, ReportedCost) for b in self.billings):
            raise ValueError("Invalid accounting billing observations")
        currencies = {billing.currency for billing in self.billings}
        if len(currencies) != len(self.billings):
            raise ValueError("Duplicate billing currency")
        if not isinstance(self.final_billings, tuple) or len(set(self.final_billings)) != len(self.final_billings) or not set(self.final_billings) <= currencies:
            raise ValueError("Invalid final billing currencies")


@dataclass(frozen=True)
class LedgerState:
    """Complete reconstructible state; totals are recomputed from attempts."""

    run_id: str
    limits: BudgetLimits
    attempts: tuple[AttemptState, ...]
    elapsed_seconds: float
    last_stop: StopReason | None

    def __post_init__(self) -> None:
        _identifier(self.run_id, "run_id")
        if not isinstance(self.limits, BudgetLimits):
            raise ValueError("Invalid accounting limits")
        if type(self.elapsed_seconds) not in (int, float) or not math.isfinite(self.elapsed_seconds) or self.elapsed_seconds < 0:
            raise ValueError("Accounting elapsed time must be finite and nonnegative")
        if self.last_stop is not None and self.last_stop not in _STOPS:
            raise ValueError("Invalid accounting stop reason")
        if not isinstance(self.attempts, tuple) or not all(isinstance(a, AttemptState) for a in self.attempts):
            raise ValueError("Invalid accounting attempts")
        if len({a.request_id for a in self.attempts}) != len(self.attempts):
            raise ValueError("Duplicate accounting attempt")


def _decimal(value: Any) -> Decimal:
    if not isinstance(value, str):
        raise ValueError("Accounting money must be encoded as a decimal string")
    result = Decimal(value)
    if not result.is_finite() or result < 0:
        raise ValueError("Invalid accounting money")
    return result


def _object(value: Any, keys: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError("Invalid accounting state fields")
    return value


def state_to_dict(state: LedgerState) -> dict[str, Any]:
    """Encode monetary quantities as decimal strings, never JSON floats."""
    data = asdict(state)
    data["version"] = 1
    if state.limits.max_cost is not None:
        data["limits"]["max_cost"] = str(state.limits.max_cost)
    for attempt in data["attempts"]:
        pricing = attempt["estimate"]["pricing"]
        if pricing is not None:
            for name in ("input_per_1k", "output_per_1k", "cache_read_per_1k", "cache_write_per_1k"):
                if pricing[name] is not None:
                    pricing[name] = str(pricing[name])
        for billing in attempt["billings"]:
            billing["amount"] = str(billing["amount"])
    return data


def state_from_dict(value: Any) -> LedgerState:
    """Reject malformed/newer states instead of reconstructing empty capacity."""
    try:
        data = _object(value, {"version", "run_id", "limits", "attempts", "elapsed_seconds", "last_stop"})
        if type(data["version"]) is not int or data["version"] != 1:
            raise ValueError("Unsupported accounting state version")
        limits = dict(_object(data["limits"], {"max_requests", "max_tokens", "max_seconds", "max_cost", "currency"}))
        if limits["max_cost"] is not None:
            limits["max_cost"] = _decimal(limits["max_cost"])
        if not isinstance(data["attempts"], (list, tuple)):
            raise ValueError("Invalid accounting attempts")
        attempts = []
        for raw in data["attempts"]:
            attempt = dict(_object(raw, {"request_id", "operation_id", "agent_id", "provider", "model", "estimate", "state", "dispatched", "usage", "final_usage", "billings", "final_billings"}))
            estimate = dict(_object(attempt["estimate"], {"prompt_tokens", "max_output_tokens", "pricing", "cache_mode"}))
            if estimate["pricing"] is not None:
                pricing = dict(_object(estimate["pricing"], {"input_per_1k", "output_per_1k", "cache_read_per_1k", "cache_write_per_1k", "currency", "source", "as_of"}))
                for name in ("input_per_1k", "output_per_1k", "cache_read_per_1k", "cache_write_per_1k"):
                    if pricing[name] is not None:
                        pricing[name] = _decimal(pricing[name])
                estimate["pricing"] = TokenPricing(**pricing)
            attempt["estimate"] = RequestEstimate(**estimate)
            usage = _object(attempt["usage"], {"prompt_tokens", "completion_tokens", "total_tokens", "cached_tokens", "cache_creation_tokens", "reasoning_tokens", "source"})
            attempt["usage"] = UsageReport(**usage)
            if not isinstance(attempt["billings"], (list, tuple)) or not isinstance(attempt["final_billings"], (list, tuple)):
                raise ValueError("Invalid accounting billings")
            billings = []
            for raw_billing in attempt["billings"]:
                billing = _object(raw_billing, {"amount", "currency"})
                billings.append(ReportedCost(_decimal(billing["amount"]), billing["currency"]))
            attempt["billings"] = tuple(billings)
            attempt["final_billings"] = tuple(attempt["final_billings"])
            attempts.append(AttemptState(**attempt))
        return LedgerState(data["run_id"], BudgetLimits(**limits), tuple(attempts), data["elapsed_seconds"], cast(StopReason | None, data["last_stop"]))
    except (TypeError, AttributeError, ArithmeticError) as exc:
        raise ValueError("Invalid accounting state") from exc


def encode_state(state: LedgerState) -> str:
    """Serialize complete accounting state without float-converting money."""
    return json.dumps(state_to_dict(state), sort_keys=True, separators=(",", ":"), allow_nan=False)


def decode_state(encoded: str) -> LedgerState:
    """Decode and validate a complete accounting state."""
    return state_from_dict(json.loads(encoded))
