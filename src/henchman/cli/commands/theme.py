"""Theme management command.

This module provides the /theme command for managing UI themes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from henchman.cli.commands import Command, CommandContext
from henchman.cli.console import ThemeManager
from henchman.cli.console_helpers import ConsoleHelper

if TYPE_CHECKING:
    from henchman.cli.repl import Repl


class ThemeCommand(Command):
    """Manage UI themes.

    This command allows users to list, set, preview, and create themes.
    """

    @property
    def name(self) -> str:
        """Command name.

        Returns:
            Command name string.
        """
        return "theme"

    @property
    def description(self) -> str:
        """Command description.

        Returns:
            Description string.
        """
        return "Manage UI themes (list, set, preview, create)"

    @property
    def usage(self) -> str:
        """Command usage.

        Returns:
            Usage string.
        """
        return "/theme <subcommand> [args]\n\nSubcommands:\n  list     - Show available themes\n  set      - Change active theme\n  preview  - Show sample output with theme\n  create   - Stub for custom theme creation"  # noqa: E501

    async def execute(self, ctx: CommandContext) -> None:
        """Execute the theme command.

        Args:
            ctx: Command context.
        """
        if not ctx.args:
            ctx.console.print("[yellow]Usage:[/] " + self.usage)
            return

        subcommand = ctx.args[0].lower()
        args = ctx.args[1:]

        if subcommand == "list":
            await self._list_themes(ctx)
        elif subcommand == "set":
            await self._set_theme(ctx, args)
        elif subcommand == "preview":
            await self._preview_theme(ctx, args)
        elif subcommand == "create":
            await self._create_theme(ctx, args)
        else:
            ctx.console.print(f"[red]Unknown subcommand: {subcommand}[/]")
            ctx.console.print("[yellow]Usage:[/] " + self.usage)

    async def _list_themes(self, ctx: CommandContext) -> None:
        """List available themes with current theme highlighted.

        Args:
            ctx: Command context.
        """
        # Get theme manager from REPL or create a new one
        theme_manager = self._get_theme_manager(ctx.repl)
        current_theme = theme_manager.current.name
        available_themes = theme_manager.list_themes()

        ctx.console.print("\n[bold blue]Available Themes[/]\n")
        for theme_name in available_themes:
            if theme_name == current_theme:
                ctx.console.print(f"  [green]• {theme_name} (current)[/]")
            else:
                ctx.console.print(f"  {theme_name}")
        ctx.console.print()

    async def _set_theme(self, ctx: CommandContext, args: list[str]) -> None:
        """Change active theme and provide feedback.

        Args:
            ctx: Command context.
            args: Command arguments (theme name).
        """
        if not args:
            self._print_set_theme_error(ctx.console)
            return

        theme_name = args[0]
        theme_manager = self._get_theme_manager(ctx.repl)

        # Check if theme exists
        theme_name = self._validate_theme_name(ctx, theme_name, theme_manager)

        # Set the theme
        theme_manager.set_theme(theme_name)

        # Update REPL renderer if available
        self._update_renderer_theme(ctx, theme_manager)

        ctx.console.print(f"[green]Theme set to:[/] {theme_name}")

        self._persist_theme_settings(ctx, theme_name)

    def _print_set_theme_error(self, console: Any) -> None:
        """Print error message for missing theme name.

        Args:
            console: Console for output.
        """
        ConsoleHelper.print_error_message(console, "Theme name required", "/theme set <theme-name>")

    def _validate_theme_name(self, ctx: CommandContext, theme_name: str, theme_manager: Any) -> str:
        """Validate theme name and fall back to default if not found.

        Args:
            ctx: Command context.
            theme_name: Name of the theme to validate.
            theme_manager: Theme manager instance.

        Returns:
            Valid theme name (original or fallback).
        """
        if theme_name not in theme_manager.list_themes():
            ctx.console.print(f"[yellow]Warning:[/] Theme '{theme_name}' not found")
            ctx.console.print("[dim]Falling back to default theme (dark)[/]")
            return "dark"
        return theme_name

    def _update_renderer_theme(self, ctx: CommandContext, theme_manager: Any) -> None:
        """Update REPL renderer with new theme.

        Args:
            ctx: Command context.
            theme_manager: Theme manager instance.
        """
        if ctx.repl and hasattr(ctx.repl, "renderer") and hasattr(ctx.repl.renderer, "renderer"):
            if hasattr(ctx.repl.renderer.renderer, "theme"):
                ctx.repl.renderer.renderer.theme = theme_manager.current
            else:
                # Fallback: create new renderer with theme
                from henchman.cli.console import OutputRenderer  # noqa: PLC0415

                ctx.repl.renderer.renderer = OutputRenderer(
                    console=ctx.repl.renderer.console, theme=theme_manager.current,
                )

    def _persist_theme_settings(self, ctx: CommandContext, theme_name: str) -> None:
        """Persist theme settings to disk.

        Args:
            ctx: Command context.
            theme_name: Name of the theme to persist.
        """
        if ctx.repl and hasattr(ctx.repl, "settings") and ctx.repl.settings:
            try:
                # Update settings object
                ctx.repl.settings.ui.theme = theme_name

                # Persist settings
                from henchman.config.settings import save_settings  # noqa: PLC0415

                save_settings(ctx.repl.settings)

                ctx.console.print("[dim]Theme saved to settings[/]")
            except Exception as e:  # noqa: BLE001
                ctx.console.print(f"[red]Warning:[/] Failed to save settings: {e}")

    async def _preview_theme(self, ctx: CommandContext, args: list[str]) -> None:
        """Show sample output with the theme.

        Args:
            ctx: Command context.
            args: Command arguments (theme name).
        """
        if not args:
            ctx.console.print("[red]Error:[/] Theme name required")
            ctx.console.print("[yellow]Usage:[/] /theme preview <theme-name>")
            return

        theme_name = args[0]
        theme_manager = self._get_theme_manager(ctx.repl)

        # Check if theme exists
        if theme_name not in theme_manager.list_themes():
            ctx.console.print(f"[red]Error:[/] Theme '{theme_name}' not found")
            ctx.console.print("[dim]Available themes:[/] " + ", ".join(theme_manager.list_themes()))
            return

        # Create a temporary renderer with the preview theme
        from henchman.cli.console import OutputRenderer  # noqa: PLC0415

        preview_theme = theme_manager.get_theme(theme_name)
        preview_renderer = OutputRenderer(console=ctx.console, theme=preview_theme)

        ctx.console.print(f"\n[bold blue]Preview of '{theme_name}' theme[/]\n")

        # Show sample output
        preview_renderer.info("This is an info message")
        preview_renderer.success("This is a success message")
        preview_renderer.warning("This is a warning message")
        preview_renderer.error("This is an error message")
        preview_renderer.muted("This is muted text")
        preview_renderer.heading("This is a heading")

        ctx.console.print()

    async def _create_theme(self, ctx: CommandContext, args: list[str]) -> None:  # noqa: ARG002
        """Stub for future custom theme creation.

        Args:
            ctx: Command context.
            args: Command arguments (theme name).
        """
        ctx.console.print("[yellow]Custom theme creation is not yet implemented.[/]")
        ctx.console.print("[dim]This feature is planned for a future release.[/]")

    def _get_theme_manager(self, repl: Repl | None) -> ThemeManager:
        """Get theme manager from REPL or create a new one.

        Args:
            repl: REPL instance or None.

        Returns:
            ThemeManager instance.
        """
        if (
            repl
            and hasattr(repl, "renderer")
            and hasattr(repl.renderer, "renderer")
            and hasattr(repl.renderer.renderer, "theme")
        ):
            # Create a theme manager with current theme
            theme_manager = ThemeManager()
            theme_manager.set_theme(repl.renderer.renderer.theme.name)
            return theme_manager

        # Fallback: create new theme manager
        return ThemeManager()
