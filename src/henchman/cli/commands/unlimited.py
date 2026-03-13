"""Unlimited command for bypassing loop protection."""

from __future__ import annotations

from henchman.cli.commands import Command, CommandContext

__all__ = ["UnlimitedCommand"]

_ON_VALUES = frozenset({"on", "true", "1", "yes"})
_OFF_VALUES = frozenset({"off", "false", "0", "no"})


def _resolve_new_state(args: list[str], current_state: bool) -> bool | None:
    """Determine the new unlimited-mode state from command arguments.

    Args:
        args: Parsed command arguments (empty = toggle).
        current_state: Current unlimited-mode value.

    Returns:
        New state, or None if the argument is unrecognised.
    """
    if not args:
        return not current_state
    token = args[0].lower()
    if token in _ON_VALUES:
        return True
    if token in _OFF_VALUES:
        return False
    return None


def _apply_unlimited_mode(ctx: CommandContext, enabled: bool) -> None:
    """Set unlimited_mode on the agent and print a status message.

    Args:
        ctx: Command context.
        enabled: New unlimited-mode value.
    """
    ctx.agent.unlimited_mode = enabled  # type: ignore[union-attr]
    if enabled:
        ctx.console.print(
            "[bold yellow]\u26a0 Unlimited mode: ON[/bold yellow]\n"
            "[yellow]Loop protection disabled. Use Ctrl+C to abort runaway execution.[/yellow]",
        )
    else:
        ctx.console.print(
            "[bold green]\u2713 Unlimited mode: OFF[/bold green]\n"
            "[dim]Loop protection re-enabled.[/dim]",
        )


class UnlimitedCommand(Command):
    """Toggle unlimited mode to bypass loop protection.

    When enabled, the agent will not enforce iteration limits on tool calls.
    Use with caution as this can lead to infinite loops.
    Use Ctrl+C to abort runaway execution.
    """

    @property
    def name(self: UnlimitedCommand) -> str:
        """Return the command name."""
        return "unlimited"

    @property
    def description(self: UnlimitedCommand) -> str:
        """Return a brief description."""
        return "Toggle unlimited mode (bypass loop protection)"

    @property
    def usage(self: UnlimitedCommand) -> str:
        """Return usage information."""
        return "/unlimited [on|off]"

    async def execute(self: UnlimitedCommand, ctx: CommandContext) -> None:
        """Execute the command.

        Args:
            ctx: The command context.

        Returns:
            None
        """
        if ctx.agent is None:
            ctx.console.print("[red]Error: No agent available[/red]")
            return

        current_state = getattr(ctx.agent, "unlimited_mode", False)
        new_state = _resolve_new_state(ctx.args, current_state)

        if new_state is None:
            ctx.console.print(f"[yellow]Usage: {self.usage}[/yellow]")
            return

        _apply_unlimited_mode(ctx, new_state)
