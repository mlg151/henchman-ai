"""Extensions command for listing registered extensions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from henchman.cli.commands import Command, CommandContext
from henchman.extensions.manager import ExtensionManager

if TYPE_CHECKING:
    from rich.console import Console


def _print_loaded_extensions(
    console: Console,
    extension_names: list[str],
    manager: ExtensionManager,
) -> None:
    """Print loaded extension details to the console.

    Args:
        console: Rich console for output.
        extension_names: Names of registered extensions.
        manager: Extension manager used to look up each extension.
    """
    console.print(f"[bold]Loaded Extensions ({len(extension_names)}):[/]")
    for name in extension_names:
        ext = manager.get(name)
        # ext is guaranteed to exist since we iterate over registered names
        assert ext is not None
        console.print(f"  • [cyan]{ext.name}[/] v{ext.version} - {ext.description}")


class ExtensionsCommand(Command):
    """Command to list registered extensions.

    Example:
        /extensions - List all loaded extensions
    """

    def __init__(self: ExtensionsCommand, manager: ExtensionManager) -> None:
        """Initialize the extensions command.

        Args:
            manager: Extension manager to query.
        """
        self._manager = manager

    @property
    def name(self: ExtensionsCommand) -> str:
        """Command name.

        Returns:
            Command name string.
        """
        return "extensions"

    @property
    def description(self: ExtensionsCommand) -> str:
        """Command description.

        Returns:
            Description string.
        """
        return "List loaded extensions"

    @property
    def usage(self: ExtensionsCommand) -> str:
        """Command usage.

        Returns:
            Usage string.
        """
        return "/extensions"

    async def execute(self: ExtensionsCommand, ctx: CommandContext) -> None:
        """Execute the command.

        Args:
            ctx: Command context with console.

        Returns:
            None
        """
        extensions = self._manager.list_extensions()

        if not extensions:
            ctx.console.print("[dim]No extensions loaded[/]")
            return

        _print_loaded_extensions(ctx.console, extensions, self._manager)
