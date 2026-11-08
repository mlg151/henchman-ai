"""Bind private child proposals to exact workers and parent review authority.

This internal coordinator does not yet route the dynamic subagent tool catalog.
The runner and its completion callback are trusted runtime components; neither
model-supplied labels nor persisted proposal IDs grant these capabilities.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from henchman.advanced.checkpoint_models import ReviewResult
from henchman.advanced.child_proposals import ChildProposalReview, ChildProposalService
from henchman.agents.workspace_ownership import (
    WorkspaceBinding,
    WorkspaceLease,
    WorkspaceOwnership,
    WorkspaceOwnershipError,
)
from henchman.utils.evidence_redaction import EvidenceRedactor

_ISSUER = object()


class ProposalHandle:
    """Opaque in-process child identity; copying or serialization grants nothing."""

    __slots__ = ()

    def __new__(cls, issuer: object) -> ProposalHandle:
        if issuer is not _ISSUER:
            raise TypeError("Proposal handles are issued by their runtime")
        return super().__new__(cls)

    def __copy__(self) -> ProposalHandle:
        raise TypeError("Proposal handles cannot be copied")

    def __deepcopy__(self, memo: dict[int, Any]) -> ProposalHandle:
        raise TypeError("Proposal handles cannot be copied")

    def __reduce__(self) -> Any:
        raise TypeError("Proposal handles cannot be serialized")


@dataclass
class _Entry:
    actor: object
    lease: WorkspaceLease
    proposal_id: str
    completed: Callable[[], bool]
    review: ChildProposalReview | None = None
    disposed: bool = False


class StagedWorkspace:
    """A child worker's explicit staged-file operations, never workspace publication."""

    def __init__(self, runtime: ProposalCoordinator, handle: ProposalHandle, actor: object) -> None:
        self._runtime = runtime
        self._handle = handle
        self._actor = actor

    def _service(self, path: str) -> tuple[ChildProposalService, _Entry]:
        entry = self._runtime._entry(self._handle)
        if entry.actor is not self._actor:
            raise WorkspaceOwnershipError("wrong_actor")
        self._runtime._ownership.require_write(entry.lease, self._actor, [path])
        service = self._runtime._service(
            lambda: self._runtime._ownership.require_write(entry.lease, self._actor, [path])
        )
        return service, entry

    def read(self, path: str) -> str | None:
        """Read the staged text for an owned path, or None for proposed absence."""
        service, entry = self._service(path)
        return service.read_staged(entry.proposal_id, path)

    def stage(self, path: str, content: str | None) -> None:
        """Stage a text replacement or deletion within the exact child lease."""
        service, entry = self._service(path)
        service.stage(entry.proposal_id, path, content)


