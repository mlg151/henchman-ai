"""Control autonomous session goals from either interactive frontend."""

from __future__ import annotations

from henchman.cli.commands import Command, CommandContext
from henchman.core.goals import GoalService, save_goal_session


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
        if ctx.session is None:
            ctx.console.print("No active session. Goals require a session.")
            return
        service = GoalService()
        args = ctx.args
        action = args[0].lower() if args else "status"
        try:
            if action == "set":
                service.start(ctx.session, " ".join(args[1:]))
            elif len(args) <= 1 and action in {"status", "pause", "resume", "complete", "clear"}:
                if action == "pause":
                    service.pause(ctx.session)
                elif action == "resume":
                    service.resume(ctx.session)
                elif action == "clear":
                    service.clear(ctx.session)
                elif action == "complete":
                    goal = service.get(ctx.session)
                    if goal is None:
                        raise ValueError("No goal is set")
                    if goal.status == "paused":
                        service.resume(ctx.session)
                    service.complete(ctx.session, goal_id=goal.id, summary="Completed by user")
            else:
                service.start(ctx.session, " ".join(args))
            if action != "status" or len(args) > 1:
                save_goal_session(ctx.session_manager, ctx.session)
            goal = service.get(ctx.session)
            if goal is None:
                ctx.console.print("No goal is set. Use /goal <objective> to start.")
            else:
                ctx.console.print(f"Goal ({goal.status}): {goal.objective}", markup=False)
        except ValueError as exc:
            ctx.console.print(f"Goal error: {exc}", markup=False)
