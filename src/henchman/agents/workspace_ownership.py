"""Runtime-only ownership of explicit files, without staging or publication.

This is a cooperative authority boundary, not a filesystem sandbox or a file
content CAS. Qualified backends must still enforce policy and compare original
bytes when publishing. No path, actor label, serialized record or inherited task
context grants ownership. The controller is confined to one process/event loop.
"""

from __future__ import annotations

import asyncio
import os
import stat
import threading
import unicodedata
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Literal

from henchman.agents.delegation_admission import join_worker

_ISSUER = object()
_Identity = tuple[int, int]
_Parents = tuple[_Identity, ...]
_Disposition = Literal["reviewed", "discarded"]
_Outcome = Literal["completed", "failed", "cancelled"]
_DEVICES = frozenset({"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"}
                     | {f"{prefix}{number}" for prefix in ("COM", "LPT") for number in range(1, 10)})


class WorkspaceOwnershipError(RuntimeError):
    """A fixed, non-retryable ownership refusal; never execution permission."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class WorkspaceLease:
    """Opaque identity whose authority exists only in its issuing controller."""

    __slots__ = ()

    def __new__(cls, issuer: object) -> WorkspaceLease:
        if issuer is not _ISSUER:
            raise TypeError("Workspace leases are issued by their runtime")
        return super().__new__(cls)

    def __copy__(self) -> WorkspaceLease:
        raise TypeError("Workspace leases cannot be copied")

    def __deepcopy__(self, memo: dict[int, Any]) -> WorkspaceLease:
        raise TypeError("Workspace leases cannot be copied")

    def __reduce__(self) -> Any:
        raise TypeError("Workspace leases cannot be serialized")


@dataclass(frozen=True)
class WorkspaceBinding:
    """Current runtime selection, compared with captured identities on every effect."""

    project_root: Path
    session: object
    generation: int


@dataclass(frozen=True)
class OwnershipSnapshot:
    """Advisory lifecycle evidence; contains no actor or execution capability."""

    paths: tuple[str, ...]
    state: Literal["reserved", "running", "settled", "released"]
    outcome: _Outcome | None
    revoked: bool
    disposition: _Disposition | None
    worker_joined: bool


@dataclass
class _Record:
    actor: object
    parent: WorkspaceLease | None
    paths: dict[str, _Parents]
    worker: asyncio.Task[Any] | None = None
    state: Literal["reserved", "running", "settled", "released"] = "reserved"
    outcome: _Outcome | None = None
    revoked: bool = False
    disposition: _Disposition | None = None
    settlement: asyncio.Task[None] | None = None


class WorkspaceOwnership:
    """Bounded, explicit ownership graph for one held runtime generation.

    Root and child scopes default to read-only. A reservation immediately removes
    its paths from the parent, then binds exactly one worker. Normal completion,
    cancellation and failure retain the transfer until explicit parent review or
    discard. Reviewing returns ownership only; it does not integrate any bytes or
    certify work. Failed/cancelled work can only be discarded in this foundation.

    Retirement permanently revokes this graph. ``close`` joins descendant workers
    but retains undisposed evidence; it neither regrants paths nor discards future
    proposal data. The runtime separately owns the root worker. Follow-ups require
    new handles after disposition. The node bound includes retained tombstones,
    so this controller never silently evicts stale-handle evidence.

    Scopes use portable NFC paths (at most 256 files, 64 KiB of names and 32
    components per path), rejecting case aliases and Windows device/trailing-dot
    forms on every platform. Parents must already exist. Observations do not pin
    future I/O: a qualified file backend must enforce its own no-follow boundary.
    """

    def __init__(self, project_root: Path, *, session: object, generation: int,
                 current_binding: Callable[[], WorkspaceBinding],
                 max_paths: int = 256, max_nodes: int = 256) -> None:
        if (type(generation) is not int or generation < 0
            or type(max_paths) is not int or not 1 <= max_paths <= 256
            or type(max_nodes) is not int or not 1 <= max_nodes <= 256):
            raise ValueError("Invalid workspace ownership bounds")
        self._valid_actor(session)
        self._session = session
        self._generation = generation
        self._current_binding = current_binding
        self._max_paths = max_paths
        self._max_nodes = max_nodes
        self._loop = asyncio.get_running_loop()
        self._creator = asyncio.current_task()
        self._process = os.getpid()
        self._thread = threading.get_ident()
        self._root = project_root.absolute()
        if self._root.resolve() != self._root:
            raise WorkspaceOwnershipError("nonphysical_project")
        self._project = tuple((path, self._directory(path)) for path in reversed((self._root, *self._root.parents)))
        self._records: dict[WorkspaceLease, _Record] = {}
        self._primary: WorkspaceLease | None = None
        self._retired = False
        self._closing: asyncio.Task[None] | None = None
        self._check()

    @staticmethod
    def _valid_actor(actor: object) -> None:
        if actor is None or isinstance(actor, (str, bytes, int, float, complex, list, tuple, dict, set, frozenset)):
            raise WorkspaceOwnershipError("invalid_actor")

    @staticmethod
    def _directory(path: Path) -> _Identity:
        try:
            info = path.lstat()
        except OSError:
            raise WorkspaceOwnershipError("directory_unavailable") from None
        if not stat.S_ISDIR(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise WorkspaceOwnershipError("nonphysical_directory")
        return info.st_dev, info.st_ino

    def _affinity(self) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            raise WorkspaceOwnershipError("wrong_runtime") from None
        if os.getpid() != self._process or threading.get_ident() != self._thread or loop is not self._loop:
            raise WorkspaceOwnershipError("wrong_runtime")

    def _check(self) -> None:
        self._affinity()
        if self._retired:
            raise WorkspaceOwnershipError("retired")
        try:
            binding = self._current_binding()
            if (type(binding) is not WorkspaceBinding or binding.session is not self._session
                or type(binding.generation) is not int or binding.generation != self._generation
                or binding.project_root != self._root):
                raise WorkspaceOwnershipError("binding_changed")
            if any(self._directory(path) != identity for path, identity in self._project):
                raise WorkspaceOwnershipError("project_changed")
        except BaseException:
            # Once the held binding cannot be established, restoring an old
            # selector/path does not revive this graph's earlier permission.
            self._retire()
            raise

    def _record(self, handle: WorkspaceLease, *, refresh: bool = True) -> _Record:
        if type(handle) is not WorkspaceLease or handle not in self._records:
            raise WorkspaceOwnershipError("unknown_handle")
        record = self._records[handle]
        if refresh and record.worker is not None and record.worker.done() and record.state == "running":
            self._worker_done(handle, record.worker)
        return record

    def _access(self, handle: WorkspaceLease, actor: object) -> _Record:
        self._check()
        record = self._record(handle)
        if record.actor is not actor:
            raise WorkspaceOwnershipError("wrong_actor")
        if record.state == "released":
            raise WorkspaceOwnershipError("released")
        if record.revoked:
            raise WorkspaceOwnershipError("revoked")
        if record.worker is None:
            raise WorkspaceOwnershipError("unbound")
        if record.worker is not asyncio.current_task():
            raise WorkspaceOwnershipError("wrong_worker")
        if record.worker.cancelling():
            raise WorkspaceOwnershipError("worker_cancelling")
        if record.state != "running":
            raise WorkspaceOwnershipError("settled")
        ancestor = record.parent
        while ancestor is not None:
            parent = self._record(ancestor)
            if (parent.revoked or parent.state != "running" or parent.worker is None
                or parent.worker.cancelling()):
                self._revoke(handle)
                raise WorkspaceOwnershipError("ancestor_unavailable")
            ancestor = parent.parent
        return record

    def _observe(self, name: str) -> _Parents:
        if (not isinstance(name, str) or not 1 <= len(name) <= 4096
            or any(ord(char) < 32 or ord(char) == 127 for char in name) or "\\" in name or ":" in name
            or unicodedata.normalize("NFC", name) != name):
            raise WorkspaceOwnershipError("invalid_path")
        path = PurePosixPath(name)
        if (path.is_absolute() or str(path) != name or name == "." or ".." in path.parts
            or len(path.parts) > 32
            or any(part.rstrip(" .") != part or part.split(".", 1)[0].upper() in _DEVICES for part in path.parts)):
            raise WorkspaceOwnershipError("invalid_path")
        if os.name == "nt" and (self._root / name).resolve() != self._root / name:
            raise WorkspaceOwnershipError("path_alias")
        parent = self._root
        identities = [self._directory(parent)]
        for component in path.parts[:-1]:
            parent /= component
            identities.append(self._directory(parent))
        try:
            info = (parent / path.name).lstat()
        except FileNotFoundError:
            return tuple(identities)
        except OSError:
            raise WorkspaceOwnershipError("file_unavailable") from None
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
            or getattr(info, "st_file_attributes", 0) & 0x400):
            raise WorkspaceOwnershipError("unsupported_file")
        return tuple(identities)

    def _paths(self, paths: Sequence[str]) -> dict[str, _Parents]:
        if not isinstance(paths, (list, tuple)) or len(paths) > self._max_paths:
            raise WorkspaceOwnershipError("scope_limit")
        result: dict[str, _Parents] = {}
        aliases: set[str] = set()
        for name in paths:
            parents = self._observe(name)
            if name.casefold() in aliases:
                raise WorkspaceOwnershipError("path_alias")
            aliases.add(name.casefold())
            result[name] = parents
        if sum(len(name.encode("utf-8")) for name in result) > 65536:
            raise WorkspaceOwnershipError("scope_limit")
        return result

    def _children(self, parent: WorkspaceLease) -> list[WorkspaceLease]:
        return [handle for handle, record in self._records.items()
                if record.parent is parent and record.state != "released"]

    def _subtree(self, handle: WorkspaceLease) -> list[WorkspaceLease]:
        values = [handle]
        for parent in values:
            values.extend(self._children(parent))
        return values

    def _issue(self, actor: object, parent: WorkspaceLease | None,
               paths: dict[str, _Parents]) -> WorkspaceLease:
        self._valid_actor(actor)
        if len(self._records) >= self._max_nodes:
            raise WorkspaceOwnershipError("node_limit")
        if any(record.actor is actor and record.state != "released" for record in self._records.values()):
            raise WorkspaceOwnershipError("actor_already_owned")
        handle = WorkspaceLease(_ISSUER)
        self._records[handle] = _Record(actor, parent, paths)
        return handle

    def open_root(self, actor: object, *, paths: Sequence[str] = ()) -> WorkspaceLease:
        """Bind an explicit primary scope to the calling runtime worker once."""
        self._check()
        if asyncio.current_task() is not self._creator:
            raise WorkspaceOwnershipError("wrong_worker")
        if self._primary is not None:
            raise WorkspaceOwnershipError("root_already_bound")
        captured = self._paths(paths)
        self._check()
        worker = asyncio.current_task()
        if worker is None:
            raise WorkspaceOwnershipError("wrong_worker")
        handle = self._issue(actor, None, captured)
        self._primary = handle
        record = self._records[handle]
        record.worker, record.state = worker, "running"
        worker.add_done_callback(lambda task: self._worker_done(handle, task))
        return handle

    def reserve(self, parent: WorkspaceLease, actor: object, child_actor: object,
                *, paths: Sequence[str] = ()) -> WorkspaceLease:
        """Transfer a subset without awaiting or queuing conflicting work."""
        source = self._access(parent, actor)
        captured = self._paths(paths)
        if not captured.keys() <= source.paths.keys():
            raise WorkspaceOwnershipError("outside_scope")
        if any(captured[name] != source.paths[name] for name in captured):
            raise WorkspaceOwnershipError("parent_changed")
        if any(captured.keys() & self._records[child].paths.keys() for child in self._children(parent)):
            raise WorkspaceOwnershipError("overlap")
        self._check()
        # Reuse immutable parent observations rather than copying long parent
        # chains at each nesting level; the root scope bounds total path bytes.
        return self._issue(child_actor, parent, {name: source.paths[name] for name in captured})

    def bind_worker(self, parent: WorkspaceLease, actor: object, child: WorkspaceLease,
                    worker: asyncio.Task[Any]) -> None:
        """Bind before the worker's first effect; failed creation must abort."""
        self._access(parent, actor)
        record = self._direct_child(parent, child)
        if record.worker is not None or record.state != "reserved":
            raise WorkspaceOwnershipError("already_bound")
        if (not isinstance(worker, asyncio.Task) or worker.get_loop() is not self._loop or worker.done()
            or any(other.worker is worker for other in self._records.values())):
            raise WorkspaceOwnershipError("invalid_worker")
        record.worker, record.state = worker, "running"
        worker.add_done_callback(lambda task: self._worker_done(child, task))

    def _direct_child(self, parent: WorkspaceLease, child: WorkspaceLease) -> _Record:
        record = self._record(child)
        if record.parent is not parent:
            raise WorkspaceOwnershipError("wrong_parent")
        return record

    def require_current(self, handle: WorkspaceLease, actor: object) -> None:
        """Validate a reader's live worker without granting any file access."""
        self._access(handle, actor)

    def require_review(self, parent: WorkspaceLease, actor: object, child: WorkspaceLease) -> None:
        """Validate parent authority over one joined child without releasing its scope."""
        self._access(parent, actor)
        record = self._direct_child(parent, child)
        if record.state != "settled" or record.worker is None or not record.worker.done():
            raise WorkspaceOwnershipError("not_settled")
        if self._children(child):
            raise WorkspaceOwnershipError("unresolved_descendants")
        if record.outcome != "completed" or record.revoked:
            raise WorkspaceOwnershipError("unsuccessful")

    def require_discard(self, parent: WorkspaceLease, actor: object, child: WorkspaceLease) -> None:
        """Validate that a direct child's entire subtree has settled before discard."""
        self._access(parent, actor)
        record = self._direct_child(parent, child)
        if record.state == "released" and record.disposition == "discarded":
            return
        if any(self._record(handle).state != "settled" for handle in self._subtree(child)):
            raise WorkspaceOwnershipError("not_settled")

    def require_write(self, handle: WorkspaceLease, actor: object, paths: Sequence[str]) -> None:
        """Validate one exact worker's targets; never imply unchanged file bytes."""
        record = self._access(handle, actor)
        captured = self._paths(paths)
        if not captured:
            raise WorkspaceOwnershipError("empty_mutation")
        if not captured.keys() <= record.paths.keys():
            raise WorkspaceOwnershipError("outside_scope")
        if any(captured[name] != record.paths[name] for name in captured):
            raise WorkspaceOwnershipError("parent_changed")
        if any(captured.keys() & self._records[child].paths.keys() for child in self._children(handle)):
            raise WorkspaceOwnershipError("transferred")
        self._check()

    def require_opaque_mutation(self, handle: WorkspaceLease, actor: object) -> None:
        """An explicit file lease never authorizes unknown shell/Python/MCP effects."""
        self._access(handle, actor)
        raise WorkspaceOwnershipError("opaque_mutation")

    def abort_reservation(self, parent: WorkspaceLease, actor: object, child: WorkspaceLease) -> None:
        """Release only a worker that was never bound, including factory failures."""
        self._access(parent, actor)
        record = self._direct_child(parent, child)
        if record.worker is not None:
            raise WorkspaceOwnershipError("already_bound")
        if record.state == "released" and record.disposition == "discarded":
            return
        if record.state != "reserved":
            raise WorkspaceOwnershipError("not_reserved")
        record.state, record.outcome, record.disposition = "released", "cancelled", "discarded"

    def _revoke(self, handle: WorkspaceLease) -> None:
        for current in self._subtree(handle):
            record = self._records[current]
            record.revoked = True
            if record.worker is None and record.state == "reserved":
                record.state, record.outcome = "settled", "cancelled"
            elif (current is not self._primary and record.worker is not None
                  and record.worker is not asyncio.current_task()
                  and not record.worker.done() and not record.worker.cancelling()):
                record.worker.cancel()

    def _worker_done(self, handle: WorkspaceLease, worker: asyncio.Task[Any]) -> None:
        record = self._records[handle]
        if record.worker is not worker or record.state != "running" or not worker.done():
            return
        record.state = "settled"
        record.outcome = "cancelled" if worker.cancelled() else "failed" if worker.exception() is not None else "completed"
        if handle is self._primary:
            self._retired = True
        for child in self._children(handle):
            self._revoke(child)

    async def _join(self, handles: Sequence[WorkspaceLease]) -> None:
        first: BaseException | None = None
        for handle in reversed(handles):
            record = self._records[handle]
            worker = record.worker
            if worker is None or handle is self._primary or record.state == "released":
                continue
            try:
                await join_worker(worker)
            except BaseException as error:
                if first is None:
                    first = error
            finally:
                self._worker_done(handle, worker)
        if first is not None:
            raise first

    async def cancel(self, parent: WorkspaceLease, actor: object, child: WorkspaceLease) -> None:
        """Revoke the subtree immediately; join it without returning its paths."""
        self._access(parent, actor)
        record = self._direct_child(parent, child)
        if record.state == "released":
            return
        self._revoke(child)
        if record.settlement is None:
            record.settlement = asyncio.create_task(self._join(self._subtree(child)))
        await join_worker(record.settlement)

    def resolve(self, parent: WorkspaceLease, actor: object, child: WorkspaceLease,
                *, disposition: _Disposition) -> None:
        """Return settled ownership explicitly; review is not file integration."""
        self._access(parent, actor)
        record = self._direct_child(parent, child)
        if disposition not in {"reviewed", "discarded"}:
            raise WorkspaceOwnershipError("invalid_disposition")
        if record.state == "released":
            if record.disposition != disposition:
                raise WorkspaceOwnershipError("disposition_changed")
            return
        handles = self._subtree(child)
        records = [self._record(handle) for handle in handles]
        if any(item.state != "settled" for item in records):
            raise WorkspaceOwnershipError("not_settled")
        if disposition == "reviewed":
            if len(handles) != 1:
                raise WorkspaceOwnershipError("unresolved_descendants")
            if record.outcome != "completed" or record.revoked:
                raise WorkspaceOwnershipError("unsuccessful")
        for item in records:
            item.state, item.disposition = "released", disposition

    def retire(self) -> None:
        """Permanently revoke admission and effects before asynchronous cleanup."""
        self._affinity()
        current = asyncio.current_task()
        if any(handle is not self._primary and record.worker is current for handle, record in self._records.items()):
            raise WorkspaceOwnershipError("descendant_lifecycle")
        self._retire()

    def _retire(self) -> None:
        """Internal revocation also serves failed binding checks inside a child."""
        self._retired = True
        if self._primary is not None:
            self._records[self._primary].revoked = True
            for child in self._children(self._primary):
                self._revoke(child)

    async def close(self) -> None:
        """Join owned descendants, preserving cancellation and undisposed evidence."""
        self.retire()
        if self._closing is None:
            self._closing = asyncio.create_task(self._join(tuple(self._records)))
        await join_worker(self._closing)

    def snapshot(self, handle: WorkspaceLease) -> OwnershipSnapshot:
        """Inspect held lifecycle evidence without granting or refreshing authority."""
        self._affinity()
        record = self._record(handle, refresh=False)
        state, outcome = record.state, record.outcome
        if state == "running" and record.worker is not None and record.worker.done():
            state = "settled"
            outcome = ("cancelled" if record.worker.cancelled() else
                       "failed" if record.worker.exception() is not None else "completed")
        return OwnershipSnapshot(tuple(record.paths), state, outcome,
                                 record.revoked or self._retired, record.disposition,
                                 record.worker is None or record.worker.done())
