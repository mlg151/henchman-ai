"""Descriptor-scoped regular-file observations for checkpoint review.

This backend requires POSIX no-follow and directory-relative operations. It is
not an OS sandbox against an owner moving directories or writing open handles.
"""

from __future__ import annotations

import fnmatch
import hashlib
import os
import stat
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path, PurePosixPath

from henchman.advanced.checkpoint_models import CheckpointConflict, FileState
from henchman.utils.evidence_redaction import EvidenceRedactor

_EXCLUDED = frozenset({".git", ".henchman", ".Henchman", "node_modules", ".venv", "__pycache__"})


class WorkspaceFiles:
    def __init__(self, root: Path, redactor: EvidenceRedactor, max_file_bytes: int,
                 exclusions: tuple[str, ...]) -> None:
        self.root = root.absolute()
        if self.root.is_symlink() or not self.root.is_dir():
            raise ValueError("Checkpoint root must be a physical directory")
        metadata = self.root.stat()
        self.identity = (metadata.st_dev, metadata.st_ino)
        self.repository = self._repository_identity()
        self.redactor = redactor
        self.max_file_bytes = max_file_bytes
        self.exclusions = exclusions

    def check_root(self) -> None:
        metadata = self.root.lstat()
        if not stat.S_ISDIR(metadata.st_mode) or (metadata.st_dev, metadata.st_ino) != self.identity:
            raise CheckpointConflict(reason="Checkpoint project directory changed")
        if self._repository_identity() != self.repository:
            raise CheckpointConflict(reason="Checkpoint repository or worktree identity changed")

    def _git_entry(self) -> Path | None:
        for parent in (self.root, *self.root.parents):
            entry = parent / ".git"
            if entry.exists() or entry.is_symlink():
                return entry
        return None

    def _repository_identity(self) -> str | None:
        entry = self._git_entry()
        if entry is None:
            return None
        metadata = entry.lstat()
        if stat.S_ISDIR(metadata.st_mode):
            value = f"{entry}:{metadata.st_dev}:{metadata.st_ino}"
        elif stat.S_ISREG(metadata.st_mode) and metadata.st_size <= 4096:
            value = f"{entry}:{metadata.st_dev}:{metadata.st_ino}:{hashlib.sha256(entry.read_bytes()).hexdigest()}"
        else:
            raise ValueError("Unsupported checkpoint repository identity")
        return hashlib.sha256(value.encode()).hexdigest()

    def path(self, value: str) -> str:
        path = PurePosixPath(value)
        if not value or len(value) > 4096 or "\x00" in value or path.is_absolute() or ".." in path.parts or "\\" in value or path == PurePosixPath("."):
            raise ValueError("Checkpoint paths must be relative files without traversal")
        if self.redactor.text(value) != value:
            raise ValueError("Credential-bearing paths cannot be persisted in checkpoints")
        return path.as_posix()

    def excluded(self, value: str) -> bool:
        parts = PurePosixPath(value).parts
        if any(part in _EXCLUDED or part == ".env" or part.startswith(".env.") for part in parts):
            return True
        if any(fnmatch.fnmatchcase(value, pattern) for pattern in self.exclusions):
            return True
        if self.repository is not None:
            environment = {key: os.environ[key] for key in ("PATH", "SYSTEMROOT", "HOME", "USERPROFILE", "XDG_CONFIG_HOME")
                           if key in os.environ}
            try:
                # Use Git's native rules, including info/exclude and configured
                # global excludes. No index refresh, hooks, or inherited Git
                # configuration injection is needed for this read-only query.
                result = subprocess.run(
                    ["git", "-c", "core.fsmonitor=false", "-C", str(self.root),
                     "check-ignore", "--no-index", "-q", "--", value],
                    env=environment, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL, timeout=2, check=False,
                )
            except (OSError, subprocess.TimeoutExpired) as error:
                raise ValueError("Git ignore policy could not be evaluated; checkpoint capture denied") from error
            if result.returncode not in {0, 1}:
                raise ValueError("Git ignore policy could not be evaluated; checkpoint capture denied")
            return result.returncode == 0
        # Interpret ignore rules conservatively, including in non-Git projects.
        # Negation never re-includes excluded content. Unsupported rules cause
        # over-exclusion rather than permission to capture ignored material.
        for offset in range(len(parts)):
            directory = self.root.joinpath(*parts[:offset])
            if directory.is_symlink():
                return True
            ignore = directory / ".gitignore"
            if ignore.is_symlink():
                return True
            if not ignore.is_file():
                continue
            if ignore.stat().st_size > 65536:
                return True
            try:
                patterns = ignore.read_text(encoding="utf-8").splitlines()
            except (OSError, UnicodeError) as error:
                raise ValueError("Local ignore policy could not be read; checkpoint capture denied") from error
            remaining = "/".join(parts[offset:])
            for pattern in patterns:
                if not pattern or pattern.startswith(("#", "!")):
                    continue
                if "\\" in pattern:
                    return True
                pattern = pattern.strip().lstrip("/").rstrip("/")
                candidates = [remaining, *remaining.split("/")]
                candidates.extend("/".join(parts[offset:end]) for end in range(offset + 1, len(parts)))
                if any(fnmatch.fnmatchcase(candidate, pattern) for candidate in candidates):
                    return True
        return False

    @contextmanager
    def parent(self, value: str) -> Iterator[tuple[int, str, tuple[tuple[int, int], ...]]]:
        if os.name != "posix" or not hasattr(os, "O_NOFOLLOW") or os.open not in os.supports_dir_fd:
            raise ValueError("Checkpoint restore requires the supported POSIX descriptor backend")
        self.check_root()
        parts = PurePosixPath(self.path(value)).parts
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        directory = os.open(self.root, flags)
        identities = []
        try:
            for part in (None, *parts[:-1]):
                if part is not None:
                    child = os.open(part, flags, dir_fd=directory)
                    os.close(directory)
                    directory = child
                metadata = os.fstat(directory)
                if metadata.st_dev != self.identity[0]:
                    raise ValueError("Checkpoint paths across mounted filesystems are unsupported")
                identities.append((metadata.st_dev, metadata.st_ino))
            self.check_root()
            yield directory, parts[-1], tuple(identities)
        finally:
            os.close(directory)

    def state(self, value: str) -> FileState:
        value = self.path(value)
        if self.excluded(value):
            return FileState("excluded")
        try:
            with self.parent(value) as (directory, name, parents):
                try:
                    descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
                except FileNotFoundError:
                    return FileState("missing", parents=parents)
                try:
                    return self.read_descriptor(descriptor, parents)
                finally:
                    os.close(descriptor)
        except FileNotFoundError:
            return FileState("missing")
        except OSError:
            return FileState("unsupported")

    def read_descriptor(self, descriptor: int, parents: tuple[tuple[int, int], ...] = (),
                        *, allowed_links: tuple[int, ...] = (1,)) -> FileState:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink not in allowed_links or metadata.st_mode & 0o7000:
            return FileState("unsupported")
        if metadata.st_size > self.max_file_bytes:
            return FileState("oversized")
        content = bytearray()
        while len(content) <= self.max_file_bytes:
            chunk = os.read(descriptor, min(65536, self.max_file_bytes + 1 - len(content)))
            if not chunk:
                break
            content.extend(chunk)
        if len(content) > self.max_file_bytes:
            return FileState("oversized")
        after = os.fstat(descriptor)
        if (metadata.st_size, metadata.st_mtime_ns, metadata.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            raise CheckpointConflict(reason="File changed during checkpoint capture")
        try:
            text = content.decode("utf-8")
        except UnicodeError:
            return FileState("binary")
        if "\x00" in text:
            return FileState("binary")
        if self.redactor.text(text) != text:
            return FileState("secret")
        return FileState("text", bytes(content), stat.S_IMODE(metadata.st_mode), parents)
