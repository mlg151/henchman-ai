"""Construct public-run accounting and expose truthful aggregate evidence."""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields, is_dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from henchman.core.run_budget import BudgetAccountingError, BudgetSnapshot, RunBudgetLedger
from henchman.core.usage_summary import summarize_usage
from henchman.providers.runtime_budget import RunBudgetScope, current_run_budget
from henchman.utils.evidence_redaction import EvidenceRedactor

if TYPE_CHECKING:
    from henchman.config.schema import Settings
    from henchman.providers.base import ModelProvider


@dataclass
class RunInvocation:
    """Evidence and cleanup ownership for one public invocation, even on failure."""

    claimed: bool = False
    budget_scope: RunBudgetScope | None = None


def new_run_budget(settings: Settings, provider: ModelProvider) -> RunBudgetScope | None:
    """Capture settings for one run; bounded unsupported providers fail closed.

    Uninstrumented extensions remain usable with no configured limits or prices.
    They cannot produce authoritative accounting evidence for that run.
    """
    from henchman.config.usage import model_pricing, run_budget_limits

    captured = settings.model_copy(deep=True)
    limits = run_budget_limits(captured)
    bounded = any(value is not None for value in (
        limits.max_requests, limits.max_tokens, limits.max_seconds, limits.max_cost,
    ))
    if getattr(provider, "supports_run_budget", False) is not True and not bounded and not captured.usage.prices:
        return None
    return RunBudgetScope(
        RunBudgetLedger(limits=limits),
        pricing_resolver=lambda provider, model: model_pricing(captured, provider=provider, model=model),
    )


def public_run_budget(
    settings: Settings, provider: ModelProvider, supplied: RunBudgetScope | None,
) -> RunBudgetScope | None:
    """Retain an enclosing run; otherwise use an explicit or newly captured run."""
    ambient = current_run_budget()
    if ambient is not None:
        if supplied is not None and supplied.ledger is not ambient.ledger:
            raise BudgetAccountingError("Cannot replace active accounting with a different run budget")
        return ambient
    return supplied if supplied is not None else new_run_budget(settings, provider)


def budget_snapshot_payload(snapshot: BudgetSnapshot, *, redactor: EvidenceRedactor | None = None) -> dict[str, Any]:
    """Serialize aggregate accounting; absent charges remain null, never zero.

    Monetary decimals remain exact strings. Provider estimates, reported billing
    and conservative holds retain their distinct field names and currencies.
    """
    def value(item: Any) -> Any:
        if isinstance(item, Decimal):
            return str(item)
        if is_dataclass(item) and not isinstance(item, type):
            return value(asdict(item))
        if isinstance(item, dict):
            return {key: value(child) for key, child in item.items()}
        if isinstance(item, (tuple, list)):
            return [value(child) for child in item]
        return item

    payload = {
        field.name: value(getattr(snapshot, field.name))
        for field in fields(snapshot) if field.name != "records"
    }
    policy = redactor if redactor is not None else EvidenceRedactor()
    breakdown = []
    for summary in summarize_usage(snapshot):
        row = value(summary)
        for name in ("provider", "model"):
            if row[name] is not None:
                row[name] = policy.text(row[name])
        if summary.pricing is not None:
            price = row["pricing"]
            for name in ("input_per_1k", "output_per_1k", "cache_read_per_1k", "cache_write_per_1k"):
                rate = getattr(summary.pricing, name)
                price[name] = str(rate) if rate is not None else None
            for name in ("source", "as_of"):
                if price[name] is not None:
                    price[name] = policy.text(price[name])
        breakdown.append(row)
    payload["usage_breakdown"] = breakdown
    return payload
