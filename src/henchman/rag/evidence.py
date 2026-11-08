"""Bounded current-file observations for repository-scoped retrieval."""

from __future__ import annotations

import hashlib
import os
import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath

from henchman.rag.repo_id import compute_repository_id

EVIDENCE_VERSION = 1
MAX_TOP_K = 20
MAX_QUERY_CHARS = 2048
MAX_FILE_BYTES = 1024 * 1024
MAX_SOURCE_BYTES = 5 * 1024 * 1024
MAX_OUTPUT_BYTES = 32 * 1024


class EvidenceUnavailable(ValueError):
    """A cached claim cannot be qualified against the current workspace."""


def validate_query(query: str, top_k: int) -> None:
    """Reject invalid bounds before embedding or querying a store."""
    if not isinstance(query, str) or not query.strip() or len(query) > MAX_QUERY_CHARS:
        raise ValueError(f"query must contain 1..{MAX_QUERY_CHARS} characters")
    if type(top_k) is not int or not 1 <= top_k <= MAX_TOP_K:
        raise ValueError(f"top_k must be an integer between 1 and {MAX_TOP_K}")


# Git's repository-local variables (git rev-parse --local-env-vars), plus
# namespace/internal prefixes, must not redirect an explicitly bound worktree.
_REPOSITORY_GIT_VARIABLES = frozenset(
    {
        "GIT_ALTERNATE_OBJECT_DIRECTORIES",
        "GIT_CONFIG",
        "GIT_CONFIG_PARAMETERS",
        "GIT_CONFIG_COUNT",
        "GIT_OBJECT_DIRECTORY",
        "GIT_DIR",
        "GIT_WORK_TREE",
        "GIT_IMPLICIT_WORK_TREE",
        "GIT_GRAFT_FILE",
        "GIT_INDEX_FILE",
        "GIT_NO_REPLACE_OBJECTS",
        "GIT_REPLACE_REF_BASE",
        "GIT_PREFIX",
        "GIT_SHALLOW_FILE",
        "GIT_COMMON_DIR",
        "GIT_NAMESPACE",
        "GIT_INTERNAL_SUPER_PREFIX",
    }
)


def repository_git_environment() -> dict[str, str]:
    """Detach ambient repository overrides; retain ordinary Git/user configuration."""
    return {
        name: value
        for name, value in os.environ.items()
        if name.upper() not in _REPOSITORY_GIT_VARIABLES
        and not name.upper().startswith(("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_"))
    }


