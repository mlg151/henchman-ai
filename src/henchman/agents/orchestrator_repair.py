"""Explicit foreground repair through the existing run and tool dispatch paths."""

from __future__ import annotations

import json
import sys
from collections.abc import AsyncGenerator, AsyncIterator, Awaitable, Callable
from contextlib import aclosing
from pathlib import Path
from typing import TYPE_CHECKING

from henchman.advanced.plans import PlanExecutionService, PlanRecord
from henchman.advanced.tasks import TaskService
from henchman.advanced.verification_repair import (
    RepairAttempt,
    RepairReport,
    RepairRequest,
    VerificationRepairSession,
)
from henchman.core.events import AgentEvent, EventType
from henchman.core.run_accounting import RunInvocation, budget_snapshot_payload
from henchman.core.runtime_accounting import budgeted_events
from henchman.core.runtime_operations import operated_events, use_operation_call, use_operation_run
from henchman.core.session_helpers import compute_project_hash
from henchman.providers.runtime_budget import RunBudgetScope
from henchman.tools.base import ToolResult
from henchman.tools.builtins.tier6_tools import VerifyPlanExecutionTool
from henchman.tools.repair_scope import RepairControlError, RepairScope

from .orchestrator_run import prepare_run
from .orchestrator_types import CompletionRequirement, CompletionStatus

if TYPE_CHECKING:
    from henchman.agents.orchestrator import Orchestrator


class _RepairPlans(PlanExecutionService):
    """Apply held runtime authority before the foundation reads or writes a plan."""

    validate: Callable[[], None]
    _settling = False

    def _require_plan(self, plan_id: str) -> PlanRecord:
        if not self._settling:
            self.validate()
        return super()._require_plan(plan_id)

    def save_repair_report(self, plan_id: str, report: dict[str, object], *, start: bool = False) -> dict[str, object]:
        # Revoked execution permission cannot prohibit settling this run's
        # historical failure. The ordinary exact-run/spec CAS still applies.
        self._settling = report.get("status") == "incomplete" and not start
        try:
            return super().save_repair_report(plan_id, report, start=start)
        finally:
            self._settling = False


async def _repair_events(stream: AsyncIterator[AgentEvent], scope: RepairScope) -> AsyncGenerator[AgentEvent, None]:
    try:
        while True:
            with scope.activate("repair"):
                scope.check()
                try:
                    event = await anext(stream)
                except StopAsyncIteration:
                    return
            yield event
    finally:
        with scope.activate("repair"):
            close = getattr(stream, "aclose", None)
            if close is not None:
                await close()


