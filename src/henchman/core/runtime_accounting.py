"""Bind accounting to agent work without exposing its scope across event yields."""

from __future__ import annotations

from collections.abc import AsyncGenerator, AsyncIterator
from typing import TYPE_CHECKING, TypeVar

from henchman.providers.runtime_budget import RunBudgetScope, current_run_budget, use_run_budget

if TYPE_CHECKING:
    from henchman.providers.base import ModelProvider

_Event = TypeVar("_Event")


def agent_budget_scope(agent_id: str | None) -> RunBudgetScope | None:
    """Capture the caller's run and attribute all preparation and transport work."""
    scope = current_run_budget()
    return scope.for_agent(agent_id) if scope is not None and agent_id is not None else scope


def continuation_budget_scope(previous: RunBudgetScope | None, agent_id: str | None) -> RunBudgetScope | None:
    """Keep the original run across tool-result continuation and reject rebinding."""
    from henchman.core.run_budget import BudgetAccountingError

    incoming = agent_budget_scope(agent_id)
    if previous is not None:
        if incoming is not None and incoming.ledger is not previous.ledger:
            raise BudgetAccountingError("Cannot continue an agent turn under a different run budget")
        return previous
    return incoming


def require_accounted_provider(provider: ModelProvider) -> None:
    """Fail before dispatch when the active run cannot account for this adapter."""
    from henchman.core.run_budget import BudgetAccountingError

    if current_run_budget() is not None and getattr(provider, "supports_run_budget", False) is not True:
        raise BudgetAccountingError("Provider does not support active run accounting")


async def budgeted_events(
    stream: AsyncIterator[_Event], scope: RunBudgetScope | None,
) -> AsyncGenerator[_Event, None]:
    """Activate only while advancing/closing, so consumers retain their context.

    A generator may be closed from a different task or under another run. No
    ContextVar token lives across a yield; cleanup still uses the captured run.
    Tasks created by the producer inherit this scope for their entire lifetime.
    """
    try:
        while True:
            with use_run_budget(scope):
                try:
                    event = await anext(stream)
                except StopAsyncIteration:
                    return
            yield event
    finally:
        with use_run_budget(scope):
            close = getattr(stream, "aclose", None)
            if close is not None:
                await close()
