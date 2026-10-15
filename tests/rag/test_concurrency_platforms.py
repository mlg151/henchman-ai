"""Native lock portability contracts and actual process exclusion."""

from __future__ import annotations

import builtins
import importlib.util
import os
import subprocess
import sys
from types import ModuleType, SimpleNamespace

import pytest

from henchman.rag.concurrency import RagLock
from henchman.utils import file_lock


@pytest.fixture
def windows_concurrency(monkeypatch):
    """Load without fcntl, then exercise a simulated Windows native API."""
    original_import = builtins.__import__

    def import_without_fcntl(name, *args, **kwargs):
        if name == "fcntl":
            raise ImportError("fcntl is unavailable on Windows")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", import_without_fcntl)
    spec = importlib.util.spec_from_file_location("portable_file_lock", file_lock.__file__)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "sys", SimpleNamespace(platform="win32"))
    native = ModuleType("msvcrt")
    native.LK_NBLCK = 2
    native.LK_UNLCK = 0
    native.calls = []
    native.held = set()

    def locking(fd, mode, count):
        position = os.lseek(fd, 0, os.SEEK_CUR)
        native.calls.append((fd, mode, count, position))
        assert position == 0
        assert count == 1
        identity = os.fstat(fd).st_ino
        if mode == native.LK_NBLCK:
            if identity in native.held:
                raise PermissionError("region locked")
            native.held.add(identity)
        else:
            assert mode == native.LK_UNLCK
            native.held.remove(identity)

    native.locking = locking
    monkeypatch.setitem(sys.modules, "msvcrt", native)
    return module, native


def test_windows_lock_uses_same_nonblocking_byte_for_acquire_and_release(windows_concurrency, tmp_path):
    module, native = windows_concurrency
    path = tmp_path / "index.lock"
    path.write_bytes(b"existing data")
    lock = module.FileLock(path)

    assert lock.acquire(timeout=0.1)
    lock.lock_file.seek(7)
    lock.release()

    assert [call[1:] for call in native.calls] == [(native.LK_NBLCK, 1, 0), (native.LK_UNLCK, 1, 0)]
    assert not lock.acquired
    assert lock.lock_file is None
    assert path.read_bytes() == b"existing data"


def test_windows_contention_times_out_then_reacquires(windows_concurrency, tmp_path):
    module, native = windows_concurrency
    path = tmp_path / "index.lock"
    first, second = module.FileLock(path), module.FileLock(path)
    try:
        assert first.acquire(timeout=0.1)
        assert not second.acquire(timeout=0.01)
        assert second.lock_file is None
        assert not second.acquired
        first.release()
        assert second.acquire(timeout=0.1)
    finally:
        first.release()
        second.release()
    assert not native.held


def test_windows_unlock_error_closes_descriptor(windows_concurrency, monkeypatch, tmp_path):
    module, native = windows_concurrency
    lock = module.FileLock(tmp_path / "index.lock")
    assert lock.acquire(timeout=0.1)
    handle = lock.lock_file

    def broken_unlock(*_args):
        raise OSError("unlock failure")

    monkeypatch.setattr(native, "locking", broken_unlock)
    with pytest.raises(OSError, match="unlock failure"):
        lock.release()
    assert handle.closed
    assert not lock.acquired
    assert lock.lock_file is None


def test_lock_preserves_existing_file_content(tmp_path):
    path = tmp_path / "index.lock"
    path.write_bytes(b"existing data")
    with RagLock(path):
        pass
    assert path.read_bytes() == b"existing data"


def test_native_lock_excludes_other_process_and_releases(tmp_path):
    path = tmp_path / "index.lock"
    script = (
        "import sys\n"
        "from henchman.rag.concurrency import RagLock\n"
        "lock = RagLock(sys.argv[1])\n"
        "acquired = lock.acquire(timeout=0.05)\n"
        "lock.release()\n"
        "sys.exit(0 if acquired else 7)\n"
    )

    def child_result():
        return subprocess.run(
            [sys.executable, "-c", script, str(path)],
            capture_output=True, text=True, timeout=15, check=False,
        )

    with RagLock(path):
        blocked = child_result()
        assert blocked.returncode == 7, blocked.stderr
    acquired = child_result()
    assert acquired.returncode == 0, acquired.stderr
