"""Control autonomous session goals from either interactive frontend."""

from __future__ import annotations

from henchman.cli.commands import Command, CommandContext
from henchman.core.goals import GoalService, save_goal_session
from henchman.core.run_budget import BudgetControlError


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
        return "/goal [<objective>|set <objective>|status|pause|resume|complete|clear]"

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

        def update() -> None:
            if action == "set":
                service.start(session, " ".join(args[1:]))
            elif len(args) <= 1 and action in controls:
                if action == "pause":
                    service.pause(session)
                elif action == "resume":
                    service.resume(session)
                elif action == "clear":
                    service.clear(session)
                elif action == "complete":
                    goal = service.get(session)
                    if goal is None:
                        raise ValueError("No goal is set")
                    if goal.status == "paused":
                        service.resume(session)
                    service.complete(session, goal_id=goal.id, summary="Completed by user")
            else:
                service.start(session, " ".join(args))

        try:
            orchestrator = getattr(ctx.repl, "orchestrator", None)
            accounting = getattr(orchestrator, "accounting_runtime", None)
            replace_goal = action == "set" or action == "clear" or not (len(args) <= 1 and action in controls)
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
                ctx.console.print(f"Goal ({goal.status}): {goal.objective}", markup=False)
        except (ValueError, BudgetControlError) as exc:
            ctx.console.print(f"Goal error: {exc}", markup=False)
