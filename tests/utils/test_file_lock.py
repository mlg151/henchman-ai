"""Shared native lock contracts without optional RAG dependencies."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


def test_file_lock_import_and_use_does_not_import_rag(tmp_path: Path) -> None:
    script = """
import importlib.abc
import sys

class RejectRag(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.startswith(('henchman.rag', 'chromadb')):
            raise AssertionError(f'Unexpected dependency: {fullname}')

sys.meta_path.insert(0, RejectRag())
from henchman.utils.file_lock import FileLock
with FileLock(sys.argv[1]) as lock:
    assert lock.acquired
assert not lock.acquired
assert not any(name.startswith(('henchman.rag', 'chromadb')) for name in sys.modules)
"""
    result = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path / "shared.lock")],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_shared_lock_excludes_legacy_rag_lock(tmp_path: Path) -> None:
    from henchman.rag.concurrency import RagLock
    from henchman.utils.file_lock import FileLock

    path = tmp_path / "shared.lock"
    contender = RagLock(path)
    with FileLock(path):
        assert not contender.acquire(timeout=0.01)
    try:
        assert contender.acquire(timeout=0.1)
    finally:
        contender.release()


def test_context_timeout_preserves_legacy_exception(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from henchman.rag.concurrency import LockTimeoutError as RagLockTimeoutError
    from henchman.utils.file_lock import FileLock

    lock = FileLock(tmp_path / "shared.lock")
    monkeypatch.setattr(lock, "acquire", lambda: False)
    with pytest.raises(RagLockTimeoutError) as error, lock:
        pytest.fail("Timed out lock entered its critical section")
    assert error.value.timeout == 5.0
    assert error.value.lock_path == str(lock.lock_path)
