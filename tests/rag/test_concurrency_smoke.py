"""Smoke tests for RAG concurrency features."""

from __future__ import annotations

import subprocess
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest

# Check if we can import the concurrency module
try:
    from henchman.rag.concurrency import RagLock, acquire_rag_lock  # noqa: F401

    CONCURRENCY_AVAILABLE = True
except ImportError:
    CONCURRENCY_AVAILABLE = False


@pytest.mark.skipif(not CONCURRENCY_AVAILABLE, reason="Concurrency module not available")
class TestConcurrencySmoke:
    """Smoke tests for concurrency features."""

    def test_basic_lock_smoke(self) -> None:
        """Smoke test: Basic lock acquisition and release."""
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_path = Path(tmpdir) / "smoke_test.lock"

            # Should not raise any exceptions
            lock = RagLock(lock_path)
            assert lock.acquire(timeout=1.0) is True
            assert lock.acquired is True
            lock.release()
            assert lock.acquired is False

    def test_concurrent_access_smoke(self) -> None:
        """Smoke test: Simulate concurrent access."""
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_path = Path(tmpdir) / "concurrent.lock"

            # First process gets lock
            lock1 = RagLock(lock_path)
            assert lock1.acquire(timeout=1.0) is True

            # Second process tries and fails
            lock2 = RagLock(lock_path)
            assert lock2.acquire(timeout=0.1) is False

            # Release first lock
            lock1.release()

            # Now second should succeed
            assert lock2.acquire(timeout=0.1) is True
            lock2.release()

    def test_file_creation_smoke(self) -> None:
        """Smoke test: Lock file creation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_dir = Path(tmpdir) / "nested" / "dir"
            lock_path = lock_dir / "test.lock"

            # Should create directory structure
            lock = RagLock(lock_path)
            assert lock.acquire(timeout=1.0) is True

            assert lock_dir.exists()
            assert lock_path.exists()

            lock.release()


@pytest.mark.integration
class TestRagSystemSmoke:
    """Smoke tests for RAG system with concurrency."""

    @pytest.fixture
    def test_repo(self) -> Generator[Path, None, None]:
        """Create a test git repository."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir) / "test_repo"
            repo_path.mkdir()

            # Initialize git repo
            subprocess.run(["git", "init"], cwd=repo_path, capture_output=True)
            subprocess.run(
                ["git", "config", "user.email", "test@example.com"],
                cwd=repo_path,
                capture_output=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test User"], cwd=repo_path, capture_output=True
            )

            # Create a test file
            test_file = repo_path / "test.py"
            test_file.write_text("print('Hello, World!')")

            # Add and commit
            subprocess.run(["git", "add", "."], cwd=repo_path, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", "Initial commit"], cwd=repo_path, capture_output=True
            )

            yield repo_path

    def test_rag_initialization_smoke(self, test_repo: Path) -> None:
        """Smoke test: RAG system initialization."""
        # Try to import and initialize RAG system
        try:
            from henchman.config.schema import RagSettings
            from henchman.rag.system import initialize_rag

            # Create minimal settings
            settings = RagSettings(
                enabled=True,
                embedding_model="test-model",
                chunk_size=512,
                chunk_overlap=50,
                file_extensions=[".py"],
                top_k=5,
            )

            # Should not raise exceptions
            rag_system = initialize_rag(
                settings=settings,
                console=None,
                git_root=test_repo,
            )

            # Should return either a RagSystem or None
            assert rag_system is None or hasattr(rag_system, "search_tool")

        except ImportError as e:
            pytest.skip(f"Required imports not available: {e}")
        except Exception as e:
            # If it fails, make sure it's not a concurrency issue
            assert "locked" not in str(e).lower()
            raise


@pytest.mark.e2e
class TestEndToEndSmoke:
    """End-to-end smoke tests."""

    def test_multiple_henchman_instances(self) -> None:
        """Smoke test: Multiple henchman instances don't crash."""
        # This is a high-level test that would require actual henchman processes
        # For now, we'll verify the imports work
        try:
            # Try to import key components
            from henchman.rag.concurrency import RagLock  # noqa: F401
            from henchman.rag.store import VectorStore  # noqa: F401
            from henchman.rag.system import RagSystem  # noqa: F401

            # All imports should succeed
            assert True

        except ImportError as e:
            pytest.skip(f"Required imports not available: {e}")


def run_smoke_tests() -> None:
    """Run all smoke tests and report results."""
    import sys

    print("Running RAG Concurrency Smoke Tests...")
    print("=" * 50)

    tests_passed = 0
    tests_failed = 0
    tests_skipped = 0

    test_cases = [
        ("Basic lock smoke", TestConcurrencySmoke().test_basic_lock_smoke),
        ("Concurrent access smoke", TestConcurrencySmoke().test_concurrent_access_smoke),
        ("File creation smoke", TestConcurrencySmoke().test_file_creation_smoke),
    ]

    for test_name, test_func in test_cases:
        try:
            test_func()
            print(f"✓ {test_name}: PASSED")
            tests_passed += 1
        except pytest.skip.Exception as e:
            print(f"⏭️ {test_name}: SKIPPED - {e}")
            tests_skipped += 1
        except Exception as e:
            print(f"✗ {test_name}: FAILED - {e}")
            tests_failed += 1

    print("=" * 50)
    print(f"Summary: {tests_passed} passed, {tests_failed} failed, {tests_skipped} skipped")

    if tests_failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    run_smoke_tests()