class ProposalCoordinator:
    """Hold scopes until joined child work is reviewed, published or discarded."""

    def __init__(self, project_root: Path, *, session: object, generation: int,
                 parent: object, paths: Sequence[str],
                 current_binding: Callable[[], WorkspaceBinding],
                 redactor: EvidenceRedactor | None = None) -> None:
        self._root_path = project_root.absolute()
        self._redactor = redactor if redactor is not None else EvidenceRedactor()
        self._parent = parent
        self._ownership = WorkspaceOwnership(self._root_path, session=session, generation=generation,
                                              current_binding=current_binding)
        self._root = self._ownership.open_root(parent, paths=paths)
        self._entries: dict[ProposalHandle, _Entry] = {}

    def _service(self, guard: Callable[[], None]) -> ChildProposalService:
        return ChildProposalService(self._root_path, redactor=self._redactor, guard=guard)

    def _entry(self, handle: ProposalHandle) -> _Entry:
        if type(handle) is not ProposalHandle or handle not in self._entries:
            raise WorkspaceOwnershipError("unknown_handle")
        entry = self._entries[handle]
        if entry.disposed:
            raise WorkspaceOwnershipError("released")
        return entry

    def _parent_guard(self) -> None:
        self._ownership.require_current(self._root, self._parent)

    def reserve(self, child: object, *, paths: Sequence[str], completed: Callable[[], bool]) -> ProposalHandle:
        """Reserve nonoverlapping files and capture their current original state."""
        if not callable(completed):
            raise ValueError("A runtime completion check is required")
        if not paths:
            raise ValueError("A staged child requires explicit file paths")
        lease = self._ownership.reserve(self._root, self._parent, child, paths=paths)
        try:
            proposal_id = self._service(self._parent_guard).begin(paths)
        except BaseException as primary:
            try:
                self._ownership.abort_reservation(self._root, self._parent, lease)
            except BaseException as cleanup:
                primary.add_note(f"Reservation cleanup also failed: {type(cleanup).__name__}")
            raise
        handle = ProposalHandle(_ISSUER)
        self._entries[handle] = _Entry(child, lease, proposal_id, completed)
        return handle

    def bind(self, handle: ProposalHandle, worker: asyncio.Task[Any]) -> None:
        """Bind exactly one actual child task before it can use staged files."""
        entry = self._entry(handle)
        self._ownership.bind_worker(self._root, self._parent, entry.lease, worker)

    def abort(self, handle: ProposalHandle) -> None:
        """Release an unbound reservation after worker creation fails."""
        entry = self._entry(handle)

        def guard() -> None:
            self._parent_guard()
            if self._ownership.snapshot(entry.lease).state != "reserved":
                raise WorkspaceOwnershipError("already_bound")

        guard()
        self._service(guard).discard(entry.proposal_id)
        self._ownership.abort_reservation(self._root, self._parent, entry.lease)
        entry.disposed = True

    def workspace(self, handle: ProposalHandle, child: object) -> StagedWorkspace:
        """Return staged operations only to the bound actor and current worker."""
        entry = self._entry(handle)
        self._ownership.require_current(entry.lease, child)
        return StagedWorkspace(self, handle, child)

    def _review_guard(self, entry: _Entry) -> None:
        self._ownership.require_review(self._root, self._parent, entry.lease)
        if entry.completed() is not True:
            raise WorkspaceOwnershipError("unsuccessful")
        self._ownership.require_review(self._root, self._parent, entry.lease)

    def review(self, handle: ProposalHandle) -> ChildProposalReview:
        """Freeze joined successful work and return a parent-held exact review."""
        entry = self._entry(handle)
        self._review_guard(entry)
        if entry.review is None:
            service = self._service(lambda: self._review_guard(entry))
            service.seal(entry.proposal_id)
            entry.review = service.review(entry.proposal_id)
        return entry.review

    def publish(self, handle: ProposalHandle, review: ChildProposalReview) -> ReviewResult:
        """Publish only the exact review held by the live parent worker."""
        entry = self._entry(handle)
        self._review_guard(entry)
        if review is not entry.review or review is None:
            raise ValueError("The exact parent-held review is required")
        service = self._service(lambda: self._review_guard(entry))
        plan = service.prepare(entry.proposal_id, revision=review.revision, expected_review=review)
        result = service.apply(plan, expected_review=review)
        self._ownership.resolve(self._root, self._parent, entry.lease, disposition="reviewed")
        entry.disposed = True
        return result

    def discard(self, handle: ProposalHandle) -> None:
        """Discard settled child evidence before returning the file scope."""
        entry = self._entry(handle)

        def guard() -> None:
            self._ownership.require_discard(self._root, self._parent, entry.lease)

        guard()
        self._service(guard).discard(entry.proposal_id)
        self._ownership.resolve(self._root, self._parent, entry.lease, disposition="discarded")
        entry.disposed = True

    async def cancel_and_discard(self, handle: ProposalHandle) -> None:
        """Revoke and join the owned subtree before discarding its proposal."""
        entry = self._entry(handle)
        await self._ownership.cancel(self._root, self._parent, entry.lease)
        self.discard(handle)

    async def close(self) -> None:
        """Retire authority and join workers; retain unresolved proposal evidence."""
        await self._ownership.close()
