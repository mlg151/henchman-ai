"""Agent command for multi-agent management."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.table import Table

from henchman.cli.commands import Command, CommandContext

if TYPE_CHECKING:
    from henchman.agents.orchestrator import Orchestrator


class AgentCommand(Command):
    """Manage and interact with specialist agents."""

    @property
    def name(self) -> str:
        """Command name."""
        return "agent"

    @property
    def description(self) -> str:
        """Command description."""
        return "List agents, show config, or talk to an agent directly"

    @property
    def usage(self) -> str:
        """Command usage."""
        return "/agent [list|config|role] [message]"

    async def execute(self, ctx: CommandContext) -> None:
        """Execute the agent command.

        Args:
            ctx: Command context.
        """
        if not ctx.repl or not hasattr(ctx.repl, "orchestrator"):
            ctx.console.print("[red]Multi-agent system not initialized.[/]")
            return

        orchestrator: Orchestrator = ctx.repl.orchestrator
        args = ctx.args

        if not args or args[0] == "list":
            self._list_agents(ctx, orchestrator)
        elif args[0] == "config":
            role = args[1] if len(args) > 1 else None
            self._show_config(ctx, orchestrator, role)
        else:
            # Talk to agent directly: /agent coder Fix this bug
            role = args[0]
            message = " ".join(args[1:])
            if not message:
                ctx.console.print(f"[red]Please provide a message for agent '{role}'.[/]")
                return

            try:
                # We need to run this through the REPL's agent run logic
                # but target a specific agent.
                if hasattr(ctx.repl, "_run_agent_direct"):
                    await ctx.repl._run_agent_direct(role, message)
                else:
                    ctx.console.print("[red]Direct agent targeting not supported in this REPL version.[/]")
            except Exception as e:
                ctx.console.print(f"[red]Error talking to agent '{role}': {e}[/]")

    def _list_agents(self, ctx: CommandContext, orchestrator: Orchestrator) -> None:
        """List all configured agents."""
        table = Table(title="Specialist Agents")
        table.add_column("Role", style="cyan")
        table.add_column("Name", style="green")
        table.add_column("Status", style="magenta")
        table.add_column("Tools", style="yellow")

        pool = orchestrator.pool
        active_roles = [a.role for a in pool.list_active_agents()]

        for identity in pool.list_agents():
            status = "[bold green]Active[/]" if identity.role in active_roles else "[dim]Idle[/]"

            # Get tool count if configured
            config = pool.configs.get(identity.role)
            tools_count = len(config.tools) if config else 0

            table.add_row(identity.role, identity.name, status, str(tools_count))

        ctx.console.print(table)

    def _show_config(self, ctx: CommandContext, orchestrator: Orchestrator, role: str | None) -> None:
        """Show configuration for agent(s)."""
        pool = orchestrator.pool
        if role:
            if role not in pool.configs:
                ctx.console.print(f"[red]Agent '{role}' not found.[/]")
                return
            config = pool.configs[role]
            ctx.console.print(f"\n[bold green]Configuration for {config.name} ({role})[/]")
            ctx.console.print(f"Description: {config.description}")
            ctx.console.print(f"Tools: {', '.join(config.tools)}")
            ctx.console.print(f"Can delegate to: {', '.join(config.can_delegate_to) or 'None'}")
            if config.provider:
                ctx.console.print(f"Provider: {config.provider}")
            if config.model:
                ctx.console.print(f"Model: {config.model}")
        else:
            for r, config in pool.configs.items():
                ctx.console.print(f"  [cyan]{r:15}[/] - {config.description}")
