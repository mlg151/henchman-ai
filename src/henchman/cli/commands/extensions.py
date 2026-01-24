"""Extensions command for listing registered extensions."""

from henchman.cli.commands import Command, CommandContext
from henchman.extensions.manager import ExtensionManager


class ExtensionsCommand(Command):
    """Command to list registered extensions.

    Example:
        /extensions - List all loaded extensions
    """

    def __init__(self, manager: ExtensionManager) -> None:
        """Initialize the extensions command.

        Args:
            manager: Extension manager to query.
        """
        self._manager = manager

    @property
    def name(self) -> str:
        """Command name.

        Returns:
            Command name string.
        """
        return "extensions"

    @property
    def description(self) -> str:
        """Command description.

        Returns:
            Description string.
        """
        return "List loaded extensions"

    @property
    def usage(self) -> str:
        """Command usage.

        Returns:
            Usage string.
        """
        return "/extensions"

    async def execute(self, ctx: CommandContext) -> None:
        """Execute the command.

        Args:
            ctx: Command context with console.
        """
        extensions = self._manager.list_extensions()

        if not extensions:
            ctx.console.print("[dim]No extensions loaded[/]")
            return

        ctx.console.print(f"[bold]Loaded Extensions ({len(extensions)}):[/]")
        for name in extensions:
            ext = self._manager.get(name)
            # ext is guaranteed to exist since we iterate over registered names
            assert ext is not None
            ctx.console.print(
                f"  • [cyan]{ext.name}[/] v{ext.version} - {ext.description}"
            )
