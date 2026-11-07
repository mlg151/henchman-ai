"""Bounded, pre-persistence evidence capture for owned background processes."""

from __future__ import annotations

import asyncio
import codecs
import contextlib
import os
import stat
from collections.abc import Iterator
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4

from henchman.utils.evidence_redaction import EvidenceRedactor, EvidenceStreamRedactor
from henchman.utils.pipe_output import pipe_chunk

MAX_TASK_OUTPUT_BYTES = 1024 * 1024
MAX_LEGACY_LOG_BYTES = 16 * MAX_TASK_OUTPUT_BYTES
_TRUNCATED = b"\n[Task output truncated at the capture limit.]\n"
_FINAL_DRAIN_SECONDS = 0.1


def _ordinary_file(info: os.stat_result) -> None:
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise OSError("Task evidence must be a regular file without links")
    if getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
        raise OSError("Task evidence reparse points are not supported")


@contextlib.contextmanager
def _evidence_directory(directory: Path) -> Iterator[int | None]:
    """Refuse linked directories; anchor POSIX I/O to checked directory FDs."""
    if os.name == "posix":
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        descriptor = os.open(directory.anchor, flags)
        try:
            for component in directory.parts[1:]:
                child = os.open(component, flags, dir_fd=descriptor)
                os.close(descriptor)
                descriptor = child
            yield descriptor
        finally:
            os.close(descriptor)
    else:
        # Python's Windows file APIs lack dir_fd and O_NOFOLLOW. Check all
        # existing components and compare the opened file identity before I/O.
        for component_path in (*reversed(directory.parents), directory):
            info = component_path.lstat()
            if not stat.S_ISDIR(info.st_mode) or (
                getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
            ):
                raise OSError("Task evidence directory links are not supported")
        yield None


def _entry(path: Path, directory_fd: int | None) -> str | Path:
    return path.name if directory_fd is not None else path


def _stat_entry(path: Path, directory_fd: int | None) -> os.stat_result:
    return os.stat(_entry(path, directory_fd), dir_fd=directory_fd, follow_symlinks=False)


@contextlib.contextmanager
def open_evidence(path: Path, *, append: bool = False) -> Iterator[BinaryIO]:
    """Open only a checked regular file, rejecting symlinks before reading."""
    with _evidence_directory(path.parent) as directory_fd:
        original = _stat_entry(path, directory_fd)
        _ordinary_file(original)
        access = os.O_WRONLY | os.O_APPEND if append else os.O_RDONLY
        descriptor = os.open(_entry(path, directory_fd), access | getattr(os, "O_NOFOLLOW", 0)
                             | getattr(os, "O_NONBLOCK", 0), dir_fd=directory_fd)
        try:
            opened = os.fstat(descriptor)
            _ordinary_file(opened)
            if not os.path.samestat(original, opened):
                raise OSError("Task evidence changed before it could be opened")
            output = os.fdopen(descriptor, "ab" if append else "rb", buffering=0)
        except BaseException:
            os.close(descriptor)
            raise
        with output:
            yield output


def _unchanged(original: os.stat_result, current: os.stat_result) -> bool:
    return os.path.samestat(original, current) and (
        original.st_size, original.st_mtime_ns, original.st_ctime_ns
    ) == (current.st_size, current.st_mtime_ns, current.st_ctime_ns)


@contextlib.contextmanager
def atomic_evidence(
    path: Path, *, expected: os.stat_result | None = None,
) -> Iterator[BinaryIO]:
    """Replace evidence privately, preserving the original on any write failure."""
    with _evidence_directory(path.parent) as directory_fd:
        temporary = path.with_name(f".{path.stem}-{uuid4().hex}.tmp")
        descriptor = os.open(_entry(temporary, directory_fd), os.O_WRONLY | os.O_CREAT | os.O_EXCL
                             | getattr(os, "O_NOFOLLOW", 0), 0o600, dir_fd=directory_fd)
        try:
            try:
                output = os.fdopen(descriptor, "wb", buffering=0)
            except BaseException:
                os.close(descriptor)
                raise
            with output:
                yield output
                output.flush()
                os.fsync(output.fileno())
            try:
                current = _stat_entry(path, directory_fd)
            except FileNotFoundError:
                if expected is not None:
                    raise OSError("Task evidence disappeared during migration") from None
            else:
                _ordinary_file(current)
                if expected is not None and not _unchanged(expected, current):
                    raise OSError("Task evidence changed during migration")
            os.replace(_entry(temporary, directory_fd), _entry(path, directory_fd),
                       src_dir_fd=directory_fd, dst_dir_fd=directory_fd)
        finally:
            with contextlib.suppress(FileNotFoundError):
                os.unlink(_entry(temporary, directory_fd), dir_fd=directory_fd)


def write_evidence(output: BinaryIO, payload: bytes) -> None:
    """Finish short writes, treating zero progress as an explicit failure."""
    remaining = memoryview(payload)
    while remaining:
        written = output.write(remaining)
        if written is None or written <= 0:
            raise OSError("Task evidence write made no progress")
        remaining = remaining[written:]


def append_evidence(path: Path, payload: bytes) -> None:
    """Append already projected UTF-8 without following replaced log links."""
    with open_evidence(path, append=True) as output:
        available = max(0, MAX_TASK_OUTPUT_BYTES - os.fstat(output.fileno()).st_size)
        payload = payload[:available].decode("utf-8", errors="ignore").encode("utf-8")
        write_evidence(output, payload)


