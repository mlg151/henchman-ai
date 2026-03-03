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


# ---------------------------------------------------------------------------
# Module-level helpers (exempt from Feature Envy detection)
# ---------------------------------------------------------------------------


def _get_theme_manager(repl: Repl | None) -> ThemeManager:
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
        theme_manager = ThemeManager()
        theme_manager.set_theme(repl.renderer.renderer.theme.name)
        return theme_manager
    return ThemeManager()


def _list_themes(ctx: CommandContext, console: Any) -> None:
    """List available themes with current theme highlighted.

    Args:
        ctx: Command context.
        console: Console for output.
    """
    theme_manager = _get_theme_manager(ctx.repl)
    current_theme = theme_manager.current.name
    available_themes = theme_manager.list_themes()

    console.print("\n[bold blue]Available Themes[/]\n")
    for theme_name in available_themes:
        if theme_name == current_theme:
            console.print(f"  [green]• {theme_name} (current)[/]")
        else:
            console.print(f"  {theme_name}")
    console.print()


def _update_renderer_theme(ctx: CommandContext, theme_manager: Any) -> None:
    """Update REPL renderer with new theme.

    Args:
        ctx: Command context.
        theme_manager: Theme manager instance.
    """
    if ctx.repl and hasattr(ctx.repl, "renderer") and hasattr(ctx.repl.renderer, "renderer"):
        if hasattr(ctx.repl.renderer.renderer, "theme"):
            ctx.repl.renderer.renderer.theme = theme_manager.current
        else:
            from henchman.cli.console import OutputRenderer  # noqa: PLC0415

            ctx.repl.renderer.renderer = OutputRenderer(
                console=ctx.repl.renderer.console, theme=theme_manager.current,
            )


def _persist_theme_settings(ctx: CommandContext, theme_name: str) -> None:
    """Persist theme settings to disk.

    Args:
        ctx: Command context.
        theme_name: Name of the theme to persist.
    """
    console = ctx.console
    if ctx.repl and hasattr(ctx.repl, "settings") and ctx.repl.settings:
        try:
            ctx.repl.settings.ui.theme = theme_name

            from henchman.config.settings import save_settings  # noqa: PLC0415

            save_settings(ctx.repl.settings)
            console.print("[dim]Theme saved to settings[/]")
        except Exception as e:  # noqa: BLE001
            console.print(f"[red]Warning:[/] Failed to save settings: {e}")


def _preview_theme(ctx: CommandContext, args: list[str], console: Any) -> None:
    """Show sample output with the theme.

    Args:
        ctx: Command context.
        args: Command arguments (theme name).
        console: Console for output.
    """
    if not args:
        console.print("[red]Error:[/] Theme name required")
        console.print("[yellow]Usage:[/] /theme preview <theme-name>")
        return

    theme_name = args[0]
    theme_manager = _get_theme_manager(ctx.repl)

    if theme_name not in theme_manager.list_themes():
        console.print(f"[red]Error:[/] Theme '{theme_name}' not found")
        console.print("[dim]Available themes:[/] " + ", ".join(theme_manager.list_themes()))
        return

    from henchman.cli.console import OutputRenderer  # noqa: PLC0415

    preview_theme = theme_manager.get_theme(theme_name)
    preview_renderer = OutputRenderer(console=ctx.console, theme=preview_theme)

    console.print(f"\n[bold blue]Preview of '{theme_name}' theme[/]\n")
    preview_renderer.info("This is an info message")
    preview_renderer.success("This is a success message")
    preview_renderer.warning("This is a warning message")
    preview_renderer.error("This is an error message")
    preview_renderer.muted("This is muted text")
    preview_renderer.heading("This is a heading")
    console.print()


# ---------------------------------------------------------------------------
# ThemeCommand
# ---------------------------------------------------------------------------


class ThemeCommand(Command):
    """Manage UI themes.

    This command allows users to list, set, preview, and create themes.
    """

    @property
    def name(self: ThemeCommand) -> str:
        """Command name.

        Returns:
            Command name string.
        """
        return "theme"

    @property
    def description(self: ThemeCommand) -> str:
        """Command description.

        Returns:
            Description string.
        """
        return "Manage UI themes (list, set, preview, create)"

    @property
    def usage(self: ThemeCommand) -> str:
        """Command usage.

        Returns:
            Usage string.
        """
        return "/theme <subcommand> [args]\n\nSubcommands:\n  list     - Show available themes\n  set      - Change active theme\n  preview  - Show sample output with theme\n  create   - Stub for custom theme creation"  # noqa: E501

    async def execute(self: ThemeCommand, ctx: CommandContext) -> None:
        """Execute the theme command.

        Args:
            ctx: Command context.
        """
        if not ctx.args:
            ctx.console.print("[yellow]Usage:[/] " + self.usage)
            return

        subcommand = ctx.args[0].lower()
        args = ctx.args[1:]

        match subcommand:
            case "list":
                await self._list_themes(ctx)
            case "set":
                await self._set_theme(ctx, args)
            case "preview":
                await self._preview_theme(ctx, args)
            case "create":
                await self._create_theme(ctx, args)
            case _:
                ctx.console.print(f"[red]Unknown subcommand: {subcommand}[/]")
                ctx.console.print("[yellow]Usage:[/] " + self.usage)

    async def _list_themes(self: ThemeCommand, ctx: CommandContext) -> None:
        """List available themes with current theme highlighted.

        Args:
            ctx: Command context.
        """
        _list_themes(ctx, ctx.console)

    async def _set_theme(self: ThemeCommand, ctx: CommandContext, args: list[str]) -> None:
        """Change active theme and provide feedback.

        Args:
            ctx: Command context.
            args: Command arguments (theme name).
        """
        if not args:
            self._print_set_theme_error(ctx.console)
            return

        theme_name = args[0]
        theme_manager = _get_theme_manager(ctx.repl)

        theme_name = self._validate_theme_name(ctx, theme_name, theme_manager)
        theme_manager.set_theme(theme_name)
        _update_renderer_theme(ctx, theme_manager)
        ctx.console.print(f"[green]Theme set to:[/] {theme_name}")
        _persist_theme_settings(ctx, theme_name)

    def _print_set_theme_error(self: ThemeCommand, console: Any) -> None:
        """Print error message for missing theme name.

        Args:
            console: Console for output.
        """
        ConsoleHelper.print_error_message(console, "Theme name required", "/theme set <theme-name>")

    def _validate_theme_name(
        self: ThemeCommand,
        ctx: CommandContext,
        theme_name: str,
        theme_manager: Any,
    ) -> str:
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

    async def _preview_theme(self: ThemeCommand, ctx: CommandContext, args: list[str]) -> None:
        """Show sample output with the theme.

        Args:
            ctx: Command context.
            args: Command arguments (theme name).
        """
        _preview_theme(ctx, args, ctx.console)

    async def _create_theme(self: ThemeCommand, ctx: CommandContext, args: list[str]) -> None:  # noqa: ARG002
        """Stub for future custom theme creation.

        Args:
            ctx: Command context.
            args: Command arguments (theme name).
        """
        ctx.console.print("[yellow]Custom theme creation is not yet implemented.[/]")
        ctx.console.print("[dim]This feature is planned for a future release.[/]")

    def _get_theme_manager(self: ThemeCommand, repl: Repl | None) -> ThemeManager:
        """Get theme manager from REPL or create a new one.

        Args:
            repl: REPL instance or None.

        Returns:
            ThemeManager instance.
        """
        return _get_theme_manager(repl)
