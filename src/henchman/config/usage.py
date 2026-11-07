"""Adapt typed accounting settings without changing provider construction."""

from __future__ import annotations

from henchman.config.schema import Settings
from henchman.core.run_budget import BudgetLimits
from henchman.providers.usage import TokenPricing


def run_budget_limits(settings: Settings) -> BudgetLimits:
    """Capture shared limits, preserving every explicit zero and Decimal amount."""
    limits = settings.usage.limits
    return BudgetLimits(
        max_requests=limits.max_requests,
        max_tokens=limits.max_tokens,
        max_seconds=limits.max_seconds,
        max_cost=limits.max_cost,
        currency=limits.currency,
    )


def model_pricing(settings: Settings, *, provider: str, model: str) -> TokenPricing | None:
    """Capture the exact provider/model price; missing entries remain unknown."""
    for price in settings.usage.prices:
        if price.provider == provider and price.model == model:
            return TokenPricing(
                input_per_1k=price.input_per_1k,
                output_per_1k=price.output_per_1k,
                cache_read_per_1k=price.cache_read_per_1k,
                cache_write_per_1k=price.cache_write_per_1k,
                currency=price.currency,
                source=price.source,
                as_of=price.as_of.isoformat() if price.as_of is not None else None,
            )
    return None
