"""Process-owned chat turns and their shared provider accounting scopes."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import AsyncGenerator, AsyncIterator, Callable
from contextlib import aclosing, asynccontextmanager
from copy import deepcopy
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from fastapi import HTTPException

from henchman.config.schema import Settings
from henchman.core import Agent, AgentEvent, EventType
from henchman.core.run_accounting import budget_snapshot_payload, public_run_budget
from henchman.core.runtime_accounting import budgeted_events
from henchman.core.usage_summary import budget_evidence_redactor
from henchman.providers.base import Message, ToolCall
from henchman.providers.runtime_budget import RunBudgetScope, use_run_budget


@dataclass
class ApiChatRun:
    """One caller-owned conversation turn; display deletion never refunds it."""

    run_id: str
    authority: str
    agent: Agent
    scope: RunBudgetScope | None
    busy: bool = False
    completed: bool = False
    interrupted: bool = False
    history_hidden: bool = False
    pending_tools: tuple[str, ...] = ()
    settings: Settings | None = None

    def budget(self) -> dict[str, Any] | None:
        """Return the common aggregate without manufacturing absent usage."""
        return (
            budget_snapshot_payload(self.scope.ledger.snapshot(), redactor=budget_evidence_redactor(self))
            if self.scope is not None
            else None
        )


class ApiChatRuns:
    """Own independent agents and bounded completed-run retention in one process.

    Active, interrupted and tool-waiting runs are never evicted. Unknown IDs,
    including those from a previous process, cannot create replacement budgets.
    This is local authority, not a durable session or cross-worker registry.
    """

    def __init__(
        self,
        settings: Settings,
        agent_factory: Callable[[Settings], Agent],
        *,
        max_runs: int = 1024,
    ) -> None:
        if max_runs < 1:
            raise ValueError("max_runs must be positive")
        self.settings = settings
        self.agent_factory = agent_factory
        self.max_runs = max_runs
        self._runs: OrderedDict[str, ApiChatRun] = OrderedDict()

    def find(self, authority: str, run_id: str | None = None) -> ApiChatRun | None:
        """Resolve only this authority's run; never fall back for an explicit ID."""
        if run_id is not None:
            run = self._runs.get(run_id)
            if run is None or run.authority != authority:
                raise HTTPException(
                    404,
                    "Unknown chat run for this caller; process runs cannot be resumed after restart",
                )
            return run
        return next(
            (run for run in reversed(self._runs.values()) if run.authority == authority), None
        )

    def check_request(
        self,
        authority: str,
        messages: list[Message],
        *,
        run_id: str | None,
        system_prompt: str | None,
    ) -> ApiChatRun | None:
        """Validate identity and continuation before response headers or mutation."""
        if self.settings.usage.persistence == "durable":
            raise HTTPException(503, "durable_accounting_requires_api_session")
        if run_id is None:
            if not messages or messages[-1].role != "user":
                raise HTTPException(
                    422,
                    "New runs must end with a user message; tool results require the original run_id",
                )
            return None
        run = self.find(authority, run_id)
        assert run is not None
        if run.busy:
            raise HTTPException(409, "This chat run is already active")
        if run.completed or run.interrupted or not run.pending_tools:
            raise HTTPException(
                409, "This run is not awaiting tool results; its budget cannot be restarted"
            )
        if system_prompt is not None:
            raise HTTPException(422, "A continuation cannot replace its system prompt")
        results = self._tool_results(run, messages)
        ids = [message.tool_call_id for message in results]
        if len(ids) != len(set(ids)) or set(ids) != set(run.pending_tools):
            raise HTTPException(422, "Supply exactly one result for every pending tool_call_id")
        return run

    @staticmethod
    def _tool_results(run: ApiChatRun, messages: list[Message]) -> list[Message]:
        if messages and all(message.role == "tool" for message in messages):
            return messages
        # Full transcript compatibility is append-only. A client cannot replace
        # the authoritative conversation while retaining a consumed run ID.
        history = run.agent.messages
        if messages[: len(history)] != history:
            raise HTTPException(
                422, "Continuation history must match the retained run; send only new tool results"
            )
        results = messages[len(history) :]
        if not results or any(message.role != "tool" for message in results):
            raise HTTPException(422, "A continuation accepts only new tool results")
        return results

    def _make_room(self) -> None:
        while len(self._runs) >= self.max_runs:
            candidate = next(
                (key for key, run in self._runs.items() if run.completed and not run.busy), None
            )
            if candidate is None:
                raise HTTPException(
                    503, "Process chat registry is full; active runs cannot be evicted"
                )
            del self._runs[candidate]

    @asynccontextmanager
    async def execute(
        self,
        authority: str,
        messages: list[Message],
        *,
        run_id: str | None = None,
        system_prompt: str | None = None,
    ) -> AsyncIterator[tuple[ApiChatRun, AsyncIterator[AgentEvent]]]:
        """Claim before mutation and close the producer under its captured scope."""
        run = self.check_request(authority, messages, run_id=run_id, system_prompt=system_prompt)
        if run is None:
            self._make_room()
            captured = self.settings.model_copy(deep=True)
            agent = self.agent_factory(captured)
            # An ASGI request is a public root, never an inherited caller task.
            with use_run_budget(None):
                scope = public_run_budget(captured, agent.provider, None)
            run = ApiChatRun(
                scope.ledger.run_id if scope is not None else uuid4().hex, authority, agent, scope,
                settings=self.settings,
            )
            budget_evidence_redactor(run)
            self._runs[run.run_id] = run
            if system_prompt is not None:
                agent.system_prompt = system_prompt
            agent.messages = deepcopy(messages[:-1])
            if system_prompt is not None:
                agent.messages = [message for message in agent.messages if message.role != "system"]
                if system_prompt:
                    agent.messages.insert(0, Message("system", system_prompt))
            stream = agent.run(messages[-1].content or "")
        else:
            results = self._tool_results(run, messages)
            for message in results:
                run.agent.submit_tool_result(message.tool_call_id or "", message.content or "")
            run.pending_tools = ()
            stream = run.agent.continue_with_tool_results()
        run.busy = True
        run.history_hidden = False
        finished = False
        exhausted = False
        pending: list[str] = []

        async def events() -> AsyncGenerator[AgentEvent, None]:
            nonlocal finished, exhausted
            async with aclosing(budgeted_events(stream, run.scope)) as source:
                async for event in source:
                    if event.type == EventType.ERROR:
                        raise RuntimeError(str(event.data))
                    if event.type == EventType.TOOL_CALL_REQUEST and isinstance(
                        event.data, ToolCall
                    ):
                        pending.append(event.data.id)
                    if event.type == EventType.FINISHED:
                        finished = True
                    yield event
                exhausted = True

        try:
            async with aclosing(events()) as source:
                yield run, source
        finally:
            # FINISHED can precede the generator's final yield/cleanup. A close
            # before exhaustion must not turn unknown dispatch into completion.
            run.pending_tools = tuple(pending)
            run.completed = exhausted and finished and not pending
            run.interrupted = not (exhausted and finished)
            run.busy = False

    def history(self, authority: str, run_id: str | None) -> list[Message]:
        run = self.find(authority, run_id)
        if run is None or run.history_hidden:
            return []
        if run.busy:
            raise HTTPException(409, "This chat run is already active")
        return deepcopy(run.agent.messages)

    def hide_history(self, authority: str, run_id: str | None) -> None:
        run = self.find(authority, run_id)
        if run is not None:
            if run.busy:
                raise HTTPException(409, "This chat run is already active")
            run.history_hidden = True
