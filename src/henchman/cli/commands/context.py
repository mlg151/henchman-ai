"""Intelligent context management commands."""

from __future__ import annotations

from typing import TYPE_CHECKING

from henchman.cli.commands import Command, CommandContext
from henchman.config import load_settings
from henchman.config.settings import save_settings

if TYPE_CHECKING:
    pass


class ContextCommand(Command):
    """Manage intelligent context settings."""

    @property
    def name(self) -> str:
        """Command name.

        Returns:
            Command name string.
        """
        return "context"

    @property
    def description(self) -> str:
        """Command description.

        Returns:
            Description string.
        """
        return "Manage intelligent context settings"

    @property
    def usage(self) -> str:
        """Command usage.

        Returns:
            Usage string.
        """
        return "/context [enable|disable|strategy|stats]"

    async def execute(self, ctx: CommandContext) -> None:
        """Execute the context command.

        Args:
            ctx: Command context.
        """
        args = ctx.args
        if not args:
            await self._show_status(ctx)
        elif args[0] == "enable":
            await self._enable_intelligent_context(ctx)
        elif args[0] == "disable":
            await self._disable_intelligent_context(ctx)
        elif args[0] == "strategy":
            await self._manage_strategy(ctx, args[1:] if len(args) > 1 else [])
        elif args[0] == "stats":
            await self._show_stats(ctx)
        else:
            ctx.console.print(f"[yellow]Usage: {self.usage}[/]")
            ctx.console.print("\nSubcommands:")
            ctx.console.print("  enable     - Enable intelligent context management")
            ctx.console.print("  disable    - Disable intelligent context management")
            ctx.console.print("  strategy   - Set compression strategy")
            ctx.console.print("  stats      - Show context usage statistics")
            ctx.console.print("")

    async def _show_status(self, ctx: CommandContext) -> None:
        """Show current intelligent context status.

        Args:
            ctx: Command context.
        """
        settings = load_settings()
        context_settings = settings.context

        ctx.console.print("\n[bold blue]Intelligent Context Management[/]\n")
        ctx.console.print(
            f"  Status: [{'green' if context_settings.intelligent_context else 'red'}]"
            f"{'Enabled' if context_settings.intelligent_context else 'Disabled'}[/]"
        )
        ctx.console.print(
            f"  Adaptive compression: [{'green' if context_settings.adaptive_compression else 'yellow'}]"
            f"{'Enabled' if context_settings.adaptive_compression else 'Disabled'}[/]"
        )
        ctx.console.print(f"  Max tokens: [cyan]{context_settings.max_tokens}[/]")
        ctx.console.print(
            f"  Compaction threshold: [cyan]{context_settings.compaction_threshold * 100:.0f}%[/]"
        )
        ctx.console.print(
            f"  Importance threshold: [cyan]{context_settings.importance_threshold}[/]"
        )
        ctx.console.print(
            f"  Cluster similarity: [cyan]{context_settings.cluster_similarity_threshold}[/]"
        )
        ctx.console.print("")
        ctx.console.print("  Use [cyan]/context enable[/] to enable intelligent context")
        ctx.console.print("  Use [cyan]/context disable[/] to disable intelligent context")
        ctx.console.print("  Use [cyan]/context strategy[/] to manage compression strategies")
        ctx.console.print("  Use [cyan]/context stats[/] to view usage statistics")
        ctx.console.print("")

    async def _enable_intelligent_context(self, ctx: CommandContext) -> None:
        """Enable intelligent context management.

        Args:
            ctx: Command context.
        """
        settings = load_settings()
        if settings.context.intelligent_context:
            ctx.console.print("[yellow]Intelligent context is already enabled.[/]")
            return

        settings.context.intelligent_context = True
        save_settings(settings)
        ctx.console.print("[green]✓ Intelligent context management enabled.[/]")
        ctx.console.print("[dim]Note: This setting will take effect in new sessions.[/]")

    async def _disable_intelligent_context(self, ctx: CommandContext) -> None:
        """Disable intelligent context management.

        Args:
            ctx: Command context.
        """
        settings = load_settings()
        if not settings.context.intelligent_context:
            ctx.console.print("[yellow]Intelligent context is already disabled.[/]")
            return

        settings.context.intelligent_context = False
        save_settings(settings)
        ctx.console.print("[green]✓ Intelligent context management disabled.[/]")
        ctx.console.print("[dim]Note: This setting will take effect in new sessions.[/]")

    async def _manage_strategy(self, ctx: CommandContext, args: list[str]) -> None:
        """Manage compression strategy settings.

        Args:
            ctx: Command context.
            args: Strategy command arguments.
        """
        if not args:
            await self._show_strategy_status(ctx)
        elif args[0] == "set":
            if len(args) < 2:
                ctx.console.print("[yellow]Usage: /context strategy set <parameter> <value>[/]")
                ctx.console.print("\nParameters:")
                ctx.console.print("  max_tokens <int>          - Maximum tokens before compaction")
                ctx.console.print("  threshold <float>         - Compaction threshold (0.0-1.0)")
                ctx.console.print("  importance <float>        - Importance threshold (0.0-1.0)")
                ctx.console.print(
                    "  similarity <float>        - Cluster similarity threshold (0.0-1.0)"
                )
                ctx.console.print(
                    "  adaptive <on|off>         - Enable/disable adaptive compression"
                )
                return
            await self._set_strategy_parameter(ctx, args[1], args[2] if len(args) > 2 else None)
        else:
            ctx.console.print("[yellow]Usage: /context strategy [set <parameter> <value>][/]")

    async def _show_strategy_status(self, ctx: CommandContext) -> None:
        """Show current compression strategy settings.

        Args:
            ctx: Command context.
        """
        settings = load_settings()
        context_settings = settings.context

        ctx.console.print("\n[bold blue]Compression Strategy Settings[/]\n")
        ctx.console.print(f"  Max tokens: [cyan]{context_settings.max_tokens}[/]")
        ctx.console.print(
            f"  Compaction threshold: [cyan]{context_settings.compaction_threshold}[/]"
        )
        ctx.console.print(
            f"  Importance threshold: [cyan]{context_settings.importance_threshold}[/]"
        )
        ctx.console.print(
            f"  Cluster similarity: [cyan]{context_settings.cluster_similarity_threshold}[/]"
        )
        ctx.console.print(
            f"  Adaptive compression: [{'green' if context_settings.adaptive_compression else 'yellow'}]"
            f"{'Enabled' if context_settings.adaptive_compression else 'Disabled'}[/]"
        )
        ctx.console.print("")
        ctx.console.print(
            "  Use [cyan]/context strategy set <parameter> <value>[/] to change settings"
        )
        ctx.console.print("")

    async def _set_strategy_parameter(
        self, ctx: CommandContext, param: str, value: str | None
    ) -> None:
        """Set a strategy parameter.

        Args:
            ctx: Command context.
            param: Parameter name.
            value: Parameter value.

        Raises:
            ValueError: If value is invalid.
        """
        if value is None:
            ctx.console.print(f"[yellow]Missing value for parameter '{param}'[/]")
            return

        # Define parameter handlers
        handlers = {
            "max_tokens": self._handle_max_tokens_parameter,
            "threshold": self._handle_threshold_parameter,
            "importance": self._handle_importance_parameter,
            "similarity": self._handle_similarity_parameter,
            "adaptive": self._handle_adaptive_parameter,
        }

        handler = handlers.get(param)
        if handler is None:
            ctx.console.print(f"[red]Unknown parameter: {param}[/]")
            ctx.console.print("\nValid parameters:")
            ctx.console.print("  max_tokens, threshold, importance, similarity, adaptive")
            return

        try:
            await handler(ctx, value)
        except ValueError as e:
            ctx.console.print(f"[red]Invalid value: {e}[/]")

    async def _handle_max_tokens_parameter(self, ctx: CommandContext, value: str) -> None:
        """Handle max_tokens parameter setting.

        Args:
            ctx: Command context.
            value: Parameter value as string.

        Raises:
            ValueError: If value is invalid.
        """
        from henchman.config import load_settings
        from henchman.config.settings import save_settings

        int_value = int(value)
        if int_value < 1000:
            raise ValueError("Max tokens must be at least 1000")

        settings = load_settings()
        settings.context.max_tokens = int_value
        save_settings(settings)
        ctx.console.print(f"[green]✓ Max tokens set to {int_value}[/]")

    async def _handle_threshold_parameter(self, ctx: CommandContext, value: str) -> None:
        """Handle threshold parameter setting.

        Args:
            ctx: Command context.
            value: Parameter value as string.

        Raises:
            ValueError: If value is invalid.
        """
        from henchman.config import load_settings
        from henchman.config.settings import save_settings

        float_value = float(value)
        if not 0.1 <= float_value <= 1.0:
            raise ValueError("Threshold must be between 0.1 and 1.0")

        settings = load_settings()
        settings.context.compaction_threshold = float_value
        save_settings(settings)
        ctx.console.print(f"[green]✓ Compaction threshold set to {float_value}[/]")

    async def _handle_importance_parameter(self, ctx: CommandContext, value: str) -> None:
        """Handle importance parameter setting.

        Args:
            ctx: Command context.
            value: Parameter value as string.

        Raises:
            ValueError: If value is invalid.
        """
        from henchman.config import load_settings
        from henchman.config.settings import save_settings

        float_value = float(value)
        if not 0.0 <= float_value <= 1.0:
            raise ValueError("Importance threshold must be between 0.0 and 1.0")

        settings = load_settings()
        settings.context.importance_threshold = float_value
        save_settings(settings)
        ctx.console.print(f"[green]✓ Importance threshold set to {float_value}[/]")

    async def _handle_similarity_parameter(self, ctx: CommandContext, value: str) -> None:
        """Handle similarity parameter setting.

        Args:
            ctx: Command context.
            value: Parameter value as string.

        Raises:
            ValueError: If value is invalid.
        """
        from henchman.config import load_settings
        from henchman.config.settings import save_settings

        float_value = float(value)
        if not 0.0 <= float_value <= 1.0:
            raise ValueError("Similarity threshold must be between 0.0 and 1.0")

        settings = load_settings()
        settings.context.cluster_similarity_threshold = float_value
        save_settings(settings)
        ctx.console.print(f"[green]✓ Cluster similarity threshold set to {float_value}[/]")

    async def _handle_adaptive_parameter(self, ctx: CommandContext, value: str) -> None:
        """Handle adaptive parameter setting.

        Args:
            ctx: Command context.
            value: Parameter value as string.

        Raises:
            ValueError: If value is invalid.
        """
        from henchman.config import load_settings
        from henchman.config.settings import save_settings

        lower_value = value.lower()
        settings = load_settings()

        if lower_value in ["on", "true", "yes", "1"]:
            settings.context.adaptive_compression = True
            save_settings(settings)
            ctx.console.print("[green]✓ Adaptive compression enabled[/]")
        elif lower_value in ["off", "false", "no", "0"]:
            settings.context.adaptive_compression = False
            save_settings(settings)
            ctx.console.print("[green]✓ Adaptive compression disabled[/]")
        else:
            raise ValueError("Value must be 'on' or 'off'")

    async def _show_stats(self, ctx: CommandContext) -> None:
        """Show context usage statistics.

        Args:
            ctx: Command context.
        """
        if not ctx.agent:
            ctx.console.print("[yellow]No active agent. Cannot show context statistics.[/]")
            return

        # Try to get statistics from the agent's context manager
        try:
            from henchman.utils.intelligent_context import IntelligentContextManager

            if hasattr(ctx.agent, "compactor") and isinstance(
                ctx.agent.compactor, IntelligentContextManager
            ):
                compactor = ctx.agent.compactor
                stats = compactor.get_statistics() if hasattr(compactor, "get_statistics") else {}

                ctx.console.print("\n[bold blue]Context Usage Statistics[/]\n")

                if stats:
                    ctx.console.print(
                        f"  Total messages: [cyan]{stats.get('total_messages', 'N/A')}[/]"
                    )
                    ctx.console.print(
                        f"  Clusters created: [cyan]{stats.get('clusters_created', 'N/A')}[/]"
                    )
                    ctx.console.print(
                        f"  Compression ratio: [cyan]{stats.get('compression_ratio', 'N/A')}[/]"
                    )
                    ctx.console.print(
                        f"  Tokens saved: [cyan]{stats.get('tokens_saved', 'N/A')}[/]"
                    )
                else:
                    ctx.console.print("  [dim]No statistics available.[/]")

                # Show current context size if available
                if hasattr(ctx.agent, "session") and ctx.agent.session:
                    messages = (
                        ctx.agent.session.messages if hasattr(ctx.agent.session, "messages") else []
                    )
                    ctx.console.print(f"  Current messages in session: [cyan]{len(messages)}[/]")

                ctx.console.print("")
            else:
                ctx.console.print("[yellow]Intelligent context manager not active.[/]")
                ctx.console.print("[dim]Enable intelligent context with /context enable[/]")

        except ImportError:
            ctx.console.print("[yellow]Intelligent context module not available.[/]")
        except Exception as e:
            ctx.console.print(f"[yellow]Could not retrieve statistics: {e}[/]")
