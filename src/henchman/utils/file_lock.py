"""Dependency-free native file locking for shared persistence."""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any, Self

# Default timeout (seconds) used when no explicit timeout is provided
DEFAULT_LOCK_TIMEOUT: float = 5.0


def _set_file_lock(lock_file: Any, *, unlock: bool = False) -> None:
    """Use the host's native nonblocking lock, always at the same file offset."""
    if sys.platform == "win32":
        import msvcrt

        # Windows locks a byte range from the current position, including past
        # EOF. Avoid writing an initial byte before another process owns it.
        lock_file.seek(0)
        msvcrt.locking(
            lock_file.fileno(), msvcrt.LK_UNLCK if unlock else msvcrt.LK_NBLCK, 1
        )
    else:
        import fcntl

        fcntl.flock(
            lock_file, fcntl.LOCK_UN if unlock else fcntl.LOCK_EX | fcntl.LOCK_NB
        )


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


class FileLock:
    """Native file lock for coordinating operations across processes.

    This lock uses native POSIX or Windows file locking to prevent
    multiple instances from entering the same critical section simultaneously.

    Attributes:
        lock_path: Path to the lock file.
        lock_file: File object used for locking (if acquired).
        acquired: Whether the lock is currently held.
    """

    def __init__(self: FileLock, lock_path: Path | str) -> None:
        """Initialize the lock.

        Args:
            lock_path: Path where the lock file should be created.
        """
        self.lock_path = Path(lock_path)
        self.lock_file: Any | None = None
        self._acquired = False

    @property
    def acquired(self: FileLock) -> bool:
        """Check if the lock is currently acquired."""
        return self._acquired

    def _try_acquire_once(self: FileLock) -> bool:
        """Attempt to acquire the lock a single time.

        Returns:
            True if the lock was acquired, False if it is held by another process.
        """
        try:
            self.lock_path.parent.mkdir(parents=True, exist_ok=True)
            # Descriptor stays open for the lifetime of the acquired lock.
            self.lock_file = open(self.lock_path, "a+b")  # noqa: SIM115
            _set_file_lock(self.lock_file)
            self._acquired = True
        except (OSError, BlockingIOError):
            if self.lock_file:
                self.lock_file.close()
                self.lock_file = None
            return False
        else:
            return True

    def acquire(self: FileLock, timeout: float = 5.0) -> bool:
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

    def release(self: FileLock) -> None:
        """Release the lock if it is held.

        Returns:
            None
        """
        if self._acquired and self.lock_file:
            try:
                _set_file_lock(self.lock_file, unlock=True)
            finally:
                self.lock_file.close()
                self.lock_file = None
                self._acquired = False

    def __enter__(self) -> Self:
        """Context manager entry."""
        if not self.acquire():
            raise LockTimeoutError(self.lock_path, DEFAULT_LOCK_TIMEOUT)
        return self

    def __exit__(self: FileLock, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.release()

    def __del__(self: FileLock) -> None:
        """Destructor to ensure lock is released."""
        self.release()