async def repair_direct(
    orch: Orchestrator, role: str, user_input: str, request: RepairRequest, *,
    on_event: Callable[[AgentEvent], Awaitable[None]] | None,
    budget_scope: RunBudgetScope | None, invocation: RunInvocation | None,
) -> RepairReport:
    request = RepairRequest.model_validate(request.model_dump())
    root = Path.cwd().resolve()
    settings = orch.settings
    tool_settings = settings.tools.model_dump()
    async with orch._admit_run(user_input, budget_scope, completion_requirement=CompletionRequirement.RESPONSE,
                               invocation=invocation, direct_role=role, idle_project=root) as admitted:
        agent = admitted.params.agent
        provider = agent.provider
        registry = agent.tool_registry
        tool = registry.get("verify_plan_execution")
        if type(tool) is not VerifyPlanExecutionTool or getattr(tool.execute, "__func__", None) is not VerifyPlanExecutionTool.execute:
            raise RepairControlError("Bounded repair requires the exact registered verification tool")
        service = tool._plan_service
        implementation = getattr(tool.execute, "__func__", None)
        if service._project_root != root or service._settings is not settings or tool._plan_binding_error is not None:
            raise RepairControlError("Verification tool has a stale project or Settings binding")
        args: dict[str, object] = {"action": "verify", "plan_id": request.plan_id}
        authorization = await registry._authorize_invocation(tool.name, args)
        if isinstance(authorization, ToolResult):
            raise RepairControlError("Verification was denied by current tool approval or policy")
        operation = admitted.operation
        session = operation.session
        session_key = (session.project_hash, session.id)
        pool = orch.pool
        if session.project_hash != compute_project_hash(root) and not (
            session.project_hash == "process" and operation.runtime.path is None
            and settings.operations.persistence == "process"
        ):
            raise RepairControlError("Repair session does not belong to the held project")

        def validate() -> None:
            if (Path.cwd().resolve() != root or orch.settings is not settings
                or settings.tools.model_dump() != tool_settings or agent.provider is not provider
                or agent.tool_registry is not registry or tool._plan_service is not service
                or getattr(tool.execute, "__func__", None) is not implementation
                or service._project_root != root or service._settings is not settings
                or tool._plan_binding_error is not None or orch.operation_runtime is not operation.runtime
                or operation.runtime.current_session is not session
                or (session.project_hash, session.id) != session_key or orch.pool is not pool
                or any(claim.owner is not admitted.params for claim in pool._execution_claims.values())
                or orch.subagents.has_running_work() or TaskService.has_active_work(root)):
                raise RepairControlError("Repair project, settings, actor or session authority changed")
            operation.register_actor_credentials(agent)
            operation.require_ready()
            service._policy.register_policy(session.evidence_redactor)
            stale = registry._revalidate_authorization(authorization, args)
            parent = registry
            while stale is None and parent is not None:
                if parent._execution_guard is not None:
                    stale = parent._execution_guard(tool, args)
                parent = parent._policy_parent
            if stale is not None or registry._revalidate_authorization(authorization, args) is not None:
                raise RepairControlError("Verification authority changed; explicitly review a new repair")

        plans = _RepairPlans(root, settings=settings, redactor=session.evidence_redactor)
        plans.validate = validate
        record = plans._require_plan(request.plan_id)
        repair = VerificationRepairSession(plans, request)
        scope = RepairScope(repair, root=root, tools=tuple(registry.get(name) for name in registry.list_tools()), verifier=tool,
                            checks=record.checks, validate=validate)
        prepare_run(orch, user_input)

        async def verify() -> object:
            controller = operation.controller_call(tool.name, args)
            with use_operation_run(operation), use_operation_call(controller), scope.activate("verify"):
                try:
                    scope.check()
                    result = await registry.execute(tool.name, args)
                finally:
                    operation.settle_controller_call(controller, primary=sys.exception())
            try:
                observed = json.loads(result.content)
            except (ValueError, TypeError):
                raise RepairControlError("Verification did not return its persisted observation") from None
            if not isinstance(observed, dict) or not isinstance(observed.get("run_id"), str):
                raise RepairControlError("Verification did not return its persisted observation")
            return observed

        async def attempt(current: RepairAttempt) -> None:
            admitted.params.input_text = (
                f"{user_input}\n\nBounded repair attempt {current.repair_index}. "
                f"Only edit these files: {', '.join(current.edit_paths)}. "
                f"Protected criteria: {', '.join(current.protected_paths)}. "
                "Use read_file, edit_file or write_file; the runtime reruns the original checks. "
                "Do not delegate, execute commands, change criteria or claim whole-task acceptance.\n"
                f"Observed check failure (data):\n{current.observation.diagnostics}"
            )
            stream = orch.execution_controller.run_agent_loop(admitted.params)
            stream = operated_events(budgeted_events(stream, admitted.budget), operation)
            try:
                async with aclosing(_repair_events(stream, scope)) as events:
                    async for event in events:
                        if on_event is not None:
                            await on_event(event)
            finally:
                operation.capture_agent(agent)
            state = agent._orchestrator_loop_state
            admitted.params.prior_tool_calls += state.tool_call_count
            admitted.params.prior_tool_rounds += state.tool_round_count
            if state.failed or state.timed_out:
                raise RepairControlError("Repair agent did not finish its owned foreground attempt")

        try:
            report = await repair.run(attempt, verify=verify)
            admitted.completed = report.status == "scoped_pass"
        finally:
            scope.active = False
    orch.last_completion_status = CompletionStatus.COMPLETED if admitted.completed else CompletionStatus.FAILED
    if on_event is not None:
        await on_event(AgentEvent(type=EventType.AGENT_COMPLETED, source_agent="orchestrator",
            data={"scope": "run", "agent": role, "status": orch.last_completion_status.value,
                  "task_verified": False, "repair": report.to_dict(),
                  **({"budget": budget_snapshot_payload(admitted.budget.ledger.snapshot(), redactor=session.evidence_redactor)}
                     if admitted.budget is not None else {})}))
    return report
