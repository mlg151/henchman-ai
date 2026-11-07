"""Task-local operation correlation captured by actual tool dispatchers."""

from __future__ import annotations

from collections.abc import AsyncGenerator, AsyncIterator, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from dataclasses import dataclass
from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from henchman.core.operation_bindings import OperationBinding
    from henchman.core.operation_recovery import DispatchPermit, OperationRecord, OperationResult
    from henchman.core.session_operations import OperationRun
    from henchman.tools.base import ToolResult


@dataclass(frozen=True)
class OperationInvocation:
    run: OperationRun
    binding: OperationBinding

    def prepare(self, name: str, params: dict[str, object], effect: str) -> OperationRecord:
        return self.run.runtime.prepare(self, name, params, effect)

    def start(self) -> DispatchPermit | None:
        permit = self.run.journal.start(self.binding.operation_id)
        if permit is not None:
            self.run.runtime._inflight[self.binding.operation_id] = self
        return permit

    def complete(self, permit: DispatchPermit, result: OperationResult) -> OperationRecord:
        try:
            return self.run.journal.finish(permit, result)
        finally:
            self.run.runtime._inflight.pop(self.binding.operation_id, None)

    def cancel(self) -> None:
        try:
            self.run.journal.cancel(self.binding.operation_id)
        finally:
            self.run.runtime._inflight.pop(self.binding.operation_id, None)

    def cancel_after_error(self, primary: BaseException) -> None:
        from henchman.core.operation_recovery import OperationRecoveryError
        from henchman.core.run_budget import BudgetControlError
        from henchman.providers.continuation import ProviderContinuationError

        try:
            self.cancel()
        except OperationRecoveryError as cleanup:
            if isinstance(primary, (OperationRecoveryError, BudgetControlError, ProviderContinuationError)) or not isinstance(primary, Exception):
                primary.add_note(f"Operation cleanup also failed: {cleanup.reason}")
                return
            raise


_CALL: ContextVar[OperationInvocation | None] = ContextVar("operation_call", default=None)
_RUN: ContextVar[OperationRun | None] = ContextVar("operation_run", default=None)
_Event = TypeVar("_Event")


def current_operation_run() -> OperationRun | None:
    return _RUN.get()


async def operated_events(stream: AsyncIterator[_Event], run: OperationRun | None) -> AsyncGenerator[_Event, None]:
    """Activate only while advancing/closing; child tasks retain captured scope."""
    try:
        while True:
            token = _RUN.set(run)
            try:
                event = await anext(stream)
            except StopAsyncIteration:
                return
            finally:
                _RUN.reset(token)
            yield event
    finally:
        token = _RUN.set(run)
        try:
            close = getattr(stream, "aclose", None)
            if close is not None:
                await close()
        finally:
            _RUN.reset(token)


def current_operation_call() -> OperationInvocation | None:
    return _CALL.get()


def tool_result_from_operation(result: OperationResult, *, display: str | None = None) -> ToolResult:
    """Return a detached observed result, preserving typed null/omission evidence."""
    from henchman.tools.base import ToolResult

    return ToolResult(result.content, result.success, display=display, error=result.error,
                      content_blocks=deepcopy(result.content_blocks), structured_content=deepcopy(result.structured_content),
                      structured_content_present=result.structured_content_present, metadata=deepcopy(result.metadata))


@contextmanager
def use_operation_call(invocation: OperationInvocation | None) -> Iterator[None]:
    token = _CALL.set(invocation)
    try:
        yield
    finally:
        _CALL.reset(token)
