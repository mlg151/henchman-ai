"""Bounded, fresh repository observations; no persistent search backend."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from pathlib import Path

from henchman.rag.evidence import (
    EvidenceUnavailable,
    SourceSnapshot,
    WorkspaceBinding,
    WorkspaceSnapshot,
    read_source,
    repository_git_environment,
)
from henchman.tools.access_policy import check_repository_read_authorization
from henchman.tools.subprocess_utils import run_bounded_subprocess

MAX_FILES = 256
MAX_ENTRIES = 20_000
MAX_GIT_BYTES = 1024 * 1024
MAX_FILE_BYTES = 256 * 1024
MAX_SOURCE_BYTES = 4 * 1024 * 1024
TOTAL_SECONDS = 10.0


@dataclass
class RepositoryObservation:
    """One invocation's deadline, membership and exact source observations."""

    binding: WorkspaceBinding
    deadline: float
    workspace: WorkspaceSnapshot | None = None
    consumed: int = 0

    def check(self) -> None:
        check_repository_read_authorization()
        self.binding.check()
        if time.monotonic() >= self.deadline:
            raise EvidenceUnavailable("repository_deadline_exceeded")

    async def checkpoint(self) -> None:
        await asyncio.sleep(0)
        self.check()
        task = asyncio.current_task()
        if task is not None and task.cancelling():
            await asyncio.sleep(0)  # Preserve the original pending cancellation.

    async def git(self, *arguments: str, allowed: tuple[int, ...] = (0,)) -> tuple[int, str]:
        await self.checkpoint()
        try:
            result = await run_bounded_subprocess(
                ["git", "--literal-pathspecs", "-c", "core.fsmonitor=false", *arguments],
                cwd=self.binding.root,
                timeout=max(0.001, self.deadline - time.monotonic()),
                max_output_bytes=MAX_GIT_BYTES, env=repository_git_environment(),
            )
        except (OSError, TimeoutError) as exc:
            raise EvidenceUnavailable("repository_command_unavailable") from exc
        await self.checkpoint()
        if result.returncode not in allowed or result.stdout_truncated or result.stderr_truncated:
            raise EvidenceUnavailable("repository_enumeration_unavailable")
        try:
            return int(result.returncode), result.stdout.decode("utf-8")
        except UnicodeError as exc:
            raise EvidenceUnavailable("repository_path_encoding_unavailable") from exc

    async def revision(self) -> tuple[str | None, str | None]:
        code, value = await self.git("rev-parse", "--verify", "--quiet", "HEAD", allowed=(0, 1))
        branch_code, branch = await self.git("symbolic-ref", "--quiet", "HEAD", allowed=(0, 1))
        reference = branch.strip() if branch_code == 0 else None
        if code == 0:
            revision = value.strip()
            if len(revision) not in (40, 64) or any(c not in "0123456789abcdef" for c in revision):
                raise EvidenceUnavailable("repository_revision_invalid")
            return revision, reference
        if reference:
            exists, _ = await self.git("show-ref", "--verify", "--quiet", reference, allowed=(0, 1))
            if exists == 1:
                return None, reference
        raise EvidenceUnavailable("repository_revision_unavailable")

    async def start(self) -> WorkspaceSnapshot:
        self.check()
        if self.binding.git_identity is None:
            raise EvidenceUnavailable("repository_metadata_unbound")
        revision, reference = await self.revision()
        self.workspace = WorkspaceSnapshot(self.binding, self.binding.git_identity, revision, reference)
        return self.workspace

    async def candidates(self, target: Path) -> tuple[tuple[str, bool], ...]:
        """Bound all Git output before sorting; ignore rules apply to tracked files too."""
        groups: list[set[str]] = []
        entries = 0
        for arguments in (("--cached",), ("--others", "--exclude-standard"),
                          ("--cached", "--ignored", "--exclude-standard")):
            _, raw = await self.git("ls-files", "-z", *arguments)
            if raw and not raw.endswith("\0"):
                raise EvidenceUnavailable("repository_listing_malformed")
            values = raw.split("\0")[:-1] if raw else []
            entries += len(values)
            if entries > MAX_ENTRIES:
                raise EvidenceUnavailable("repository_entry_budget_exceeded")
            groups.append(set(values))
        tracked, untracked, ignored = groups
        selected: list[tuple[str, bool]] = []
        for index, path in enumerate(sorted((tracked | untracked) - ignored)):
            if index % 32 == 0:
                await self.checkpoint()
            candidate = self.binding.root / path
            if candidate.suffix != ".py" or not candidate.is_relative_to(target):
                continue
            # A nested repository is a separate authority even when the parent
            # index happens to contain its files.
            parents = candidate.relative_to(self.binding.root).parents
            if len(parents) > 64:
                raise EvidenceUnavailable("repository_path_depth_exceeded")
            if any((self.binding.root / parent / ".git").exists()
                   for parent in parents if str(parent) != "."):
                continue
            selected.append((path, path in tracked))
        return tuple(selected)

    def source(self, path: str, *, max_bytes: int = MAX_FILE_BYTES) -> SourceSnapshot:
        self.check()
        assert self.workspace is not None
        source = read_source(self.workspace, path, require_tracked=False,
                             max_bytes=min(max_bytes, MAX_SOURCE_BYTES - self.consumed),
                             byte_observer=self._charge_bytes)
        self.check()
        return source

    def _charge_bytes(self, count: int) -> None:
        # Even a failed decode/identity check consumed bytes from this budget.
        self.consumed += count

    async def verify(self, sources: list[SourceSnapshot], target: Path,
                     membership: tuple[tuple[str, bool], ...]) -> None:
        assert self.workspace is not None
        if await self.candidates(target) != membership:
            raise EvidenceUnavailable("repository_membership_changed")
        if await self.revision() != (self.workspace.revision, self.workspace.reference):
            raise EvidenceUnavailable("repository_revision_changed")
        self.consumed = 0
        for source in sources:
            await self.checkpoint()
            current = self.source(source.relative_path)
            if current.sha256 != source.sha256 or current.identity != source.identity:
                raise EvidenceUnavailable("source_changed_during_retrieval")
        await self.checkpoint()


def repository_target(binding: WorkspaceBinding, path: str) -> Path:
    """Resolve a literal model path inside the already captured physical root."""
    if not isinstance(path, str) or not path or len(path) > 4096 or "\0" in path:
        raise EvidenceUnavailable("repository_target_invalid")
    target = binding.root / path
    if ".." in target.parts or not target.is_relative_to(binding.root):
        raise EvidenceUnavailable("repository_target_outside_workspace")
    relative = target.relative_to(binding.root)
    if len(relative.parts) > 64:
        raise EvidenceUnavailable("repository_path_depth_exceeded")
    current = binding.root
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise EvidenceUnavailable("repository_target_symlink")
    if not target.exists() or target.resolve() != target:
        raise EvidenceUnavailable("repository_target_unavailable")
    return target