def _bounded_write(output: BinaryIO, text: str, written: int) -> tuple[int, bool]:
    encoded = text.encode("utf-8")
    available = MAX_TASK_OUTPUT_BYTES - len(_TRUNCATED) - written
    if len(encoded) > available:
        encoded = encoded[:available].decode("utf-8", errors="ignore").encode("utf-8") + _TRUNCATED
        write_evidence(output, encoded)
        return written + len(encoded), True
    write_evidence(output, encoded)
    return written + len(encoded), False


def migrate_evidence(path: Path, policy: EvidenceRedactor) -> bool:
    """Project a retained UTF-8 log atomically with bounded input and output.

    Malformed, linked, oversized or concurrently changed inputs remain intact
    for explicit recovery. No raw backup or temporary copy is created.
    """
    with open_evidence(path) as source:
        original = os.fstat(source.fileno())
        if original.st_size > MAX_LEGACY_LOG_BYTES:
            raise OSError("Task log exceeds the 16 MiB automatic migration limit")
        decoder = codecs.getincrementaldecoder("utf-8")("strict")
        projection = EvidenceStreamRedactor(policy)
        written = consumed = 0
        truncated = False
        with atomic_evidence(path, expected=original) as output:
            while chunk := source.read(4096):
                consumed += len(chunk)
                if consumed > MAX_LEGACY_LOG_BYTES:
                    raise OSError("Task log exceeds the 16 MiB automatic migration limit")
                safe = projection.feed(decoder.decode(chunk))
                if not truncated:
                    written, truncated = _bounded_write(output, safe, written)
            safe = projection.feed(decoder.decode(b"", final=True)) + projection.finish(interrupted=True)
            if not truncated:
                _, truncated = _bounded_write(output, safe, written)
            if not _unchanged(original, os.fstat(source.fileno())):
                raise OSError("Task evidence changed during migration")
            # Windows cannot replace a destination with its CRT reader open.
            source.close()
    return truncated


class TaskOutput:
    """Own an anonymous pipe and write only projected bytes to a private log.

    The subprocess receives the writer FD, not an asyncio pipe transport, so
    descendant writers cannot prevent observing its exit. The caller closes
    its writer after spawn and must await finish on every exit path.
    """

    def __init__(self, path: Path, policy: EvidenceRedactor) -> None:
        self.path = path
        self.policy = policy
        self.truncated = False
        self.error: str | None = None
        self.failure: asyncio.Future[str] = asyncio.get_running_loop().create_future()
        self._written = 0
        self._closing_deadline: float | None = None
        self._output: BinaryIO
        with _evidence_directory(path.parent) as directory_fd:
            descriptor = os.open(_entry(path, directory_fd), os.O_WRONLY | os.O_CREAT | os.O_EXCL
                                 | getattr(os, "O_NOFOLLOW", 0), 0o600, dir_fd=directory_fd)
        try:
            self._output = os.fdopen(descriptor, "wb", buffering=0)
        except BaseException:
            os.close(descriptor)
            raise
        self._reader = -1
        self.writer = -1
        try:
            self._reader, self.writer = os.pipe()
            if os.name != "nt":
                os.set_blocking(self._reader, False)
        except BaseException:
            if self._reader >= 0:
                with contextlib.suppress(OSError):
                    os.close(self._reader)
            self.close_writer()
            with contextlib.suppress(OSError):
                self._output.close()
            raise
        self.task = asyncio.create_task(self._drain(), name=f"henchman-task-output-{path.stem}")

    def close_writer(self) -> None:
        """Release the parent's writer while leaving the child's copy intact."""
        if self.writer >= 0:
            writer = self.writer
            self.writer = -1
            try:
                os.close(writer)
            except OSError as exc:
                self._fail(exc)

    def _write(self, text: str) -> None:
        """Write bounded projected UTF-8 and continue draining after truncation."""
        if not text or self.truncated:
            return
        self._written, self.truncated = _bounded_write(self._output, text, self._written)

    def _fail(self, error: Exception) -> None:
        detail = self.policy.text(str(error))
        message = self.policy.text(
            f"Could not capture task output: {type(error).__name__}: {detail}",
        )
        self.error = f"{self.error}\n{message}" if self.error else message
        if not self.failure.done():
            self.failure.set_result(self.error)

    async def _drain(self) -> None:
        decoder = codecs.getincrementaldecoder("utf-8")("replace")
        projection = EvidenceStreamRedactor(self.policy)
        try:
            loop = asyncio.get_running_loop()
            while self._closing_deadline is None or loop.time() < self._closing_deadline:
                chunk = pipe_chunk(self._reader)
                if chunk is None:
                    if self._closing_deadline is not None:
                        break
                    await asyncio.sleep(0.01)
                    continue
                if not chunk:
                    break
                self._write(projection.feed(decoder.decode(chunk)))
                await asyncio.sleep(0)
            self._write(projection.feed(decoder.decode(b"", final=True)))
            self._write(projection.finish(interrupted=True))
        except Exception as exc:
            self._fail(exc)
        finally:
            try:
                os.close(self._reader)
            except OSError as exc:
                self._fail(exc)
            try:
                self._output.close()
            except OSError as exc:
                self._fail(exc)

    async def finish(self) -> None:
        """Drain available bytes with a deadline and await all owned cleanup."""
        self.close_writer()
        self._closing_deadline = asyncio.get_running_loop().time() + _FINAL_DRAIN_SECONDS
        await self.task
        if not self.failure.done():
            self.failure.cancel()

    def append_diagnostic(self, text: str) -> None:
        """Append a projected diagnostic after capture closes, within its cap."""
        safe = self.policy.text(text)
        available = max(0, MAX_TASK_OUTPUT_BYTES - self._written)
        safe = safe.encode("utf-8")[:available].decode("utf-8", errors="ignore")
        append_evidence(self.path, safe.encode("utf-8"))
        self._written += len(safe.encode("utf-8"))
