"""Control autonomous session goals from either interactive frontend."""

from __future__ import annotations

from henchman.cli.commands import Command, CommandContext
from henchman.core.goals import GoalService, save_goal_session
from henchman.core.run_budget import BudgetControlError
from henchman.core.workflow_state import WorkflowError


class GoalCommand(Command):
    """Set, inspect, pause, resume, complete, or clear the session goal."""

    @property
    def name(self) -> str:
        """Return the slash command name."""
        return "goal"

    @property
    def description(self) -> str:
        """Describe the user-visible goal behavior."""
        return "Work toward a persistent goal until completed or paused"

    @property
    def usage(self) -> str:
        """Show lifecycle controls and objective syntax."""
        return "/goal [<objective>|set <objective>|status|pause|resume [--accept-policy-change]|complete|clear|bind-plan <id>|unbind-plan <id>]"

    async def execute(self, ctx: CommandContext) -> None:
        """Update the goal; the interactive frontend schedules continuation."""
        from henchman.core.session_run_accounting import SessionRunAccounting

        if ctx.session is None:
            ctx.console.print("No active session. Goals require a session.")
            return
        service = GoalService()
        session = ctx.session
        args = ctx.args
        action = args[0].lower() if args else "status"
        controls = {"status", "pause", "resume", "complete", "clear"}
        explicit_control = action in controls or action in {"bind-plan", "unbind-plan"}

        def update() -> None:
            if action == "set":
                service.start(session, " ".join(args[1:]))
            elif explicit_control:
                if action == "resume":
                    if args[1:] not in ([], ["--accept-policy-change"]):
                        raise ValueError(self.usage)
                    service.resume(session, accept_policy_change=bool(args[1:]))
                    return
                if action in {"bind-plan", "unbind-plan"}:
                    if len(args) != 2 or session.workflow_runtime is None:
                        raise ValueError("Plan binding requires the workflow runtime and one plan ID")
                    method = session.workflow_runtime.bind_plan if action == "bind-plan" else session.workflow_runtime.unbind_plan
                    method(args[1])
                    return
                if len(args) > 1:
                    raise ValueError(self.usage)
                if action == "pause":
                    service.pause(session)
                elif action == "clear":
                    service.clear(session)
                elif action == "complete":
                    service.acknowledge(session)
            else:
                service.start(session, " ".join(args))

        try:
            orchestrator = getattr(ctx.repl, "orchestrator", None)
            accounting = getattr(orchestrator, "accounting_runtime", None)
            replace_goal = action == "set" or action == "clear" or not explicit_control
            if replace_goal and isinstance(accounting, SessionRunAccounting):
                accounting.apply_user_goal_transition(
                    session, update=update,
                    save=lambda: save_goal_session(ctx.session_manager, session),
                )
            else:
                update()
                if action != "status" or len(args) > 1:
                    save_goal_session(ctx.session_manager, session)
            goal = service.get(session)
            if goal is None:
                ctx.console.print("No goal is set. Use /goal <objective> to start.")
            else:
                source = f", completion source: {goal.completion_source}" if goal.completion_source else ""
                text = f"Goal ({goal.status}, revision {goal.revision}{source}): {goal.objective}"
                ctx.console.print(session.evidence_redactor.text(text), markup=False, highlight=False)
                if session.workflow_runtime is not None and session.workflow_runtime.report().goal_requires_resume:
                    ctx.console.print("Goal continuation is held; explicitly /goal resume after reviewing current policy.", markup=False)
        except (ValueError, BudgetControlError, WorkflowError) as exc:
            ctx.console.print(session.evidence_redactor.text(f"Goal error: {exc}"), markup=False, highlight=False)
