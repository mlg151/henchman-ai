"""Retry utilities with exponential backoff for resilient operations.

This module provides an async retry decorator with configurable exponential
backoff for handling transient failures in network operations and other
potentially flaky operations.
"""

from __future__ import annotations

import asyncio
import functools
import random
from dataclasses import dataclass
from typing import TYPE_CHECKING, ParamSpec, TypeVar

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

P = ParamSpec("P")
R = TypeVar("R")


@dataclass
class RetryConfig:
    """Configuration for retry behavior.

    Attributes:
        max_retries: Maximum number of retry attempts (0 = no retries).
        base_delay: Base delay in seconds between retries.
        max_delay: Maximum delay in seconds (cap for exponential growth).
        exponential_base: Base for exponential backoff (default 2.0).
        jitter: Whether to add random jitter to delay (prevents thundering herd).
        retryable_exceptions: Tuple of exception types to retry on.
    """

    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0
    exponential_base: float = 2.0
    jitter: bool = True
    retryable_exceptions: tuple[type[Exception], ...] = (
        ConnectionError,
        TimeoutError,
        OSError,
    )


def calculate_delay(attempt: int, config: RetryConfig) -> float:
    """Calculate delay for a retry attempt with exponential backoff.

    Args:
        attempt: The current retry attempt number (0-indexed).
        config: Retry configuration.

    Returns:
        Delay in seconds before the next retry.

    Example:
        >>> cfg = RetryConfig(base_delay=1.0, exponential_base=2.0, jitter=False)
        >>> calculate_delay(0, cfg)
        1.0
        >>> calculate_delay(1, cfg)
        2.0
        >>> calculate_delay(2, cfg)
        4.0
    """
    delay = config.base_delay * (config.exponential_base**attempt)
    delay = min(delay, config.max_delay)

    if config.jitter:
        # Add random jitter between 0-50% of the delay
        jitter_amount = delay * random.uniform(0, 0.5)
        delay += jitter_amount

    return delay


def with_retry(
    config: RetryConfig | None = None,
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """Decorator for adding retry logic with exponential backoff.

    Args:
        config: Retry configuration. If None, uses defaults.

    Returns:
        Decorated async function with retry logic.

    Example:
        >>> @with_retry(RetryConfig(max_retries=3))
        ... async def fetch_data(url: str) -> str:
        ...     # Network operation that might fail
        ...     return await http_get(url)
    """
    if config is None:
        config = RetryConfig()

    def decorator(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        """Inner decorator that wraps the function with retry logic."""

        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            """Wrapper function that implements retry with exponential backoff."""
            last_exception: Exception | None = None

            for attempt in range(config.max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except config.retryable_exceptions as exc:  # noqa: PERF203
                    last_exception = exc

                    if attempt < config.max_retries:
                        delay = calculate_delay(attempt, config)
                        await asyncio.sleep(delay)
                    # On last attempt, fall through to raise

            # Should never reach here without an exception, but satisfy type checker
            if last_exception is not None:
                raise last_exception
            msg = "Retry logic error: no exception captured"
            raise RuntimeError(msg)  # pragma: no cover

        return wrapper

    return decorator


async def retry_async(
    func: Callable[[], Awaitable[R]],
    config: RetryConfig | None = None,
) -> R:
    """Execute an async function with retry logic.

    This is a functional alternative to the decorator for cases where
    you want to retry a specific call rather than decorating a function.

    Args:
        func: Zero-argument async callable to execute.
        config: Retry configuration. If None, uses defaults.

    Returns:
        Result of the function call.

    Raises:
        Exception: The last exception if all retries fail.

    Example:
        >>> result = await retry_async(
        ...     lambda: fetch_data("https://api.example.com"),
        ...     config=RetryConfig(max_retries=3)
        ... )
    """
    if config is None:
        config = RetryConfig()

    @with_retry(config)
    async def wrapped() -> R:
        """Wrapped function with retry logic applied."""
        return await func()

    return await wrapped()


__all__ = [
    "RetryConfig",
    "calculate_delay",
    "retry_async",
    "with_retry",
]
