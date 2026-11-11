"""Task and agent inspection and explicit owned-work interruption."""
from __future__ import annotations

from typing import Literal

from rich.text import Text

from henchman.cli.commands import Command, CommandContext
from henchman.cli.inspection_runtime import _current_policy
from henchman.cli.work_inspection import WorkInspection, _bounded
from henchman.utils.exception_evidence import exception_text


class WorkCommand(Command):
    """Inspect observed work or explicitly stop locally owned work."""

    @property
    def name(self) -> str:
        return "work"

    @property
    def description(self) -> str:
        return "Inspect tasks and agents or stop owned work by exact ID"

    @property
    def usage(self) -> str:
        return "/work [list] | /work inspect agent|task <exact-id> | /work stop agent|task <exact-id>"

    async def execute(self, ctx: CommandContext) -> None:
        listing = not ctx.args or ctx.args == ["list"]
        inspecting = len(ctx.args) == 3 and ctx.args[0] == "inspect" and ctx.args[1] in {"agent", "task"}
        stopping = len(ctx.args) == 3 and ctx.args[0] == "stop" and ctx.args[1] in {"task", "agent"}
        if not listing and not inspecting and not stopping:
            ctx.console.print(Text(f"Usage: {self.usage}"))
            return
        runtime = ctx.repl if ctx.repl is not None else ctx
        policy = _current_policy(runtime)
        inspection = None
        try:
            inspection = WorkInspection(runtime)
            if ctx.session is not None and ctx.session is not inspection.session:
                raise ValueError("Selected session changed; invoke /work again")
            if listing:
                rows, notice = await inspection.catalog()
                text = inspection.catalog_text(rows, notice)
            elif inspecting:
                kind: Literal["agent", "task"] = "agent" if ctx.args[1] == "agent" else "task"
                fields, interrupted = await inspection.inspect(kind, ctx.args[2])
                text = inspection.details(fields, interrupted=interrupted)
            elif ctx.args[1] == "task":
                result = await inspection.interrupt_current_task(
                    ctx.args[2],
                    on_requested=lambda: ctx.console.print(Text("Stop requested; checking owner, then waiting for cleanup.")),
                )
                text = inspection.details(
                    (("Task", result.task_id), ("State", result.status),
                     ("Outcome", "Stop request settled; refresh for retained evidence.")),
                    interrupted=result.status != "completed",
                )
            else:
                child = await inspection.interrupt_current_agent(
                    ctx.args[2],
                    on_requested=lambda: ctx.console.print(Text("Stop requested; waiting for child cleanup.")),
                )
                text = inspection.details(
                    (("Agent", child.conversation_id), ("State", child.status),
                     ("Outcome", "Cancelled; owned child cleanup settled." if child.cancelled else "Not cancelled; inspect current state.")),
                    interrupted=child.cancelled,
                )
            inspection.admit()
            ctx.console.print(Text(text))
        except Exception as error:
            policy.register_policy(inspection._refresh_policy() if inspection is not None else _current_policy(runtime))
            ctx.console.print(Text("Work inspection unavailable: " + _bounded(exception_text(error, policy))))
