"""Unit tests for RAG concurrency and locking mechanisms."""

from __future__ import annotations

import tempfile
import time
from pathlib import Path

import pytest

from henchman.rag.concurrency import (
    LockTimeoutError,
    RagLock,
    acquire_rag_lock,
    retry_on_locked,
)


class TestRagLock:
    """Tests for the RagLock class."""

    def test_lock_acquire_and_release(self) -> None:
        """Test basic lock acquisition and release."""
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_path = Path(tmpdir) / "test.lock"
            lock = RagLock(lock_path)

            # Should acquire lock successfully
            assert lock.acquire(timeout=1.0) is True
            assert lock_path.exists()

            # Should release lock
            lock.release()
            # Lock file should still exist
            assert lock_path.exists()

    def test_lock_context_manager(self) -> None:
        """Test lock as context manager."""
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_path = Path(tmpdir) / "test.lock"

            with RagLock(lock_path) as lock:
                assert lock.acquired is True
                assert lock_path.exists()

            # Should be released after context
            assert lock.acquired is False

    def test_lock_timeout(self) -> None:
        """Test lock acquisition timeout when already locked."""
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_path = Path(tmpdir) / "test.lock"

            # Acquire first lock
            lock1 = RagLock(lock_path)
            assert lock1.acquire(timeout=1.0) is True

            # Try to acquire second lock - should timeout
            lock2 = RagLock(lock_path)
            start_time = time.time()
            assert lock2.acquire(timeout=0.5) is False
            elapsed = time.time() - start_time

            # Should have waited approximately the timeout
            assert 0.4 <= elapsed <= 0.6

            # Release first lock
            lock1.release()

            # Now second lock should acquire
            assert lock2.acquire(timeout=0.1) is True
            lock2.release()

    def test_lock_file_creation(self) -> None:
        """Test that lock file is created in correct directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_dir = Path(tmpdir) / "subdir"
            lock_path = lock_dir / "test.lock"

            # Directory doesn't exist yet
            assert not lock_dir.exists()

            lock = RagLock(lock_path)
            assert lock.acquire(timeout=1.0) is True

            # Directory should be created
            assert lock_dir.exists()
            assert lock_path.exists()

            lock.release()

    def test_lock_already_acquired_property(self) -> None:
        """Test the acquired property."""
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_path = Path(tmpdir) / "test.lock"
            lock = RagLock(lock_path)

            assert lock.acquired is False
            lock.acquire(timeout=1.0)
            assert lock.acquired is True
            lock.release()
            assert lock.acquired is False


class TestAcquireRagLockFunction:
    """Tests for the acquire_rag_lock function."""

    def test_successful_acquisition(self) -> None:
        """Test successful lock acquisition."""
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_path = Path(tmpdir) / "test.lock"

            acquired, lock = acquire_rag_lock(lock_path, timeout=1.0)
            assert acquired is True
            assert lock is not None
            assert lock_path.exists()

            # Clean up
            if lock:
                lock.release()

    def test_failed_acquisition(self) -> None:
        """Test failed lock acquisition when already locked."""
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_path = Path(tmpdir) / "test.lock"

            # Acquire first lock
            acquired1, lock1 = acquire_rag_lock(lock_path, timeout=1.0)
            assert acquired1 is True

            # Try to acquire second lock - should fail
            acquired2, lock2 = acquire_rag_lock(lock_path, timeout=0.1)
            assert acquired2 is False
            assert lock2 is None

            # Clean up
            if lock1:
                lock1.release()


class TestRetryOnLockedDecorator:
    """Tests for the retry_on_locked decorator."""

    def test_successful_first_try(self) -> None:
        """Test function that succeeds on first try."""
        call_count = 0

        @retry_on_locked(max_retries=3, delay=0.01)
        def successful_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = successful_func()
        assert result == "success"
        assert call_count == 1

    def test_retry_on_locked_error(self) -> None:
        """Test function that retries on locked error."""
        call_count = 0

        @retry_on_locked(max_retries=3, delay=0.01)
        def retrying_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RuntimeError("Database is locked")
            return "success"

        result = retrying_func()
        assert result == "success"
        assert call_count == 3

    def test_max_retries_exceeded(self) -> None:
        """Test function that exceeds max retries."""
        call_count = 0

        @retry_on_locked(max_retries=2, delay=0.01)
        def failing_func():
            nonlocal call_count
            call_count += 1
            raise RuntimeError("Database is locked")

        with pytest.raises(RuntimeError, match="Database is locked"):
            failing_func()

        assert call_count == 2

    def test_non_lock_error_not_retried(self) -> None:
        """Test that non-lock errors are not retried."""
        call_count = 0

        @retry_on_locked(max_retries=3, delay=0.01)
        def error_func():
            nonlocal call_count
            call_count += 1
            raise ValueError("Some other error")

        with pytest.raises(ValueError, match="Some other error"):
            error_func()

        assert call_count == 1

    def test_lock_error_pattern_matching(self) -> None:
        """Test that various lock error messages are detected."""
        lock_messages = [
            "database is locked",
            "Database is locked",
            "SQLITE_BUSY",
            "locked database",
            "resource temporarily unavailable",
        ]

        for message in lock_messages:
            call_count = 0

            @retry_on_locked(max_retries=2, delay=0.01)
            def func(msg: str = message):  # noqa: B023
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    raise RuntimeError(msg)
                return "success"

            result = func()
            assert result == "success"
            assert call_count == 2


class TestLockTimeoutError:
    """Tests for LockTimeoutError exception."""

    def test_exception_creation(self) -> None:
        """Test creating LockTimeoutError."""
        error = LockTimeoutError("test.lock", 5.0)
        assert error.lock_path == "test.lock"
        assert error.timeout == 5.0
        assert "test.lock" in str(error)
        assert "5.0" in str(error)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
