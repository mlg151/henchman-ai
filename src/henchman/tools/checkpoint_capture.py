"""Operation-scoped content capture around deterministic mutation transactions."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, TypeVar

from henchman.advanced.checkpoint_models import CheckpointOperation
from henchman.advanced.checkpoints import CheckpointService
from henchman.tools.base import Tool, ToolKind, ToolResult

if TYPE_CHECKING:
    from henchman.core.runtime_operations import OperationInvocation

_T = TypeVar("_T")
_CURRENT: ContextVar[MutationCheckpoint | None] = ContextVar("mutation_checkpoint", default=None)


class CheckpointCaptureError(RuntimeError):
    """A promised capture could not be completed; mutation evidence is incomplete."""


async def _joined(function: Callable[[], _T]) -> _T:
    """Join bounded filesystem work even through repeated cancellation."""
    worker = asyncio.create_task(asyncio.to_thread(function))
    interrupted: asyncio.CancelledError | None = None
    while not worker.done():
        try:
            await asyncio.shield(worker)
        except asyncio.CancelledError as error:
            if interrupted is None:
                interrupted = error
        except BaseException:
            # Retrieve below so a later worker error cannot replace the
            # caller's original cancellation after cleanup has been joined.
            if not worker.done():
                raise
    try:
        value = worker.result()
    except BaseException:
        if interrupted is not None:
            interrupted.add_note("Checkpoint filesystem work also failed after cancellation")
            raise interrupted from None
        raise
    if interrupted is not None:
        raise interrupted
    return value


class MutationCheckpoint:
    """One advisory capture, bound to an already correlated tool invocation.

    Declared paths do not grant access. Restricted registries never use this
    unmediated storage backend. Unknown effects and outside-project targets are
    explicitly unavailable instead of being inferred from workspace changes.
    """

    def __init__(self, operation: OperationInvocation | None, tool: Tool, params: dict[str, object],
                 restricted: Callable[[], bool]) -> None:
        self.operation = operation
        self.tool = tool
        self.root = Path.cwd().absolute()
        self.restricted = restricted
        self.paths: tuple[Path, ...] | None = None
        self.report: dict[str, object] | None = None
        self.service: CheckpointService | None = None
        self.checkpoint_id: str | None = None
        self.dispatched = False
        self.claimed = False
        self.finished = False
        self._discarding = False
        self._eligible = False
        if operation is None or tool.execution_kind(params) not in {ToolKind.WRITE, ToolKind.EXECUTE}:
            return
        paths = tool.checkpoint_paths(params)
        if paths is None:
            self._unavailable("Tool effects have no deterministic file scope")
            return
        if not isinstance(paths, tuple) or any(not isinstance(path, str) or not path for path in paths):
            raise CheckpointCaptureError("Tool declared an invalid checkpoint file scope")
        # Declarations use the tool's own path semantics. In particular, patch
        # and generated-test targets treat '~' literally while write/edit
        # declarations expand it just as their execution helpers do.
        targets = tuple(sorted({Path(os.path.abspath(path)) for path in paths}))
        if len(targets) > 256:
            raise CheckpointCaptureError("Declared checkpoint scope exceeds the 256-file bound")
        self.paths = targets
        if restricted():
            self._unavailable("Checkpoint storage is unavailable under restricted tool policy")
            return
        if any(not path.is_relative_to(self.root) for path in targets):
            self._unavailable("Declared mutation targets are outside the active project")
            return
        self._eligible = True

    def _unavailable(self, reason: str) -> None:
        self.report = {"status": "unavailable", "reason": reason}

    async def begin(self) -> None:
        """Capture before dispatch; callers must revalidate authorization afterwards."""
        if not self._eligible or not self.paths or self.operation is None:
            return
        if self.restricted():
            self._unavailable("Checkpoint storage is unavailable under restricted tool policy")
            return

        def capture() -> None:
            assert self.operation is not None and self.paths is not None
            self.check_access()
            context = self.operation.binding.context
            operation = CheckpointOperation(self.operation.binding.operation_id, context.run_id, context.agent_id, self.tool.name)
            self.service = CheckpointService(self.root, redactor=self.operation.run.session.evidence_redactor,
                                             _capture_guard=self._check_capture_access)
            record = self.service.begin([path.relative_to(self.root).as_posix() for path in self.paths],
                                        actor=context.agent_id, operation=operation)
            self.checkpoint_id = record.checkpoint_id

        try:
            await _joined(capture)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            raise CheckpointCaptureError("Before checkpoint capture failed; tool was not dispatched") from error

    def check_access(self) -> None:
        """Stop newly restricted unmediated work at its next admission boundary."""
        if self.restricted():
            raise CheckpointCaptureError("Checkpoint and formatter access became restricted")

    def _check_capture_access(self) -> None:
        if not self._discarding:
            self.check_access()

    async def finish(self, primary: BaseException | None = None) -> None:
        """Complete after formatting or discard a capture whose body never ran."""
        if self.finished:
            return
        self.finished = True
        if self.service is None or self.checkpoint_id is None:
            return
        service, identity = self.service, self.checkpoint_id

        def capture() -> None:
            if not self.dispatched:
                # Joined cleanup may remove our own before-only record even
                # after policy tightened. It captures no new workspace bytes.
                self._discarding = True
                try:
                    service.discard(identity)
                finally:
                    self._discarding = False
                return
            service.complete(identity)
            review = service.review(identity)
            self.report = {"status": "captured", "checkpoint_id": identity,
                           "restorable": all(file.restorable for file in review.files),
                           "non_restorable": {file.path: {"before": file.before.status, "after": file.after.status}
                                              for file in review.files if not file.restorable}}

        try:
            if self.dispatched and self.restricted():
                raise CheckpointCaptureError("After capture is unavailable because tool policy became restricted")
            await _joined(capture)
        except BaseException as error:
            if not isinstance(error, asyncio.CancelledError):
                self.report = {"status": "incomplete", "checkpoint_id": identity,
                               "reason": "Checkpoint capture did not complete; inspect or discard the inactive capture"}
            if primary is not None:
                primary.add_note("Checkpoint finalization also failed or was interrupted; inspect its correlated capture")
                return
            if isinstance(error, asyncio.CancelledError):
                raise
            raise CheckpointCaptureError("After checkpoint capture failed; tool effects may already exist") from error

    def project(self, result: ToolResult) -> ToolResult:
        """Attach advisory status without replacing raw tool payloads or success."""
        if self.report is None:
            return result
        if result.metadata is not None and "henchman.checkpoint" in result.metadata:
            # Tool metadata is opaque and caller-owned. Do not overwrite a
            # colliding key, stringify its value, or treat it as our authority.
            status = self.report["status"]
            identity = self.report.get("checkpoint_id")
            notice = f"Checkpoint: {status}" + (f" ({identity})" if identity else "")
            return replace(result, content=f"{result.content}\n{notice}")
        return replace(result, metadata={**(result.metadata or {}), "henchman.checkpoint": self.report})


def current_checkpoint() -> MutationCheckpoint | None:
    return _CURRENT.get()


@contextmanager
def use_checkpoint(capture: MutationCheckpoint) -> Iterator[None]:
    token = _CURRENT.set(capture)
    try:
        yield
    finally:
        _CURRENT.reset(token)
