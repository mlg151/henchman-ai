from pathlib import Path

from henchman.cli.commands import Command, CommandContext
from henchman.skills.executor import SkillExecutor
from henchman.skills.learner import SkillLearner
from henchman.skills.store import SkillStore


class SkillCommand(Command):
    """Manage and execute learned skills."""

    @property
    def name(self) -> str:
        """Command name."""
        return "skill"

    @property
    def description(self) -> str:  # pragma: no cover
        """Command description."""
        return "Manage and execute learned skills"

    @property
    def usage(self) -> str:
        """Command usage."""
        return "/skill [list|show|run|delete|learn|export|import|remote]"

    async def execute(self, ctx: CommandContext) -> None:
        """Execute the command.

        Args:
            ctx: Command context.
        """
        if not ctx.args:  # pragma: no cover
            ctx.console.print(f"Usage: {self.usage}")
            return

        subcommand = ctx.args[0]
        args = ctx.args[1:]
        store = SkillStore()

        if subcommand == "list":
            await self._list_skills(ctx, store)
        elif subcommand == "show":
            await self._show_skill(ctx, store, args)
        elif subcommand == "run":
            await self._run_skill(ctx, store, args)
        elif subcommand == "delete":
            await self._delete_skill(ctx, store, args)
        elif subcommand == "learn":
            await self._learn_skill(ctx, store, args)
        elif subcommand == "export":
            await self._export_skill(ctx, store, args)
        elif subcommand == "import":
            await self._import_skill(ctx, store, args)
        elif subcommand == "remote":
            await self._remote_skill(ctx, store, args)
        else:  # pragma: no cover
            ctx.console.print(f"[red]Unknown subcommand: {subcommand}[/]")

    async def _list_skills(self, ctx: CommandContext, store: SkillStore) -> None:
        """List all learned skills."""
        skills = store.list_skills()
        if not skills:  # pragma: no cover
            ctx.console.print("[yellow]No skills learned yet.[/]")
            return

        ctx.console.print("\n[bold blue]Learned Skills[/]\n")
        for skill in skills:
            ctx.console.print(f"  [cyan]{skill.name}[/] - {skill.description}")
        ctx.console.print("")

    async def _show_skill(self, ctx: CommandContext, store: SkillStore, args: list[str]) -> None:
        """Show details of a specific skill."""
        if not args:
            ctx.console.print("[red]Usage: /skill show <name>[/]")
            return

        name = args[0]
        try:
            skill = store.load(name)
            ctx.console.print(f"\n[bold cyan]Skill: {skill.name}[/]")
            ctx.console.print(f"[dim]{skill.description}[/]\n")
            ctx.console.print("[bold]Steps:[/]")
            for i, step in enumerate(skill.steps, 1):
                ctx.console.print(f"  {i}. [green]{step.tool}[/]({step.arguments})")
            ctx.console.print("")
        except FileNotFoundError:  # pragma: no cover
            ctx.console.print(f"[red]Skill not found: {name}[/]")

    async def _run_skill(self, ctx: CommandContext, store: SkillStore, args: list[str]) -> None:
        """Execute a specific skill."""
        if not args:
            ctx.console.print("[red]Usage: /skill run <name>[/]")
            return

        if not ctx.tool_registry:  # pragma: no cover
            ctx.console.print("[red]Tool registry not available.[/]")
            return

        name = args[0]
        try:
            skill = store.load(name)
            executor = SkillExecutor(ctx.tool_registry)

            ctx.console.print(f"[bold blue]Running skill: {skill.name}[/]")
            async for result in executor.run(skill):
                if result.success:  # pragma: no cover
                    ctx.console.print(f"[green]✓[/] {result.content[:100]}...")
                else:  # pragma: no cover
                    ctx.console.print(f"[red]✗[/] Error: {result.error}")
                    break
            ctx.console.print("[bold blue]Skill execution complete.[/]")
        except FileNotFoundError:  # pragma: no cover
            ctx.console.print(f"[red]Skill not found: {name}[/]")

    async def _delete_skill(self, ctx: CommandContext, store: SkillStore, args: list[str]) -> None:
        """Delete a specific skill."""
        if not args:  # pragma: no cover
            ctx.console.print("[red]Usage: /skill delete <name>[/]")
            return

        name = args[0]
        store.delete(name)
        ctx.console.print(f"[green]Skill deleted: {name}[/]")

    async def _learn_skill(self, ctx: CommandContext, store: SkillStore, args: list[str]) -> None:
        """Learn a new skill from the current session."""
        if len(args) < 2:
            ctx.console.print("[red]Usage: /skill learn <name> <description>[/]")
            return

        if not ctx.session or not ctx.session.messages:
            ctx.console.print("[red]No messages in current session to learn from.[/]")
            return

        name = args[0]
        description = " ".join(args[1:])

        learner = SkillLearner()
        # Cast to avoid invariance issue or use Union
        from typing import Any, cast
        messages = cast(list[Any], ctx.session.messages)
        skill = learner.extract_skill(name, description, messages)

        if not skill.steps:  # pragma: no cover
            ctx.console.print("[yellow]No tool calls found in session to extract as a skill.[/]")
            return

        store.save(skill)
        ctx.console.print(f"[green]Learned new skill: {name}[/]")

    async def _export_skill(self, ctx: CommandContext, store: SkillStore, args: list[str]) -> None:
        """Export a skill to stdout."""
        if not args:  # pragma: no cover
            ctx.console.print("[red]Usage: /skill export <name>[/]")
            return
        name = args[0]
        try:
            content = store.export_skill(name)
            ctx.console.print(f"\n[bold green]--- Skill YAML: {name} ---[/]")
            ctx.console.print(content)
            ctx.console.print("[bold green]--- End YAML ---[/]\n")
        except FileNotFoundError:  # pragma: no cover
            ctx.console.print(f"[red]Skill not found: {name}[/]")

    async def _import_skill(self, ctx: CommandContext, store: SkillStore, args: list[str]) -> None:
        """Import a skill from a file."""
        if not args:  # pragma: no cover
            ctx.console.print("[red]Usage: /skill import <path>[/]")
            return
        path = Path(args[0])
        if not path.exists():  # pragma: no cover
            ctx.console.print(f"[red]File not found: {path}[/]")
            return
        try:
            content = path.read_text()
            skill = store.import_skill(content)
            ctx.console.print(f"[green]Successfully imported skill: {skill.name}[/]")
        except Exception as e:  # pragma: no cover
            ctx.console.print(f"[red]Failed to import skill: {e}[/]")

    async def _remote_skill(self, ctx: CommandContext, store: SkillStore, args: list[str]) -> None:
        """Manage skill remotes."""
        if not args:  # pragma: no cover
            ctx.console.print("[red]Usage: /skill remote [add <url>|push|pull][/]")
            return
        cmd = args[0]
        try:
            if cmd == "add" and len(args) > 1:
                store.remote_add(args[1])
                ctx.console.print(f"[green]Remote added: {args[1]}[/]")
            elif cmd == "push":
                store.remote_push()
                ctx.console.print("[green]Skills pushed to remote.[/]")
            elif cmd == "pull":
                store.remote_pull()
                ctx.console.print("[green]Skills pulled from remote.[/]")
            else:  # pragma: no cover
                ctx.console.print(f"[red]Unknown remote command: {cmd}[/]")
        except Exception as e:  # pragma: no cover
            ctx.console.print(f"[red]Remote operation failed: {e}[/]")
