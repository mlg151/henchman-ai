"""Concurrency utilities for RAG system.

This module provides locking and retry mechanisms to support
multiple concurrent instances of henchman using the RAG system.
"""

from __future__ import annotations

import time
from functools import wraps
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar

from henchman.utils.file_lock import DEFAULT_LOCK_TIMEOUT as DEFAULT_LOCK_TIMEOUT
from henchman.utils.file_lock import FileLock as RagLock
from henchman.utils.file_lock import LockTimeoutError as LockTimeoutError
from henchman.utils.file_lock import _set_file_lock as _set_file_lock

__all__ = [
    "DEFAULT_LOCK_TIMEOUT",
    "LockTimeoutError",
    "RagLock",
    "acquire_rag_lock",
    "is_lock_error",
    "retry_on_locked",
]

if TYPE_CHECKING:
    from collections.abc import Callable

T = TypeVar("T")


def acquire_rag_lock(lock_path: Path | str, timeout: float = 5.0) -> tuple[bool, RagLock | None]:
    """Convenience function to acquire a RAG lock.

    Args:
        lock_path: Path to the lock file.
        timeout: Maximum time to wait for lock (seconds).

    Returns:
        Tuple of (success, lock) where success is True if lock
        was acquired, and lock is the RagLock object if successful.
    """
    lock = RagLock(lock_path)
    if lock.acquire(timeout):
        return True, lock
    return False, None


def _execute_with_retry(
    func: Callable[..., T],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    max_retries: int,
    delay: float,
) -> T:
    """Execute *func* with exponential-backoff retry on database lock errors.

    Args:
        func: Callable to invoke.
        args: Positional arguments for *func*.
        kwargs: Keyword arguments for *func*.
        max_retries: Maximum number of attempts.
        delay: Base delay between retries (seconds); doubles each attempt.

    Returns:
        The return value of *func* on success.

    Raises:
        The last exception if all retries are exhausted or the error is not
        lock-related.
    """
    last_exception: Exception | None = None

    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            last_exception = e
            if not is_lock_error(e) or attempt == max_retries - 1:
                raise
            time.sleep(min(delay * (2**attempt), 1.0))

    raise last_exception  # type: ignore  # pragma: no cover


def retry_on_locked(
    max_retries: int = 3,
    delay: float = 0.1,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator to retry operations on database lock errors.

    This decorator catches exceptions that indicate a database is
    locked (e.g., SQLITE_BUSY) and retries the operation after a delay.

    Args:
        max_retries: Maximum number of retry attempts.
        delay: Initial delay between retries (seconds).

    Returns:
        Decorated function that retries on lock errors.
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        """The actual decorator function."""

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            """Wrapper that delegates to _execute_with_retry."""
            return _execute_with_retry(func, args, kwargs, max_retries, delay)

        return wrapper

    return decorator


def is_lock_error(exception: Exception) -> bool:
    """Check if an exception indicates a database lock error.

    Args:
        exception: The exception to check.

    Returns:
        True if the exception indicates a lock error.
    """
    error_str = str(exception).lower()
    return any(
        phrase in error_str
        for phrase in [
            "locked",
            "sqlite_busy",
            "resource temporarily unavailable",
            "database is locked",
        ]
    )
