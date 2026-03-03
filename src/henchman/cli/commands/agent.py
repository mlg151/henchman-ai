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
        if not self._check_multi_agent_initialized(ctx):
            return

        orchestrator = self._get_orchestrator(ctx)
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
                self._print_error(ctx, f"Please provide a message for agent '{role}'.")
                return

            await self._talk_to_agent_directly(ctx, role, message)

    def _check_multi_agent_initialized(self, ctx: CommandContext) -> bool:
        """Check if multi-agent system is initialized.

        Args:
            ctx: Command context.

        Returns:
            True if initialized, False otherwise.
        """
        if not ctx.repl or not hasattr(ctx.repl, "orchestrator"):
            ctx.console.print("[red]Multi-agent system not initialized.[/]")
            return False
        return True

    def _get_orchestrator(self, ctx: CommandContext) -> Orchestrator:
        """Get orchestrator from context.

        Args:
            ctx: Command context.

        Returns:
            Orchestrator instance.
        """
        return ctx.repl.orchestrator

    def _print_error(self, ctx: CommandContext, message: str) -> None:
        """Print error message.

        Args:
            ctx: Command context.
            message: Error message.
        """
        ctx.console.print(f"[red]{message}[/]")

    async def _talk_to_agent_directly(self, ctx: CommandContext, role: str, message: str) -> None:
        """Talk to agent directly.

        Args:
            ctx: Command context.
            role: Agent role.
            message: Message to send.
        """
        try:
            # We need to run this through the REPL's agent run logic
            # but target a specific agent.
            if hasattr(ctx.repl, "_run_agent_direct"):
                await ctx.repl._run_agent_direct(role, message)
            else:
                ctx.console.print(
                    "[red]Direct agent targeting not supported in this REPL version.[/]",
                )
        except Exception as e:
            ctx.console.print(f"[red]Error talking to agent '{role}': {e}[/]")

    def _list_agents(self, ctx: CommandContext, orchestrator: Orchestrator) -> None:
        """List all configured agents."""
        table = Table(title="Specialist Agents")
        table.add_column("Role", style="cyan")
        table.add_column("Name", style="green")
        table.add_column("Status", style="magenta")
        table.add_column("Tools", style="yellow")
        table_add_row = table.add_row

        pool = orchestrator.pool
        active_roles = [a.role for a in pool.list_active_agents()]

        for identity in pool.list_agents():
            status = "[bold green]Active[/]" if identity.role in active_roles else "[dim]Idle[/]"

            # Get tool count if configured
            config = pool.configs.get(identity.role)
            tools_count = len(config.tools) if config else 0

            table_add_row(identity.role, identity.name, status, str(tools_count))

        ctx.console.print(table)

    def _show_config(
        self, ctx: CommandContext, orchestrator: Orchestrator, role: str | None,
    ) -> None:
        """Show configuration for agent(s)."""
        console = ctx.console
        pool = orchestrator.pool
        if role:
            if role not in pool.configs:
                console.print(f"[red]Agent '{role}' not found.[/]")
                return
            config = pool.configs[role]
            config_name = config.name
            config_description = config.description
            config_tools = config.tools
            config_can_delegate_to = config.can_delegate_to
            console.print(f"\n[bold green]Configuration for {config_name} ({role})[/]")
            console.print(f"Description: {config_description}")
            console.print(f"Tools: {', '.join(config_tools)}")
            console.print(f"Can delegate to: {', '.join(config_can_delegate_to) or 'None'}")
            if config.provider:
                console.print(f"Provider: {config.provider}")
            if config.model:
                console.print(f"Model: {config.model}")
        else:
            for r, config in pool.configs.items():
                console.print(f"  [cyan]{r:15}[/] - {config.description}")
