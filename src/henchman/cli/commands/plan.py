"""Plan mode command for Henchman-AI CLI.

This module provides the `/plan` command that toggles plan mode, which restricts
the agent to read-only operations for planning and architectural discussions
without modifying the codebase.
"""

from __future__ import annotations

from henchman.cli.commands import Command, CommandContext

PLAN_MODE_PROMPT = """
---
**PLAN MODE ACTIVE**
You are currently in PLAN MODE.
Your goal is to discuss, plan, and architect solutions without modifying the codebase.
You can read files and explore the project, but you cannot write files or
execute commands that modify state.
Focus on creating detailed implementation plans.
---
"""


def _toggle_plan_mode(ctx: CommandContext) -> bool:
    """Toggle plan mode on the active session and return the new state.

    Args:
        ctx: Command context.

    Returns:
        New plan-mode state (True = enabled).
    """
    new_mode = not ctx.session.plan_mode  # type: ignore[union-attr]
    ctx.session.plan_mode = new_mode  # type: ignore[union-attr]
    return new_mode


def apply_plan_mode(
    *,
    enabled: bool,
    session: object | None = None,
    tool_registry: object | None = None,
    agent: object | None = None,
) -> None:
    """Apply plan mode to the active session's tool registry and agent.

    Args:
        enabled: Whether plan mode should be enabled.
        session: Optional session to mark with plan_mode flag.
        tool_registry: The tool registry to set plan mode on.
        agent: The agent to update with plan mode prompt.
    """
    if tool_registry is not None:
        from henchman.tools.registry import ToolRegistry

        if isinstance(tool_registry, ToolRegistry):
            tool_registry.set_plan_mode(enabled=enabled)

    # Mark the session with the plan_mode flag if it supports it
    if session is not None and hasattr(session, "plan_mode"):
        session.plan_mode = enabled

    if agent is not None and hasattr(agent, "system_prompt"):
        system_prompt = agent.system_prompt
        if isinstance(system_prompt, str):
            if enabled and PLAN_MODE_PROMPT not in system_prompt:
                agent.system_prompt = system_prompt + PLAN_MODE_PROMPT
            elif not enabled:
                agent.system_prompt = system_prompt.replace(PLAN_MODE_PROMPT, "")


def _apply_plan_mode_to_tools(ctx: CommandContext, enabled: bool) -> None:
    """Apply plan-mode setting to the tool registry.

    Args:
        ctx: Command context.
        enabled: Whether plan mode should be enabled.
    """
    if ctx.tool_registry:
        ctx.tool_registry.set_plan_mode(enabled=enabled)


def _apply_plan_mode_to_agent(ctx: CommandContext, enabled: bool) -> None:
    """Append or remove the plan-mode system prompt on the agent.

    Args:
        ctx: Command context.
        enabled: Whether plan mode is being enabled.
    """
    if not ctx.agent:
        return
    if enabled:
        if PLAN_MODE_PROMPT not in ctx.agent.system_prompt:
            ctx.agent.system_prompt += PLAN_MODE_PROMPT
    else:
        ctx.agent.system_prompt = ctx.agent.system_prompt.replace(PLAN_MODE_PROMPT, "")


def _print_plan_mode_status(ctx: CommandContext, enabled: bool) -> None:
    """Print the new plan-mode status to the console.

    Args:
        ctx: Command context.
        enabled: Whether plan mode is now enabled.
    """
    state = "ENABLED" if enabled else "DISABLED"
    style = "bold green" if enabled else "bold yellow"
    ctx.console.print(f"[{style}]Plan Mode {state}[/]")
    if enabled:
        ctx.console.print("[dim]Write and Execute tools are now disabled.[/]")


class PlanCommand(Command):
    """Toggle Plan Mode (Read-Only)."""

    @property
    def name(self: PlanCommand) -> str:
        """Command name."""
        return "plan"

    @property
    def description(self: PlanCommand) -> str:
        """Command description."""
        return "Toggle Plan Mode (Read-Only)"

    @property
    def usage(self: PlanCommand) -> str:
        """Command usage."""
        return "/plan"

    async def execute(self: PlanCommand, ctx: CommandContext) -> None:
        """Execute the command.

        Args:
            ctx: Command context.

        Returns:
            None: Toggles plan mode (read-only mode) and returns nothing.
        """
        if not ctx.session:
            ctx.console.print("[yellow]No active session. Plan mode requires a session.[/]")
            return

        new_mode = _toggle_plan_mode(ctx)
        _apply_plan_mode_to_tools(ctx, new_mode)
        _apply_plan_mode_to_agent(ctx, new_mode)
        _print_plan_mode_status(ctx, new_mode)
