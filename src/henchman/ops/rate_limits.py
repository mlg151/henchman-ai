"""Policy rate limiting helpers for Tier 8 APIs."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass

_WINDOWS = {
    "second": 1,
    "seconds": 1,
    "minute": 60,
    "minutes": 60,
    "hour": 3600,
    "hours": 3600,
    "day": 86400,
    "days": 86400,
}


@dataclass(frozen=True, slots=True)
class ParsedRateLimit:
    """Normalized rate-limit definition."""

    limit: int
    window_seconds: int
    raw: str


def parse_rate_limit(raw_value: str) -> ParsedRateLimit:
    """Parse a simple rate-limit string.

    Args:
        raw_value: String such as ``100/hour`` or ``2/minute``.

    Returns:
        Parsed rate-limit definition.

    Raises:
        ValueError: If the input cannot be parsed.
    """
    if "/" not in raw_value:
        msg = f"Invalid rate limit: {raw_value}"
        raise ValueError(msg)
    limit_text, window_text = raw_value.split("/", 1)
    window_key = window_text.strip().lower()
    if window_key not in _WINDOWS:
        msg = f"Unsupported rate limit window: {window_text}"
        raise ValueError(msg)
    return ParsedRateLimit(
        limit=int(limit_text.strip()),
        window_seconds=_WINDOWS[window_key],
        raw=raw_value,
    )


class RateLimiter:
    """In-memory fixed-window style rate limiter."""

    def __init__(self, *, time_source: Callable[[], float] | None = None) -> None:
        """Initialize the rate limiter.

        Args:
            time_source: Optional monotonic clock injection for tests.
        """
        self._time_source = time_source or time.monotonic
        self._history: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str, raw_limit: str) -> bool:
        """Return whether a request should be allowed.

        Args:
            key: Rate-limit bucket key.
            raw_limit: Limit expression such as ``100/hour``.

        Returns:
            ``True`` when the request is allowed.
        """
        parsed = parse_rate_limit(raw_limit)
        now = self._time_source()
        bucket = self._history[f"{key}:{parsed.raw}"]
        while bucket and now - bucket[0] >= parsed.window_seconds:
            bucket.popleft()
        if len(bucket) >= parsed.limit:
            return False
        bucket.append(now)
        return True