def _git(root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", "--literal-pathspecs", *arguments],
            cwd=root,
            env=repository_git_environment(),
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise EvidenceUnavailable("repository_command_unavailable") from exc


def _revision(root: Path) -> tuple[str | None, str | None]:
    revision = _git(root, "rev-parse", "--verify", "--quiet", "HEAD")
    branch = _git(root, "symbolic-ref", "--quiet", "HEAD")
    reference = branch.stdout.strip() if branch.returncode == 0 else None
    if revision.returncode == 0:
        value = revision.stdout.strip()
        if len(value) not in (40, 64) or any(char not in "0123456789abcdef" for char in value):
            raise EvidenceUnavailable("repository_revision_invalid")
        if branch.returncode not in (0, 1):
            raise EvidenceUnavailable("repository_revision_unavailable")
        return value, reference
    if reference and _git(root, "show-ref", "--verify", "--quiet", reference).returncode == 1:
        return None, reference  # An unborn branch still has a real tracked-file index.
    raise EvidenceUnavailable("repository_revision_unavailable")


def _git_identity(root: Path) -> tuple[object, ...]:
    entry = root / ".git"
    info = entry.lstat()
    if stat.S_ISDIR(info.st_mode):
        return info.st_dev, info.st_ino
    if not stat.S_ISREG(info.st_mode) or info.st_size > 4096:
        raise EvidenceUnavailable("repository_identity_unsupported")
    return info.st_dev, info.st_ino, hashlib.sha256(entry.read_bytes()).hexdigest()


@dataclass(frozen=True)
class WorkspaceBinding:
    """An explicit physical worktree authority, independent of branch names."""

    declared: Path
    root: Path
    identity: tuple[int, int]
    repository_id: str
    git_identity: tuple[object, ...] | None

    @classmethod
    def bind(cls, root: Path) -> WorkspaceBinding:
        declared = Path(root).absolute()
        resolved = declared.resolve(strict=True)
        info = resolved.stat()
        if not stat.S_ISDIR(info.st_mode):
            raise EvidenceUnavailable("repository_root_not_directory")
        git_identity = _git_identity(resolved) if (resolved / ".git").exists() else None
        return cls(
            declared,
            resolved,
            (info.st_dev, info.st_ino),
            compute_repository_id(resolved),
            git_identity,
        )

    def check(self) -> None:
        if self.declared.resolve(strict=True) != self.root:
            raise EvidenceUnavailable("repository_root_changed")
        info = self.root.stat()
        if (info.st_dev, info.st_ino) != self.identity or not stat.S_ISDIR(info.st_mode):
            raise EvidenceUnavailable("repository_root_changed")
        if self.git_identity is not None and _git_identity(self.root) != self.git_identity:
            raise EvidenceUnavailable("repository_identity_changed")

    def snapshot(self) -> WorkspaceSnapshot:
        self.check()
        if self.git_identity is None:
            raise EvidenceUnavailable("repository_metadata_unbound")
        identity = _git_identity(self.root)
        revision, reference = _revision(self.root)
        self.check()
        return WorkspaceSnapshot(self, identity, revision, reference)


@dataclass(frozen=True)
class WorkspaceSnapshot:
    """Repository identity and revision held through one retrieval publication."""

    binding: WorkspaceBinding
    git_identity: tuple[object, ...]
    revision: str | None
    reference: str | None

    def check(self) -> None:
        self.binding.check()
        if _git_identity(self.binding.root) != self.git_identity:
            raise EvidenceUnavailable("repository_identity_changed")
        if _revision(self.binding.root) != (self.revision, self.reference):
            raise EvidenceUnavailable("repository_revision_changed")


def _source_path(workspace: WorkspaceSnapshot, relative: str) -> Path:
    if (
        not isinstance(relative, str)
        or not relative
        or len(relative) > 4096
        or "\\" in relative
        or "\0" in relative
        or PureWindowsPath(relative).drive
    ):
        raise EvidenceUnavailable("source_path_invalid")
    parts = PurePosixPath(relative).parts
    if PurePosixPath(relative).is_absolute() or ".." in parts or ".git" in parts:
        raise EvidenceUnavailable("source_path_outside_repository")
    current = workspace.binding.root
    workspace.binding.check()
    for part in parts:
        current = current / part
        if current.is_symlink():
            raise EvidenceUnavailable("source_symlink_unavailable")
    if not current.resolve(strict=True).is_relative_to(workspace.binding.root):
        raise EvidenceUnavailable("source_path_outside_repository")
    tracked = _git(workspace.binding.root, "ls-files", "--error-unmatch", "--", relative)
    if tracked.returncode != 0:
        raise EvidenceUnavailable("source_not_tracked")
    return current


def _file_identity(info: os.stat_result) -> tuple[int, ...]:
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns, info.st_nlink


@dataclass(frozen=True)
class SourceSnapshot:
    """Exact bounded source bytes, decoded without changing their digest."""

    relative_path: str
    sha256: str
    text: str
    size: int
    identity: tuple[int, ...]

    def check(self, workspace: WorkspaceSnapshot) -> None:
        current = read_source(workspace, self.relative_path)
        if current.identity != self.identity or current.sha256 != self.sha256:
            raise EvidenceUnavailable("source_changed_during_retrieval")


def read_source(
    workspace: WorkspaceSnapshot,
    relative: str,
    *,
    max_bytes: int = MAX_FILE_BYTES,
) -> SourceSnapshot:
    """Read only a tracked regular source, checking path and descriptor identities."""
    path = _source_path(workspace, relative)
    before = path.stat()
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
        raise EvidenceUnavailable("source_type_unavailable")
    limit = min(MAX_FILE_BYTES, max_bytes)
    if limit < 0 or before.st_size > limit:
        raise EvidenceUnavailable("source_byte_budget_exceeded")
    descriptor = os.open(
        path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    )
    with os.fdopen(descriptor, "rb") as stream:
        opened = os.fstat(stream.fileno())
        if not stat.S_ISREG(opened.st_mode) or _file_identity(opened) != _file_identity(before):
            raise EvidenceUnavailable("source_changed_during_read")
        raw = stream.read(limit + 1)
        after = os.fstat(stream.fileno())
    if len(raw) > limit:
        raise EvidenceUnavailable("source_byte_budget_exceeded")
    if _file_identity(after) != _file_identity(before) or _file_identity(
        _source_path(workspace, relative).stat()
    ) != _file_identity(after):
        raise EvidenceUnavailable("source_changed_during_read")
    try:
        text = raw.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
    except UnicodeError as exc:
        raise EvidenceUnavailable("source_encoding_unavailable") from exc
    return SourceSnapshot(
        relative, hashlib.sha256(raw).hexdigest(), text, len(raw), _file_identity(after)
    )
