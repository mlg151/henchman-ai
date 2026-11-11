"""User-only inspection, acknowledgement and one-attempt operation recovery."""

from __future__ import annotations

from rich.table import Table
from rich.text import Text

from henchman.cli.commands import Command, CommandContext
from henchman.core.operation_recovery import OperationRecoveryError
from henchman.core.run_budget import BudgetControlError
from henchman.core.runtime_operations import use_operation_call
from henchman.tools.base import ToolResult


class RecoveryCommand(Command):
    name = "recovery"
    description = "Inspect interrupted operations and explicitly resolve or retry one attempt"
    usage = "/recovery [status|abandon <id> <revision> <note>|complete <id> <revision> <note>|retry <id> <revision>]"

    async def execute(self, ctx: CommandContext) -> None:
        from henchman.core.session_operations import SessionRunOperations

        orchestrator = getattr(ctx.repl, "orchestrator", None)
        if orchestrator is None:
            orchestrator = getattr(getattr(ctx.repl, "core_context", None), "orchestrator", None)
        runtime = getattr(orchestrator, "operation_runtime", None)
        if not isinstance(runtime, SessionRunOperations):
            ctx.console.print("No operation recovery runtime is available.", markup=False)
            return
        session = runtime.current_session
        policy = session.evidence_redactor if session is not None else None

        def show(text: str) -> None:
            ctx.console.print(policy.text(text) if policy is not None else text, markup=False, highlight=False)

        args = ctx.args
        try:
            if not args or args == ["status"]:
                report = runtime.recovery_report()
                if report is None or not report.records:
                    show("No operation history is available.")
                    return
                table = Table("Operation ID", "Revision", "State", "Tool", "Agent")
                for record in report.records:
                    table.add_row(*(Text(policy.text(value) if policy is not None else value) for value in (
                        record.operation_id, str(record.revision), record.state, record.tool_name, record.context.agent_id)))
                ctx.console.print(table)
                for record in report.records:
                    if record.result is not None:
                        content = policy.text(record.result.content) if policy is not None else record.result.content
                        preview = content if len(content) <= 500 else content[:500] + " [preview truncated]"
                        show(f"Result {record.operation_id}: {preview}")
                    if record.resolution is not None:
                        show(f"Resolution {record.operation_id}: {record.resolution}; {record.resolution_note}")
                if report.blocking_operation_ids:
                    show("Uncertain effects block continuation. Inspect external state before explicitly completing, abandoning or retrying an operation.")
                return
            if len(args) < 3 or args[0] not in {"abandon", "complete", "retry"}:
                show(f"Usage: {self.usage}")
                return
            action, operation_id, raw_revision = args[:3]
            revision = int(raw_revision)
            if action == "retry":
                if len(args) != 3:
                    raise ValueError("Retry accepts only an operation ID and revision")
                registry = ctx.agent.tool_registry if ctx.agent is not None else ctx.tool_registry
                if registry is None:
                    raise OperationRecoveryError("current_tool_registry_unavailable")
                call = runtime.retry_request(operation_id, revision)
                if call.name == "delegate_task":
                    show("Delegation retry requires orchestration: resolve or abandon this operation after reviewing external state, then issue a new task.")
                    return
                authorized = await registry.authorize(call.name, call.arguments)
                if isinstance(authorized, ToolResult):
                    show(authorized.error or authorized.content)
                    return
                invocation = runtime.authorize_user_retry(operation_id, revision, call)
                with use_operation_call(invocation):
                    result = await registry.execute(call.name, call.arguments)
                runtime.finish_user_retry(invocation)
                show(f"Retry {invocation.binding.operation_id}: {'completed' if result.success else 'failed'}; {result.content}")
            else:
                note = " ".join(args[3:]).strip()
                if not note:
                    raise ValueError("Resolution requires a note describing the user's inspection or decision")
                record = runtime.resolve_user(operation_id, revision,
                                              decision="completed" if action == "complete" else "abandon", note=note)
                show(f"Operation {record.operation_id}: {record.resolution or record.state}")
            if ctx.agent is not None and runtime.current_session is not None:
                from henchman.cli.session_manager import _sync_messages_to_agent

                _sync_messages_to_agent(ctx.agent, runtime.current_session)
        except (ValueError, OperationRecoveryError, BudgetControlError) as exc:
            show(f"Recovery stopped: {exc}")
