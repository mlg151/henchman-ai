"""Read-only usage observations, separate from budget holds and provider bills."""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from typing import Any

from henchman.core.run_budget import BudgetSnapshot
from henchman.providers.usage import TokenPricing, UsageReport, UsageSource
from henchman.utils.evidence_redaction import EvidenceRedactor

_COUNT_FIELDS = tuple(item.name for item in fields(UsageReport) if item.name != "source")


@dataclass
class UsageSummary:
    """Cumulative observations for one model, source and exact price snapshot.

    Counts are observed subtotals, not final consumption or admission bounds.
    Each field's coverage counts requests supplying that field. Cache/reasoning
    fields remain subsets; missing values are never added as zero observations.
    """

    provider: str | None
    model: str | None
    usage_source: UsageSource
    pricing: TokenPricing | None
    dispatched_requests: int = 0
    settled_requests: int = 0
    counts: dict[str, int | None] = field(default_factory=lambda: dict.fromkeys(_COUNT_FIELDS))
    counted_requests: dict[str, int] = field(default_factory=lambda: dict.fromkeys(_COUNT_FIELDS, 0))


def summarize_usage(snapshot: BudgetSnapshot) -> tuple[UsageSummary, ...]:
    """Group dispatched attempts once, retaining unknown and incomplete evidence."""
    groups: dict[tuple[str | None, str | None, UsageSource, TokenPricing | None], UsageSummary] = {}
    for record in snapshot.records:
        if not record.dispatched:
            continue
        key = (record.provider, record.model, record.usage.source, record.estimate.pricing)
        summary = groups.setdefault(key, UsageSummary(*key))
        summary.dispatched_requests += 1
        summary.settled_requests += record.settled_tokens is not None
        if record.usage.source == "unknown":
            continue
        for name in _COUNT_FIELDS:
            count = getattr(record.usage, name)
            if count is not None:
                summary.counts[name] = (summary.counts[name] or 0) + count
                summary.counted_requests[name] += 1
    return tuple(groups.values())


def budget_evidence_redactor(runtime: Any) -> EvidenceRedactor:
    """Retain current and rotated credentials for emitted accounting labels.

    Inspect only already-bound runtime objects; never open or create authority.
    Numeric accounting and executable provider/model identities remain untouched.
    """
    policy = getattr(runtime, "_budget_evidence_redactor", None)
    if not isinstance(policy, EvidenceRedactor):
        policy = EvidenceRedactor()
        runtime._budget_evidence_redactor = policy
    operation_runtime = getattr(runtime, "operation_runtime", None)
    session = getattr(operation_runtime, "current_session", None)
    session_policy = getattr(session, "evidence_redactor", None)
    if isinstance(session_policy, EvidenceRedactor):
        policy.register_policy(session_policy)
    settings = getattr(runtime, "settings", None)
    dump = getattr(settings, "model_dump", None)
    if callable(dump):
        policy.register_config(dump())
    for provider in (getattr(runtime, "default_provider", None),
                     getattr(runtime, "provider", None),
                     getattr(getattr(runtime, "agent", None), "provider", None)):
        key = getattr(provider, "api_key", None)
        if isinstance(key, str):
            policy.register_secret(key)
    return policy
