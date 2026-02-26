"""Team command for multi-agent orchestration management."""

from __future__ import annotations

from typing import TYPE_CHECKING

from henchman.cli.commands import Command, CommandContext

if TYPE_CHECKING:
    from henchman.agents.orchestrator import Orchestrator


class TeamCommand(Command):
    """Overview and management of the agent team."""

    @property
    def name(self) -> str:
        """Command name."""
        return "team"

    @property
    def description(self) -> str:
        """Command description."""
        return "Show team status or reset all agents"

    @property
    def usage(self) -> str:
        """Command usage."""
        return "/team [status|reset]"

    async def execute(self, ctx: CommandContext) -> None:
        """Execute the team command.

        Args:
            ctx: Command context.
        """
        if not ctx.repl or not hasattr(ctx.repl, "orchestrator") or not ctx.repl.orchestrator:
            ctx.console.print("[red]Multi-agent system not initialized.[/]")
            return

        orchestrator: Orchestrator = ctx.repl.orchestrator
        args = ctx.args

        if not args or args[0] == "status":
            self._show_status(ctx, orchestrator)
        elif args[0] == "reset":
            orchestrator.pool.reset_all()
            orchestrator.tech_lead.clear_history()
            ctx.console.print("[green]All agent histories have been reset.[/]")
        else:
            ctx.console.print(f"[red]Unknown team subcommand: {args[0]}[/]")

    def _show_status(self, ctx: CommandContext, orchestrator: Orchestrator) -> None:
        """Show detailed team status."""
        ctx.console.print("\n[bold blue]Team Status[/]\n")

        pool = orchestrator.pool
        active = pool.list_active_agents()

        ctx.console.print(f"Active Agents: [bold green]{len(active)}[/] / {len(pool.configs)}")
        for agent in active:
            ctx.console.print(f"  - [cyan]{agent.name}[/] ([dim]{agent.role}[/])")

        if orchestrator.shared_context:
            ctx.console.print("\n[bold yellow]Recent Shared Context Decisions:[/]")
            for item in orchestrator.shared_context[-3:]:
                ctx.console.print(
                    f"  [dim]{item['timestamp']}[/] [[bold cyan]{item['agent']}[/]]: {item['summary'][:100]}..."
                )
