"""Private, bounded, atomic JSON checkpoint records and restore journals."""

from __future__ import annotations

import json
import os
import stat
import sys
import tempfile
import threading
from collections.abc import Iterator
from contextlib import AbstractContextManager, ExitStack, contextmanager
from pathlib import Path
from typing import Any

from henchman.utils.file_lock import FileLock


class CheckpointStore:
    def __init__(self, project: Path, max_bytes: int) -> None:
        self.path = project / ".henchman" / "tungsten" / "checkpoints"
        self.max_bytes = max_bytes
        self._directories: dict[Path, tuple[int, int]] = {}
        self._windows = None
        if sys.platform == "win32":
            from henchman.advanced.checkpoint_windows import windows_api

            self._windows = windows_api()
        with ExitStack() as stack:
            if self._windows is not None:
                stack.enter_context(self._windows.directories(project))
            for directory in (project / ".henchman", project / ".henchman/tungsten", self.path, self.path / "plans"):
                if self._windows is not None and directory in {self.path, self.path / "plans"}:
                    self._windows.private_directory(directory)
                else:
                    directory.mkdir(mode=0o700, exist_ok=True)
                if self._windows is not None:
                    stack.enter_context(self._windows.open(directory, directory=True))
                info = directory.lstat()
                if not stat.S_ISDIR(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
                    raise ValueError("Checkpoint storage must not contain links, reparse points or non-directories")
                if os.name == "posix" and directory == self.path and info.st_mode & 0o077:
                    raise ValueError("Existing checkpoint storage must be private (mode 0700)")
                self._directories[directory] = (info.st_dev, info.st_ino)
            lock = self.path / ".lock"
            if self._windows is not None:
                try:
                    with self._windows.open(lock, create=True, writable=True):
                        pass
                except FileExistsError:
                    with self._windows.open(lock, attributes_only=True, share=3) as handle:
                        self._windows.check_private(handle)
            else:
                descriptor = os.open(lock, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
                os.close(descriptor)
        self._lock_path = lock
        self._thread_lock = threading.RLock()

    @property
    def lock(self) -> AbstractContextManager[None]:
        return self._locked()

    @contextmanager
    def _locked(self) -> Iterator[None]:
        with self._thread_lock, ExitStack() as stack:
            if self._windows is not None:
                stack.enter_context(self._windows.directories(self.path / "plans"))
                handle = stack.enter_context(self._windows.open(self._lock_path, attributes_only=True, share=3))
                self._windows.check_private(handle)
            stack.enter_context(FileLock(self._lock_path))
            self.check()
            # A dead writer may leave only an uncommitted atomic record temp.
            # Native locking proves no other service writer owns it now.
            for directory in (self.path, self.path / "plans"):
                for temporary in directory.glob(".record-*"):
                    info = temporary.lstat()
                    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or getattr(info, "st_file_attributes", 0) & 0x400:
                        raise ValueError("Unsupported checkpoint temporary")
                    temporary.unlink()
            yield

    def check(self) -> None:
        for path, identity in self._directories.items():
            info = path.lstat()
            if not stat.S_ISDIR(info.st_mode) or (info.st_dev, info.st_ino) != identity:
                raise ValueError("Checkpoint storage identity changed")
            if self._windows is not None:
                with self._windows.open(path, directory=True) as handle:
                    if path in {self.path, self.path / "plans"}:
                        self._windows.check_private(handle, protected=True)
            if os.name == "posix" and path == self.path and info.st_mode & 0o077:
                raise ValueError("Checkpoint storage is no longer private")

    def usage(self) -> int:
        self.check()
        total = 0
        for path in self.path.rglob("*"):
            info = path.lstat()
            if (stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400
                    or not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode))):
                raise ValueError("Unsupported object in checkpoint storage")
            if stat.S_ISREG(info.st_mode):
                if self._windows is not None:
                    with self._windows.open(path, attributes_only=True, share=3) as handle:
                        self._windows.check_private(handle)
                total += info.st_size
        return total

    def reserve(self, size: int, *, replacing: Path | None = None) -> None:
        existing = replacing.stat().st_size if replacing is not None and replacing.exists() else 0
        if self.usage() + size - existing > self.max_bytes:
            raise ValueError("Checkpoint storage limit reached; discard completed history or increase its bound")

    def read(self, path: Path) -> dict[str, Any]:
        self.check()
        if self._windows is not None:
            with self._windows.open(path) as handle:
                self._windows.check_file(handle)
                self._windows.check_private(handle)
                if self._windows.info(handle).size > self.max_bytes:
                    raise ValueError("Unsupported checkpoint record")
                payload = json.loads(self._windows.read(handle, self.max_bytes))
            if not isinstance(payload, dict) or payload.get("version") != 1:
                raise ValueError("Unsupported checkpoint version or corrupt record")
            return payload
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
        with os.fdopen(descriptor, "rb") as handle:
            info = os.fstat(handle.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > self.max_bytes:
                raise ValueError("Unsupported checkpoint record")
            payload = json.loads(handle.read(self.max_bytes + 1))
        if not isinstance(payload, dict) or payload.get("version") != 1:
            raise ValueError("Unsupported checkpoint version or corrupt record")
        return payload

    def write(self, path: Path, payload: dict[str, Any]) -> None:
        self.check()
        data = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()
        self.reserve(len(data), replacing=path)
        descriptor, temporary = tempfile.mkstemp(prefix=".record-", dir=path.parent)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
            self.sync_directory(path.parent)
        finally:
            Path(temporary).unlink(missing_ok=True)

    @staticmethod
    def sync_directory(path: Path) -> None:
        if sys.platform != "win32" and os.name == "posix":
            descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
