"""Rate limiting utilities for API providers."""

import asyncio
import time
from collections import deque


class AsyncRateLimiter:
    """An asynchronous rate limiter using a sliding window.

    Tracks token usage and provides a way to wait until enough capacity
    is available.
    """

    def __init__(self, tokens_per_minute: int) -> None:
        """Initialize the rate limiter.

        Args:
            tokens_per_minute: Maximum tokens allowed per 60-second window.
        """
        self.tokens_per_minute = tokens_per_minute
        # Each entry is (timestamp, token_count)
        self.usage: deque[tuple[float, int]] = deque()
        self._lock = asyncio.Lock()

    async def _clean_old_usage(self) -> None:
        """Remove usage entries older than 60 seconds."""
        now = time.time()
        while self.usage and self.usage[0][0] < now - 60:
            self.usage.popleft()

    def _get_current_usage(self) -> int:
        """Calculate the total tokens used in the last 60 seconds."""
        return sum(tokens for _, tokens in self.usage)

    async def wait_for_capacity(self, tokens: int) -> None:
        """Wait until the specified number of tokens can be used.

        Args:
            tokens: The number of tokens to be used.
        """
        if tokens > self.tokens_per_minute:
            # If a single request is larger than the limit, we can't really
            # satisfy it, but we'll just wait for the window to be completely clear.
            tokens = self.tokens_per_minute

        async with self._lock:
            while True:
                await self._clean_old_usage()
                current_usage = self._get_current_usage()

                if current_usage + tokens <= self.tokens_per_minute:
                    break

                # Wait until the oldest entry expires
                if self.usage:
                    sleep_time = self.usage[0][0] + 60.1 - time.time()
                    if sleep_time > 0:
                        await asyncio.sleep(sleep_time)
                else:
                    # Should not happen if current_usage > 0, but safety first
                    await asyncio.sleep(1)

    async def add_usage(self, tokens: int) -> None:
        """Record token usage.

        Args:
            tokens: The number of tokens used.
        """
        async with self._lock:
            self.usage.append((time.time(), tokens))
