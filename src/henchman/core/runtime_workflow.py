"""Task-local input correlation; this context never grants dispatch permission."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from henchman.core.session_data import Session
    from henchman.core.session_workflow import SessionWorkflow, WorkflowDispatch

_input: ContextVar[tuple[SessionWorkflow, WorkflowDispatch] | None] = ContextVar("henchman_workflow_input", default=None)


@contextmanager
def use_workflow_input(runtime: SessionWorkflow, dispatch: WorkflowDispatch) -> Iterator[None]:
    """Capture original correlation for children, restoring callers on exit.

    Late children may add evidence after frontend settlement. They retain only
    correlation, never queue eligibility or permission to repeat the input.
    """
    token = _input.set((runtime, dispatch))
    try:
        yield
    finally:
        _input.reset(token)


def correlate_workflow(session: Session, *, budget_run_id: str | None = None,
                       operation_run_id: str | None = None, operation_id: str | None = None) -> None:
    """Commit evidence before a run/operation effect; storage failures propagate."""
    context = _input.get()
    if context is not None:
        runtime, dispatch = context
        runtime.correlate(dispatch, session, budget_run_id=budget_run_id,
                          operation_run_id=operation_run_id, operation_id=operation_id)
