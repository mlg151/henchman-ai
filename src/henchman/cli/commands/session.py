"""Enhanced session management command.

This module provides the /session command for advanced session operations
including branching, merging, templates, and export/import.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from henchman.cli.commands import BaseCommand, CommandContext

if TYPE_CHECKING:
    from henchman.core.session import SessionManager


class SessionCommand(BaseCommand):
    """/session command for enhanced session management."""

    _help_command_name = "Enhanced Session"
    _help_lines = [
        "  /session branch <id> <point> [tag]  - Branch from session at message point",
        "  /session merge <id1> <id2> [strategy] [tag] - Merge sessions",
        "  /session template save <id> <name>  - Save session as template",
        "  /session template create <name>     - Create from template",
        "  /session template list              - List templates",
        "  /session template delete <id>       - Delete template",
        "  /session export <id> [format]       - Export session (json/markdown)",
        "  /session import <file> [format]     - Import session",
        "  /session list                       - List sessions with enhanced info",
        "",
        "[dim]Strategies: union, intersection, smart[/]",
        "[dim]Formats: json (default), markdown[/]",
    ]

    @property
    def name(self) -> str:
        """Command name.

        Returns:
            Command name string.
        """
        return "session"

    @property
    def description(self) -> str:
        """Command description.

        Returns:
            Description string.
        """
        return "Enhanced session management (branch, merge, templates, export/import)"

    @property
    def usage(self) -> str:
        """Command usage.

        Returns:
            Usage string.
        """
        return "/session <branch|merge|template|export|import|list> [args]"

    async def execute(self, ctx: CommandContext) -> None:
        """Execute the session command.

        Args:
            ctx: Command context with args and session_manager.
        """
        if not ctx.args:
            await self._show_help(ctx)
            return

        subcommand = ctx.args[0].lower()
        if subcommand == "branch":
            await self._branch(ctx)
        elif subcommand == "merge":
            await self._merge(ctx)
        elif subcommand == "template":
            await self._template(ctx)
        elif subcommand == "export":
            await self._export(ctx)
        elif subcommand == "import":
            await self._import(ctx)
        elif subcommand == "list":
            await self._list(ctx)
        else:
            await self._show_help(ctx)

    def _get_manager(self, ctx: CommandContext) -> SessionManager | None:
        """Get session manager from context with error handling.

        Args:
            ctx: Command context.

        Returns:
            SessionManager or None if not available.
        """
        manager: SessionManager | None = getattr(ctx, "session_manager", None)
        if manager is None:
            ctx.console.print("[red]Session manager not available[/]")
        return manager

    def _ensure_args(self, ctx: CommandContext, min_args: int, usage: str) -> bool:
        """Ensure minimum number of arguments.

        Args:
            ctx: Command context.
            min_args: Minimum number of arguments required.
            usage: Usage string to show if validation fails.

        Returns:
            True if arguments are valid, False otherwise.
        """
        if len(ctx.args) < min_args:
            ctx.console.print(f"[yellow]Usage: {usage}[/]")
            return False
        return True

    async def _branch(self, ctx: CommandContext) -> None:
        """Branch from an existing session."""
        manager = self._get_manager(ctx)
        if manager is None:
            return

        if not self._ensure_args(ctx, 3, "/session branch <id> <point> [tag]"):
            return

        session_id = ctx.args[1]
        try:
            branch_point = int(ctx.args[2])
        except ValueError:
            ctx.console.print("[red]Branch point must be an integer[/]")
            return

        tag = ctx.args[3] if len(ctx.args) > 3 else None

        try:
            branch = manager.branch_session(session_id, branch_point, tag)
            manager.save(branch)
            ctx.console.print(f"[green]✓[/] Created branch: {branch.id}")
            if branch.tag:
                ctx.console.print(f"[dim]Tag: {branch.tag}[/]")
            ctx.console.print(f"[dim]Branch point: {branch_point}, Parent: {session_id}[/]")
        except (FileNotFoundError, ValueError) as e:
            ctx.console.print(f"[red]Error: {e}[/]")

    async def _merge(self, ctx: CommandContext) -> None:
        """Merge multiple sessions."""
        manager = self._get_manager(ctx)
        if manager is None:
            return

        if not self._ensure_args(ctx, 3, "/session merge <id1> <id2> [strategy] [tag]"):
            return

        session_ids = [ctx.args[1], ctx.args[2]]
        strategy = "smart"
        tag = None

        # Parse optional arguments
        if len(ctx.args) > 3:
            if ctx.args[3] in ("union", "intersection", "smart"):
                strategy = ctx.args[3]
                if len(ctx.args) > 4:
                    tag = ctx.args[4]
            else:
                tag = ctx.args[3]

        try:
            merged = manager.merge_sessions(session_ids, strategy, tag)
            manager.save(merged)
            ctx.console.print(f"[green]✓[/] Created merged session: {merged.id}")
            if merged.tag:
                ctx.console.print(f"[dim]Tag: {merged.tag}[/]")
            ctx.console.print(f"[dim]Strategy: {strategy}, Sources: {', '.join(session_ids)}[/]")
            ctx.console.print(f"[dim]Messages: {len(merged.messages)}[/]")
        except (FileNotFoundError, ValueError) as e:
            ctx.console.print(f"[red]Error: {e}[/]")

    async def _template(self, ctx: CommandContext) -> None:
        """Template operations."""
        manager = self._get_manager(ctx)
        if manager is None:
            return

        if not self._ensure_args(ctx, 2, "/session template <save|create|list|delete> [args]"):
            return

        subcmd = ctx.args[1].lower()
        if subcmd == "save":
            await self._template_save(ctx, manager)
        elif subcmd == "create":
            await self._template_create(ctx, manager)
        elif subcmd == "list":
            await self._template_list(ctx, manager)
        elif subcmd == "delete":
            await self._template_delete(ctx, manager)
        else:
            ctx.console.print("[yellow]Usage: /session template <save|create|list|delete>[/]")

    async def _template_save(self, ctx: CommandContext, manager: SessionManager) -> None:
        """Save a session as template."""
        if not self._ensure_args(ctx, 4, "/session template save <id> <name>"):
            return

        session_id = ctx.args[2]
        name = ctx.args[3]
        description = ctx.args[4] if len(ctx.args) > 4 else ""

        try:
            template = manager.save_template(session_id, name, description)
            ctx.console.print(f"[green]✓[/] Saved template: {template['name']}")
            ctx.console.print(f"[dim]ID: {template['id']}[/]")
            if description:
                ctx.console.print(f"[dim]Description: {description}[/]")
        except (FileNotFoundError, ValueError) as e:
            ctx.console.print(f"[red]Error: {e}[/]")

    async def _template_create(self, ctx: CommandContext, manager: SessionManager) -> None:
        """Create session from template."""
        if not self._ensure_args(ctx, 3, "/session template create <template_id> [tag]"):
            return

        template_id = ctx.args[2]
        tag = ctx.args[3] if len(ctx.args) > 3 else None

        try:
            session = manager.create_from_template(template_id, tag=tag)
            manager.save(session)
            ctx.console.print(f"[green]✓[/] Created session from template: {session.id}")
            if session.tag:
                ctx.console.print(f"[dim]Tag: {session.tag}[/]")
            ctx.console.print(f"[dim]Template: {template_id}[/]")
        except (FileNotFoundError, ValueError) as e:
            ctx.console.print(f"[red]Error: {e}[/]")

    async def _template_list(self, ctx: CommandContext, manager: SessionManager) -> None:
        """List available templates."""
        templates = manager.list_templates()

        if not templates:
            ctx.console.print("[dim]No templates available[/]")
            return

        ctx.console.print("\n[bold blue]Available Templates[/]\n")
        for template in templates:
            ctx.console.print(f"  [cyan]{template['name']}[/]")
            ctx.console.print(f"    ID: {template['id']}")
            if template.get('description'):
                ctx.console.print(f"    Description: {template['description']}")
            if template.get('parameters'):
                params = ', '.join(template['parameters'].keys())
                ctx.console.print(f"    Parameters: {params}")
            ctx.console.print(f"    Created: {template.get('created_at', 'unknown')}")
            ctx.console.print("")

    async def _template_delete(self, ctx: CommandContext, manager: SessionManager) -> None:
        """Delete a template."""
        if not self._ensure_args(ctx, 3, "/session template delete <template_id>"):
            return

        template_id = ctx.args[2]

        try:
            manager.delete_template(template_id)
            ctx.console.print(f"[green]✓[/] Deleted template: {template_id}")
        except FileNotFoundError as e:
            ctx.console.print(f"[red]Error: {e}[/]")

    async def _export(self, ctx: CommandContext) -> None:
        """Export a session."""
        manager = self._get_manager(ctx)
        if manager is None:
            return

        if not self._ensure_args(ctx, 2, "/session export <id> [format]"):
            return

        session_id = ctx.args[1]
        format = ctx.args[2] if len(ctx.args) > 2 else "json"

        try:
            exported = manager.export_session(session_id, format)

            ext = "json" if format == "json" else "md"
            output_file = Path.cwd() / f"session_{session_id}.{ext}"
            output_file.write_text(exported)
            
            ctx.console.print(f"[green]✓[/] Exported session to: {output_file}")
            ctx.console.print(f"[dim]Format: {format}, Size: {len(exported)} bytes[/]")
        except (FileNotFoundError, ValueError) as e:
            ctx.console.print(f"[red]Error: {e}[/]")

    async def _import(self, ctx: CommandContext) -> None:
        """Import a session."""
        manager = self._get_manager(ctx)
        if manager is None:
            return

        if not self._ensure_args(ctx, 2, "/session import <file> [format]"):
            return

        file_path = Path(ctx.args[1])
        if not file_path.exists():
            ctx.console.print(f"[red]File not found: {file_path}[/]")
            return

        format = ctx.args[2] if len(ctx.args) > 2 else "json"
        tag = ctx.args[3] if len(ctx.args) > 3 else None

        try:
            data = file_path.read_text()
            session = manager.import_session(data, format, tag)
            manager.save(session)

            ctx.console.print(f"[green]✓[/] Imported session: {session.id}")
            if session.tag:
                ctx.console.print(f"[dim]Tag: {session.tag}[/]")
            ctx.console.print(f"[dim]Format: {format}, Messages: {len(session.messages)}[/]")
        except (ValueError, json.JSONDecodeError) as e:
            ctx.console.print(f"[red]Error importing session: {e}[/]")

    async def _list(self, ctx: CommandContext) -> None:
        """List sessions with enhanced information."""
        manager = self._get_manager(ctx)
        if manager is None:
            return

        project_hash = getattr(ctx, "project_hash", None)
        sessions = manager.list_sessions(project_hash)

        if not sessions:
            ctx.console.print("[dim]No saved sessions[/]")
            return

        ctx.console.print("\n[bold blue]Saved Sessions[/]\n")
        for meta in sessions:
            # Load full session for enhanced info
            try:
                session = manager.load(meta.id)

                tag_display = f"[cyan]{meta.tag}[/]" if meta.tag else f"[dim]{meta.id[:8]}[/]"
                branch_info = ""
                template_info = ""

                if session.parent_id:
                    branch_info = f" [yellow]↳[/] branch from {session.parent_id[:8]}"
                if session.template_id:
                    template_info = f" [magenta]ⓣ[/] template:{session.template_id[:8]}"

                ctx.console.print(
                    f"  {tag_display}{branch_info}{template_info}"
                )
                ctx.console.print(
                    f"    Messages: {meta.message_count}, "
                    f"Updated: {meta.last_updated[:10]}"
                )
                if session.export_metadata and "merged_from" in session.export_metadata:
                    ctx.console.print(
                        f"    [dim]Merged from {len(session.export_metadata['merged_from'])} sessions[/]"
                    )
                ctx.console.print("")
            except (FileNotFoundError, ValueError, json.JSONDecodeError):
                # Fallback to basic info if session can't be loaded
                tag_display = f"[cyan]{meta.tag}[/]" if meta.tag else f"[dim]{meta.id[:8]}[/]"
                ctx.console.print(
                    f"  {tag_display} - {meta.message_count} messages, "
                    f"updated {meta.last_updated[:10]}"
                )
