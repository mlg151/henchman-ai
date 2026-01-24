from henchman.cli.commands import Command, CommandContext

PLAN_MODE_PROMPT = """
---
**PLAN MODE ACTIVE**
You are currently in PLAN MODE.
Your goal is to discuss, plan, and architect solutions without modifying the codebase.
You can read files and explore the project, but you cannot write files or execute commands that modify state.
Focus on creating detailed implementation plans.
---
"""

class PlanCommand(Command):
    """Toggle Plan Mode (Read-Only)."""

    @property
    def name(self) -> str:
        """Command name."""
        return "plan"

    @property
    def description(self) -> str:
        """Command description."""
        return "Toggle Plan Mode (Read-Only)"

    @property
    def usage(self) -> str:
        """Command usage."""
        return "/plan"

    async def execute(self, ctx: CommandContext) -> None:
        """Execute the command.

        Args:
            ctx: Command context.
        """
        if not ctx.session:
            ctx.console.print("[yellow]No active session. Plan mode requires a session.[/]")
            return

        # Toggle mode
        new_mode = not ctx.session.plan_mode
        ctx.session.plan_mode = new_mode

        # Apply to ToolRegistry
        if ctx.tool_registry:
            ctx.tool_registry.set_plan_mode(new_mode)

        # Apply to Agent System Prompt
        if ctx.agent:
            if new_mode:
                # Store original prompt if not already stored?
                # Actually, Repl config has the base prompt.
                # But Agent instance might have modified it?
                # For simplicity, we append to current if enabling,
                # or reset to base + append if we tracked base.
                # Since we don't track base in Agent, we rely on Repl re-init or just append.
                # If we toggle ON -> OFF -> ON, we might duplicate.
                # So we should check if prompt is already there.

                if PLAN_MODE_PROMPT not in ctx.agent.system_prompt:
                    ctx.agent.system_prompt += PLAN_MODE_PROMPT
            else:
                # Remove prompt
                ctx.agent.system_prompt = ctx.agent.system_prompt.replace(PLAN_MODE_PROMPT, "")

        state = "ENABLED" if new_mode else "DISABLED"
        style = "bold green" if new_mode else "bold yellow"
        ctx.console.print(f"[{style}]Plan Mode {state}[/]")
        if new_mode:
            ctx.console.print("[dim]Write and Execute tools are now disabled.[/]")
