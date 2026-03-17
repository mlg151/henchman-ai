"""Concurrency utilities for RAG system.

This module provides locking and retry mechanisms to support
multiple concurrent instances of henchman using the RAG system.
"""

from __future__ import annotations

import fcntl
import time
from functools import wraps
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar

from typing_extensions import Self

if TYPE_CHECKING:
    from collections.abc import Callable

T = TypeVar("T")

# Default timeout (seconds) used when no explicit timeout is provided
DEFAULT_LOCK_TIMEOUT: float = 5.0


class LockTimeoutError(Exception):
    """Exception raised when a lock cannot be acquired within timeout."""

    def __init__(self: LockTimeoutError, lock_path: str | Path, timeout: float) -> None:
        """Initialize the exception.

        Args:
            lock_path: Path to the lock file.
            timeout: Timeout in seconds that was exceeded.
        """
        self.lock_path = str(lock_path)
        self.timeout = timeout
        super().__init__(f"Could not acquire lock at {lock_path} within {timeout} seconds")


class RagLock:
    """File-based lock for RAG system operations.

    This lock uses advisory file locking (fcntl) to prevent multiple
    instances from performing RAG indexing simultaneously.

    Attributes:
        lock_path: Path to the lock file.
        lock_file: File object used for locking (if acquired).
        acquired: Whether the lock is currently held.
    """

    def __init__(self: RagLock, lock_path: Path | str) -> None:
        """Initialize the lock.

        Args:
            lock_path: Path where the lock file should be created.
        """
        self.lock_path = Path(lock_path)
        self.lock_file: Any | None = None
        self._acquired = False

    @property
    def acquired(self: RagLock) -> bool:
        """Check if the lock is currently acquired."""
        return self._acquired

    def _try_acquire_once(self: RagLock) -> bool:
        """Attempt to acquire the lock a single time.

        Returns:
            True if the lock was acquired, False if it is held by another process.
        """
        try:
            self.lock_path.parent.mkdir(parents=True, exist_ok=True)
            self.lock_file = open(self.lock_path, "w")
            fcntl.flock(self.lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self._acquired = True
        except (OSError, BlockingIOError):
            if self.lock_file:
                self.lock_file.close()
                self.lock_file = None
            return False
        else:
            return True

    def acquire(self: RagLock, timeout: float = 5.0) -> bool:
        """Attempt to acquire the lock.

        Args:
            timeout: Maximum time to wait for lock (seconds).

        Returns:
            True if lock was acquired, False if timeout was reached.
        """
        if self._acquired:
            return True

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._try_acquire_once():
                return True
            time.sleep(min(0.1, timeout / 10))

        return False

    def release(self: RagLock) -> None:
        """Release the lock if it is held.

        Returns:
            None
        """
        if self._acquired and self.lock_file:
            try:
                fcntl.flock(self.lock_file, fcntl.LOCK_UN)
            finally:
                self.lock_file.close()
                self.lock_file = None
                self._acquired = False

    def __enter__(self: RagLock) -> Self:
        """Context manager entry."""
        if not self.acquire():
            raise LockTimeoutError(self.lock_path, DEFAULT_LOCK_TIMEOUT)
        return self

    def __exit__(self: RagLock, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.release()

    def __del__(self: RagLock) -> None:
        """Destructor to ensure lock is released."""
        self.release()


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
