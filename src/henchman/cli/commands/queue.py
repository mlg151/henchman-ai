"""User-only inspection and revision-checked disposition of accepted input."""

from __future__ import annotations

from rich.table import Table
from rich.text import Text

from henchman.cli.commands import Command, CommandContext
from henchman.core.workflow_state import WorkflowError


class QueueCommand(Command):
    name = "queue"
    description = "Inspect accepted inputs and explicitly send, edit, move, drop or abandon one"
    usage = "/queue [status|send <id> <revision>|drop <id> <revision>|edit <id> <revision> <text>|move <id> <revision> <position>|abandon <id> <revision> <note>]"

    async def execute(self, ctx: CommandContext) -> None:
        session = ctx.session
        runtime = session.workflow_runtime if session is not None else None
        if runtime is None or session is None:
            ctx.console.print("No workflow runtime is available.", markup=False)
            return
        policy = session.evidence_redactor

        def show(text: str) -> None:
            ctx.console.print(policy.text(text), markup=False, highlight=False)

        try:
            args = ctx.args
            if not args or args == ["status"]:
                report = runtime.report()
                table = Table("Input ID", "Revision", "State", "Kind", "Preview")
                for item in sorted(report.state.inputs, key=lambda item: item.order):
                    preview = policy.text(item.preview)
                    if len(preview) > 500:
                        preview = preview[:500] + " [preview truncated]"
                    state = item.state + (f" ({item.resolution})" if item.resolution else "")
                    table.add_row(*(Text(policy.text(value)) for value in (item.id, str(item.revision), state, item.kind, preview)))
                ctx.console.print(table)
                show(f"Queue persistence: {report.persistence}. Restored and edited inputs require explicit send; move positions start at 0 among queued inputs.")
                if report.blocking_input_ids:
                    show("Uncertain input blocks new turns. Inspect effects and /recovery separately before explicitly abandoning the input; abandon never retries it.")
                if report.failure_reason:
                    show(f"Workflow blocked: {report.failure_reason}")
                return
            if len(args) < 3:
                raise ValueError(self.usage)
            action, input_id, revision = args[0], args[1], int(args[2])
            if action in {"send", "drop"} and len(args) == 3:
                item = runtime.send(input_id, revision) if action == "send" else runtime.drop(input_id, revision)
            elif action == "move" and len(args) == 4:
                item = runtime.move(input_id, revision, int(args[3]))
            elif action in {"edit", "abandon"} and len(args) > 3:
                text = " ".join(args[3:])
                if ctx.raw_input is not None:
                    parts = ctx.raw_input.split(maxsplit=4)
                    if len(parts) == 5 and parts[:4] == ["/queue", action, input_id, args[2]]:
                        text = parts[4]
                item = runtime.edit(input_id, revision, text) if action == "edit" else runtime.abandon(input_id, revision, text)
            else:
                raise ValueError(self.usage)
            show(f"Input {item.id}, revision {item.revision}: {item.state}; action {action} recorded.")
        except (ValueError, WorkflowError) as exc:
            show(f"Queue stopped: {exc}")
