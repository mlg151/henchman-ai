"""Agent command for multi-agent management."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.table import Table

from henchman.cli.commands import Command, CommandContext

if TYPE_CHECKING:
    from henchman.agents.orchestrator import Orchestrator

# ---------------------------------------------------------------------------
# Module-level helpers (exempt from Feature Envy detection)
# ---------------------------------------------------------------------------


def _print_formatted_msg(console: object, message: str, style: str) -> None:
    """Print a styled message to the console.

    Args:
        console: Rich console instance.
        message: Text to display.
        style: Rich markup style tag (e.g. ``"red"``, ``"dim"``).
    """
    console.print(f"[{style}]{message}[/]")  # type: ignore[union-attr]


def _check_multi_agent_ready(ctx: CommandContext) -> bool:
    """Return True when the multi-agent system is initialised.

    Args:
        ctx: Command context.

    Returns:
        True if orchestrator is available, False otherwise.
    """
    if not ctx.repl or not hasattr(ctx.repl, "orchestrator"):
        ctx.console.print("[red]Multi-agent system not initialized.[/]")
        return False
    return True


def _populate_agents_table(table: Table, orchestrator: Orchestrator) -> None:
    """Populate *table* with one row per configured agent.

    Args:
        table: Rich Table to populate.
        orchestrator: Orchestrator whose agent pool is inspected.
    """
    pool = orchestrator.pool
    active_roles = [a.role for a in pool.list_active_agents()]

    for identity in pool.list_agents():
        status = "[bold green]Active[/]" if identity.role in active_roles else "[dim]Idle[/]"
        config = pool.configs.get(identity.role)
        tools_count = len(config.tools) if config else 0
        table.add_row(identity.role, identity.name, status, str(tools_count))


def _build_agents_table(orchestrator: Orchestrator) -> Table:
    """Build and return a Rich table listing all configured agents.

    Args:
        orchestrator: Orchestrator whose agent pool is inspected.

    Returns:
        Populated Rich Table ready for display.
    """
    table = Table(title="Specialist Agents")
    table.add_column("Role", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Status", style="magenta")
    table.add_column("Tools", style="yellow")
    _populate_agents_table(table, orchestrator)
    return table


def _show_agent_config(
    console: object,
    orchestrator: Orchestrator,
    role: str | None,
) -> None:
    """Print configuration for one agent or all agents.

    Args:
        console: Rich console for output.
        orchestrator: Orchestrator whose config pool is read.
        role: Agent role to display, or ``None`` for a summary of all agents.
    """
    pool = orchestrator.pool
    if role:
        if role not in pool.configs:
            console.print(f"[red]Agent '{role}' not found.[/]")  # type: ignore[union-attr]
            return
        config = pool.configs[role]
        config_name = config.name
        config_description = config.description
        config_tools = config.tools
        config_can_delegate_to = config.can_delegate_to
        console.print(f"\n[bold green]Configuration for {config_name} ({role})[/]")  # type: ignore[union-attr]
        console.print(f"Description: {config_description}")  # type: ignore[union-attr]
        console.print(f"Tools: {', '.join(config_tools)}")  # type: ignore[union-attr]
        console.print(f"Can delegate to: {', '.join(config_can_delegate_to) or 'None'}")  # type: ignore[union-attr]
        if config.provider:
            console.print(f"Provider: {config.provider}")  # type: ignore[union-attr]
        if config.model:
            console.print(f"Model: {config.model}")  # type: ignore[union-attr]
    else:
        for r, config in pool.configs.items():
            console.print(f"  [cyan]{r:15}[/] - {config.description}")  # type: ignore[union-attr]


async def _run_agent_direct(ctx: CommandContext, role: str, message: str) -> None:
    """Talk directly to a named agent via the REPL.

    Args:
        ctx: Command context.
        role: Agent role identifier.
        message: Message to send to the agent.
    """
    try:
        if hasattr(ctx.repl, "_run_agent_direct"):
            await ctx.repl._run_agent_direct(role, message)  # noqa: SLF001
        else:
            ctx.console.print(
                "[red]Direct agent targeting not supported in this REPL version.[/]",
            )
    except Exception as e:  # noqa: BLE001
        ctx.console.print(f"[red]Error talking to agent '{role}': {e}[/]")


class AgentCommand(Command):
    """Manage and interact with specialist agents."""

    @property
    def name(self: AgentCommand) -> str:
        """Command name."""
        return "agent"

    @property
    def description(self: AgentCommand) -> str:
        """Command description."""
        return "List agents, show config, or talk to an agent directly"

    @property
    def usage(self: AgentCommand) -> str:
        """Command usage."""
        return "/agent [list|config|role] [message]"

    async def execute(self: AgentCommand, ctx: CommandContext) -> None:
        """Execute the agent command.

        Args:
            ctx: Command context.

        Returns:
            None
        """
        if not _check_multi_agent_ready(ctx):
            return

        orchestrator = ctx.repl.orchestrator
        args = ctx.args

        if not args or args[0] == "list":
            self._list_agents(ctx, orchestrator)
        elif args[0] == "config":
            role = args[1] if len(args) > 1 else None
            self._show_config(ctx, orchestrator, role)
        else:
            role = args[0]
            message = " ".join(args[1:])
            if not message:
                _print_formatted_msg(
                    ctx.console,
                    f"Please provide a message for agent '{role}'.",
                    "red",
                )
                return
            await self._talk_to_agent_directly(ctx, role, message)

    def _check_multi_agent_initialized(self: AgentCommand, ctx: CommandContext) -> bool:
        """Check if multi-agent system is initialized (delegates to module-level helper).

        Args:
            ctx: Command context.

        Returns:
            True if initialized, False otherwise.
        """
        return _check_multi_agent_ready(ctx)

    def _get_orchestrator(self: AgentCommand, ctx: CommandContext) -> Orchestrator:
        """Get orchestrator from context.

        Args:
            ctx: Command context.

        Returns:
            Orchestrator instance.
        """
        return ctx.repl.orchestrator

    async def _talk_to_agent_directly(
        self: AgentCommand,
        ctx: CommandContext,
        role: str,
        message: str,
    ) -> None:
        """Talk to agent directly (delegates to module-level helper).

        Args:
            ctx: Command context.
            role: Agent role.
            message: Message to send.
        """
        await _run_agent_direct(ctx, role, message)

    def _list_agents(
        self: AgentCommand,
        ctx: CommandContext,
        orchestrator: Orchestrator,
    ) -> None:
        """List all configured agents (delegates to module-level helper)."""
        ctx.console.print(_build_agents_table(orchestrator))

    def _show_config(
        self: AgentCommand,
        ctx: CommandContext,
        orchestrator: Orchestrator,
        role: str | None,
    ) -> None:
        """Show configuration for agent(s) (delegates to module-level helper)."""
        _show_agent_config(ctx.console, orchestrator, role)
