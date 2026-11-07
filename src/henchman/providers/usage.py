"""Portable usage snapshots and explicit configured token-price estimates."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Literal

UsageSource = Literal["reported", "estimated", "unknown"]
MoneyRate = Decimal | float | int


def usage_field(value: Any, name: str) -> Any:
    """Read a usage field from either SDK models or compatible wire mappings."""
    return value.get(name) if isinstance(value, dict) else getattr(value, name, None)


def token_count(value: Any, name: str) -> int | None:
    """Read a reported nonnegative token count without inventing missing values."""
    count = usage_field(value, name)
    if count is None:
        return None
    if type(count) is not int or count < 0:
        raise ValueError(f"{name} must be a nonnegative integer")
    return count


@dataclass(frozen=True)
class UsageReport:
    """Cumulative usage for one request; cache/reasoning counts are subsets."""

    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    cached_tokens: int | None = None
    cache_creation_tokens: int | None = None
    reasoning_tokens: int | None = None
    source: UsageSource = "unknown"

    def __post_init__(self) -> None:
        if self.source not in ("reported", "estimated", "unknown"):
            raise ValueError("Usage source must be reported, estimated or unknown")
        for name, value in asdict(self).items():
            if name != "source" and value is not None and (type(value) is not int or value < 0):
                raise ValueError(f"{name} must be a nonnegative integer")
        if self.prompt_tokens is not None:
            cached = (self.cached_tokens or 0) + (self.cache_creation_tokens or 0)
            if cached > self.prompt_tokens:
                raise ValueError("Cached token subsets exceed prompt_tokens")
        if self.completion_tokens is not None and (self.reasoning_tokens or 0) > self.completion_tokens:
            raise ValueError("Reasoning token subset exceeds completion_tokens")
        if self.total_tokens is None and self.prompt_tokens is not None and self.completion_tokens is not None:
            object.__setattr__(self, "total_tokens", self.prompt_tokens + self.completion_tokens)

    def to_counts(self) -> dict[str, int]:
        """Serialize only known counts, preserving the existing provider contract."""
        return {name: value for name, value in asdict(self).items() if name != "source" and value is not None}


def validate_money(value: MoneyRate, name: str) -> None:
    """Reject negative, nonfinite, boolean and nonnumeric monetary values."""
    finite = (
        value.is_finite() if isinstance(value, Decimal)
        else type(value) is int or (type(value) is float and math.isfinite(value))
    )
    if not finite or value < 0:
        raise ValueError(f"{name} must be a finite nonnegative number")


@dataclass(frozen=True)
class TokenPricing:
    """A configured price snapshot, never a provider billing observation."""

    input_per_1k: MoneyRate | None = None
    output_per_1k: MoneyRate | None = None
    cache_read_per_1k: MoneyRate | None = None
    cache_write_per_1k: MoneyRate | None = None
    currency: str = "USD"
    source: str = "configured"
    as_of: str | None = None

    def __post_init__(self) -> None:
        for name in ("input_per_1k", "output_per_1k", "cache_read_per_1k", "cache_write_per_1k"):
            value = getattr(self, name)
            if value is not None:
                validate_money(value, name)
        if len(self.currency) != 3 or not self.currency.isascii() or not self.currency.isupper() or not self.currency.isalpha():
            raise ValueError("Pricing currency must be a three-letter uppercase code")
        if not self.source.strip():
            raise ValueError("Pricing source must be nonempty")
        if self.as_of is not None:
            date.fromisoformat(self.as_of)

    @classmethod
    def uniform(cls, rate: MoneyRate) -> TokenPricing:
        """Preserve an explicitly configured legacy uniform rate, including zero."""
        return cls(rate, rate, rate, rate)

    def estimate(self, usage: UsageReport) -> float | None:
        """Price known usage, returning unknown if a required count/rate is absent."""
        if usage.source == "unknown" or usage.prompt_tokens is None or usage.completion_tokens is None:
            return None
        cached = usage.cached_tokens or 0
        created = usage.cache_creation_tokens or 0
        parts = (
            (usage.prompt_tokens - cached - created, self.input_per_1k),
            (usage.completion_tokens, self.output_per_1k),
            (cached, self.cache_read_per_1k),
            (created, self.cache_write_per_1k),
        )
        amount = Decimal(0)
        for count, rate in parts:
            if count:
                if rate is None:
                    return None
                amount += Decimal(count) * Decimal(str(rate)) / 1000
        return float(amount)
