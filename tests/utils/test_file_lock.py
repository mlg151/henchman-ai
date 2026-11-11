"""Shared native lock contracts without optional RAG dependencies."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.mark.parametrize("read_size", [1, 32, 257])
def test_windows_locking_uses_kernel_offset_after_buffered_marker_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, read_size: int,
) -> None:
    from henchman.utils import file_lock

    path = tmp_path / "marker.lock"
    marker = b"a" * 32
    path.write_bytes(marker)
    positions: list[tuple[int, int]] = []

    def locking(descriptor: int, operation: int, size: int) -> None:
        position = os.lseek(descriptor, 0, os.SEEK_CUR)
        positions.append((operation, position))
        assert size == 1
        if position != 0:
            raise PermissionError("Windows unlock addresses an unowned byte range")

    monkeypatch.setattr(file_lock, "sys", SimpleNamespace(platform="win32"))
    monkeypatch.setitem(sys.modules, "msvcrt", SimpleNamespace(LK_NBLCK=1, LK_UNLCK=2, locking=locking))
    with file_lock.FileLock(path) as lock:
        assert lock.lock_file.read(read_size) == marker[:read_size]
    assert positions == [(1, 0), (2, 0)]
    assert path.read_bytes() == marker
    assert not lock.acquired and lock.lock_file is None


def test_native_lock_marker_survives_buffered_write_read_and_reacquisition(tmp_path: Path) -> None:
    from henchman.utils.file_lock import FileLock

    path = tmp_path / "marker.lock"
    marker = b"a" * 32
    with FileLock(path) as lock:
        lock.lock_file.write(marker)
        lock.lock_file.flush()
        lock.lock_file.seek(0)
        assert lock.lock_file.read(257) == marker
    with FileLock(path) as lock:
        lock.lock_file.seek(0)
        assert lock.lock_file.read(1) == marker[:1]
    assert path.read_bytes() == marker


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
