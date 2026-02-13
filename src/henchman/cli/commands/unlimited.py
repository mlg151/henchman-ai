"""Unlimited command for bypassing loop protection."""

from henchman.cli.commands import Command, CommandContext

__all__ = ["UnlimitedCommand"]


class UnlimitedCommand(Command):
    """Toggle unlimited mode to bypass loop protection.

    When enabled, the agent will not enforce iteration limits on tool calls.
    Use with caution as this can lead to infinite loops.
    Use Ctrl+C to abort runaway execution.
    """

    @property
    def name(self) -> str:
        """Return the command name."""
        return "unlimited"

    @property
    def description(self) -> str:
        """Return a brief description."""
        return "Toggle unlimited mode (bypass loop protection)"

    @property
    def usage(self) -> str:
        """Return usage information."""
        return "/unlimited [on|off]"

    async def execute(self, ctx: CommandContext) -> None:
        """Execute the command.

        Args:
            ctx: The command context.
        """
        args = ctx.args

        # Get current state from agent
        agent = ctx.agent
        if agent is None:
            ctx.console.print("[red]Error: No agent available[/red]")
            return

        current_state = getattr(agent, "unlimited_mode", False)

        # Toggle or set explicitly
        if not args:
            # Toggle
            new_state = not current_state
        elif args[0].lower() in ("on", "true", "1", "yes"):
            new_state = True
        elif args[0].lower() in ("off", "false", "0", "no"):
            new_state = False
        else:
            ctx.console.print(f"[yellow]Usage: {self.usage}[/yellow]")
            return

        agent.unlimited_mode = new_state

        if new_state:
            ctx.console.print(
                "[bold yellow]⚠ Unlimited mode: ON[/bold yellow]\n"
                "[yellow]Loop protection disabled. Use Ctrl+C to abort runaway execution.[/yellow]"
            )
        else:
            ctx.console.print(
                "[bold green]✓ Unlimited mode: OFF[/bold green]\n"
                "[dim]Loop protection re-enabled.[/dim]"
            )
