"""Fail-fast execution capacity shared by one orchestration runtime's descendants."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from typing import Any


class DelegationAdmissionError(RuntimeError):
    """An explicit non-retryable refusal, never an execution or budget success."""

    def __init__(self, code: str, *, limit: int, active: int) -> None:
        self.payload: dict[str, object] = {
            "code": code, "limit": limit, "active": active, "retryable": False,
        }
        super().__init__("Delegation capacity is unavailable; continue directly or explicitly try after owned work finishes."
                         if code == "delegation_capacity" else
                         "Delegation authority was retired; start fresh work in the current runtime.")


class DelegationLease:
    """One execution reservation; cached actors retain no execution capacity."""

    def __init__(self, controller: DelegationAdmission) -> None:
        self.controller = controller
        self.generation = controller.generation
        self.released = False
        self.claimed = False
        self.owner: asyncio.Task[Any] | None = None
        self.stream: AsyncGenerator[Any, None] | None = None

    def claim(self, controller: DelegationAdmission) -> None:
        controller.require(self.generation)
        if self.controller is not controller or self.released or self.claimed:
            raise controller.denial("delegation_retired")
        self.claimed = True

    def release(self) -> None:
        if not self.released:
            self.released = True
            self.controller._leases.discard(self)


class DelegationAdmission:
    """Synchronous reservations have no await or hidden capacity wait queue.

    Like the owning orchestrator, this controller is confined to its event loop.
    Retirement revokes authority before cleanup; capacity remains occupied until
    each execution has actually settled. The primary never reserves a slot.
    """

    def __init__(self, limit: int = 4) -> None:
        if type(limit) is not int or limit < 0:
            raise ValueError("Delegation capacity must be a nonnegative integer")
        self.limit = limit
        self.generation = 0
        self._leases: set[DelegationLease] = set()
        self._accepting = True
        self._closed = False
        self._settlement: asyncio.Task[None] | None = None

    @property
    def active(self) -> int:
        return len(self._leases)

    def denial(self, code: str) -> DelegationAdmissionError:
        return DelegationAdmissionError(code, limit=self.limit, active=self.active)

    def require(self, generation: int) -> None:
        if self._closed or not self._accepting or generation != self.generation:
            raise self.denial("delegation_retired")

    def reserve(self, *, generation: int | None = None) -> DelegationLease:
        self.require(self.generation if generation is None else generation)
        if self.active >= self.limit:
            raise self.denial("delegation_capacity")
        lease = DelegationLease(self)
        self._leases.add(lease)
        return lease

    def retire(self, *, permanent: bool = False) -> None:
        self.generation += 1
        self._accepting = False
        self._closed = self._closed or permanent

    def reopen(self) -> None:
        if self.active or self._closed:
            raise self.denial("delegation_retired")
        self._accepting = True

    async def settle(self) -> None:
        """Close suspended streams and join owned workers after revocation."""
        if self._accepting:
            raise RuntimeError("Delegation admission must retire before settlement")
        if self._settlement is None or self._settlement.done():
            self._settlement = asyncio.create_task(self._settle_owned(asyncio.current_task()))
        await join_worker(self._settlement)

    async def _settle_owned(self, current: asyncio.Task[Any] | None) -> None:
        tasks: set[asyncio.Task[Any]] = set()
        for lease in tuple(self._leases):
            if lease.stream is not None and not getattr(lease.stream, "ag_running", True):
                tasks.add(asyncio.create_task(lease.stream.aclose()))
            elif lease.owner is not None and lease.owner is not current and not lease.owner.done():
                if not lease.owner.cancelling():
                    lease.owner.cancel()
                tasks.add(lease.owner)
        first: BaseException | None = None
        for task in tasks:
            try:
                await join_worker(task)
            except BaseException as error:
                if first is None or isinstance(error, asyncio.CancelledError) and not isinstance(first, asyncio.CancelledError):
                    first = error
        if first is not None:
            raise first


async def join_worker(task: asyncio.Task[Any]) -> None:
    """Join already-cancelled work without forwarding a caller's next cancel."""
    cancellation: asyncio.CancelledError | None = None
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError as error:
            current = asyncio.current_task()
            if current is not None and current.cancelling() and cancellation is None:
                cancellation = error
        except BaseException:
            break
    # Retrieve cleanup failures even when cancellation remains primary.
    failure = None if task.cancelled() else task.exception()
    if cancellation is not None:
        if failure is not None:
            cancellation.add_note("Delegation cleanup also failed; original cancellation retained")
        raise cancellation
    if failure is not None:
        raise failure
