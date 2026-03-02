"""Intelligent context management commands."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from henchman.cli.commands import Command, CommandContext
from henchman.config import load_settings
from henchman.config.settings import save_settings

if TYPE_CHECKING:
    pass


@dataclass
class RangeParameterConfig:
    """Configuration for range-validated parameters.
    
    Attributes:
        param_name: Name of the parameter.
        min_val: Minimum allowed value.
        max_val: Maximum allowed value (optional).
        is_int: Whether the value should be an integer.
        label: Display label for the parameter.
    """
    param_name: str
    min_val: float
    max_val: float | None = None
    is_int: bool = False
    label: str | None = None
    
    def get_display_label(self) -> str:
        """Get display label for the parameter.
        
        Returns:
            Display label.
        """
        return self.label or self.param_name.replace('_', ' ').capitalize()
    
    def validate_value(self, value: float | int) -> None:
        """Validate value against range constraints.
        
        Args:
            value: Value to validate.
            
        Raises:
            ValueError: If value is outside valid range.
        """
        display_label = self.get_display_label()
        if self.max_val is not None:
            if not self.min_val <= value <= self.max_val:
                raise ValueError(
                    f"{display_label} must be between {self.min_val} and {self.max_val}"
                )
        else:
            if value < self.min_val:
                raise ValueError(f"{display_label} must be at least {self.min_val}")
    
    def parse_value(self, value_str: str) -> float | int:
        """Parse string value to appropriate type.
        
        Args:
            value_str: String value to parse.
            
        Returns:
            Parsed value as float or int.
        """
        return int(value_str) if self.is_int else float(value_str)


class ContextCommand(Command):
    """Manage intelligent context settings."""

    # Command argument indices
    _SUBCOMMAND_IDX = 0
    _STRATEGY_ACTION_IDX = 0
    _STRATEGY_PARAM_IDX = 1
    _STRATEGY_VALUE_IDX = 2

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
        if not ctx.args:
            await self._show_status(ctx)
            return

        subcommand = ctx.args[self._SUBCOMMAND_IDX].lower()
        dispatch = {
            "enable": self._enable_intelligent_context,
            "disable": self._disable_intelligent_context,
            "strategy": lambda c: self._manage_strategy(c, c.args[1:]),
            "stats": self._show_stats,
        }

        handler = dispatch.get(subcommand)
        if handler:
            await handler(ctx)
        else:
            await self._show_help_message(ctx)

    async def _show_help_message(self, ctx: CommandContext) -> None:
        """Show detailed help message."""
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
        self._print_status_info(ctx.console, context_settings)

    def _print_status_info(self, console: Any, context_settings: Any) -> None:
        """Print intelligent context status information.
        
        Args:
            console: Console for output.
            context_settings: Context settings to display.
        """
        console.print("\n[bold blue]Intelligent Context Management[/]\n")
        console.print(
            f"  Status: [{'green' if context_settings.intelligent_context else 'red'}]"
            f"{'Enabled' if context_settings.intelligent_context else 'Disabled'}[/]"
        )
        console.print(
            f"  Adaptive compression: [{'green' if context_settings.adaptive_compression else 'yellow'}]"
            f"{'Enabled' if context_settings.adaptive_compression else 'Disabled'}[/]"
        )
        console.print(f"  Max tokens: [cyan]{context_settings.max_tokens}[/]")
        console.print(
            f"  Compaction threshold: [cyan]{context_settings.compaction_threshold * 100:.0f}%[/]"
        )
        console.print(
            f"  Importance threshold: [cyan]{context_settings.importance_threshold}[/]"
        )
        console.print(
            f"  Cluster similarity: [cyan]{context_settings.cluster_similarity_threshold}[/]"
        )
        console.print("")
        console.print("  Use [cyan]/context enable[/] to enable intelligent context")
        console.print("  Use [cyan]/context disable[/] to disable intelligent context")
        console.print("  Use [cyan]/context strategy[/] to manage compression strategies")
        console.print("  Use [cyan]/context stats[/] to view usage statistics")
        console.print("")

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
            return

        action = args[self._STRATEGY_ACTION_IDX].lower()
        if action == "set":
            if len(args) < 3:  # Need at least 'set', 'parameter' and 'value'
                ctx.console.print("[yellow]Usage: /context strategy set <parameter> <value>[/]")
                ctx.console.print("\nParameters:")
                ctx.console.print("  max_tokens <int>          - Maximum tokens before compaction")
                ctx.console.print("  threshold <float>         - Compaction threshold (0.1-1.0)")
                ctx.console.print("  importance <float>        - Importance threshold (0.0-1.0)")
                ctx.console.print(
                    "  similarity <float>        - Cluster similarity threshold (0.0-1.0)"
                )
                ctx.console.print(
                    "  adaptive <on|off>         - Enable/disable adaptive compression"
                )
                return
            
            param = args[self._STRATEGY_PARAM_IDX]
            value = args[self._STRATEGY_VALUE_IDX]
            await self._set_strategy_parameter(ctx, param, value)
        else:
            ctx.console.print("[yellow]Usage: /context strategy [set <parameter> <value>][/]")

    async def _show_strategy_status(self, ctx: CommandContext) -> None:
        """Show current compression strategy settings.

        Args:
            ctx: Command context.
        """
        settings = load_settings()
        context_settings = settings.context
        console = ctx.console

        console.print("\n[bold blue]Compression Strategy Settings[/]\n")
        console.print(f"  Max tokens: [cyan]{context_settings.max_tokens}[/]")
        console.print(
            f"  Compaction threshold: [cyan]{context_settings.compaction_threshold}[/]"
        )
        console.print(
            f"  Importance threshold: [cyan]{context_settings.importance_threshold}[/]"
        )
        console.print(
            f"  Cluster similarity: [cyan]{context_settings.cluster_similarity_threshold}[/]"
        )
        console.print(
            f"  Adaptive compression: [{'green' if context_settings.adaptive_compression else 'yellow'}]"
            f"{'Enabled' if context_settings.adaptive_compression else 'Disabled'}[/]"
        )
        console.print("")
        console.print(
            "  Use [cyan]/context strategy set <parameter> <value>[/] to change settings"
        )
        console.print("")

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

    async def _update_context_setting(
        self, ctx: CommandContext, param_name: str, value: any, display_value: str
    ) -> None:
        """Helper to update a context setting and save it.

        Args:
            ctx: Command context.
            param_name: Name of the setting in ContextSettings.
            value: New value for the setting.
            display_value: Formatted value string for success message.
        """
        settings = load_settings()
        setattr(settings.context, param_name, value)
        save_settings(settings)
        ctx.console.print(f"[green]✓ {param_name.replace('_', ' ').capitalize()} set to {display_value}[/]")

    async def _handle_range_parameter(
        self,
        ctx: CommandContext,
        value: str,
        config: RangeParameterConfig
    ) -> None:
        """Generic handler for range-validated parameters (DRY)."""
        val = config.parse_value(value)
        config.validate_value(val)
        await self._update_context_setting(ctx, config.param_name, val, str(val))

    async def _handle_max_tokens_parameter(self, ctx: CommandContext, value: str) -> None:
        """Handle max_tokens parameter setting."""
        config = RangeParameterConfig(
            param_name="max_tokens",
            min_val=1000,
            is_int=True
        )
        await self._handle_range_parameter(ctx, value, config)

    async def _handle_threshold_parameter(self, ctx: CommandContext, value: str) -> None:
        """Handle threshold parameter setting."""
        config = RangeParameterConfig(
            param_name="compaction_threshold",
            min_val=0.1,
            max_val=1.0,
            label="Threshold"
        )
        await self._handle_range_parameter(ctx, value, config)

    async def _handle_importance_parameter(self, ctx: CommandContext, value: str) -> None:
        """Handle importance parameter setting."""
        await self._handle_zero_to_one_parameter(ctx, value, "importance_threshold")

    async def _handle_similarity_parameter(self, ctx: CommandContext, value: str) -> None:
        """Handle similarity parameter setting."""
        await self._handle_zero_to_one_parameter(ctx, value, "cluster_similarity_threshold")

    async def _handle_zero_to_one_parameter(
        self, ctx: CommandContext, value: str, param_name: str
    ) -> None:
        """Handle parameter with range 0.0 to 1.0.
        
        Args:
            ctx: Command context.
            value: Parameter value as string.
            param_name: Name of the parameter.
        """
        config = RangeParameterConfig(
            param_name=param_name,
            min_val=0.0,
            max_val=1.0
        )
        await self._handle_range_parameter(ctx, value, config)

    async def _handle_adaptive_parameter(self, ctx: CommandContext, value: str) -> None:
        """Handle adaptive parameter setting."""
        lower_value = value.lower()
        if lower_value in ["on", "true", "yes", "1"]:
            await self._update_context_setting(ctx, "adaptive_compression", True, "enabled")
        elif lower_value in ["off", "false", "no", "0"]:
            await self._update_context_setting(ctx, "adaptive_compression", False, "disabled")
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

        self._print_stats_info(ctx.console, ctx.agent)

    def _print_stats_info(self, console: Any, agent: Any) -> None:
        """Print context usage statistics.
        
        Args:
            console: Console for output.
            agent: Agent to get statistics from.
        """
        # Try to get statistics from the agent's context manager
        try:
            from henchman.utils.intelligent_context import IntelligentContextManager

            if hasattr(agent, "compactor") and isinstance(
                agent.compactor, IntelligentContextManager
            ):
                compactor = agent.compactor
                stats = compactor.get_statistics() if hasattr(compactor, "get_statistics") else {}

                console.print("\n[bold blue]Context Usage Statistics[/]\n")

                if stats:
                    console.print(f"  Total messages: [cyan]{stats.get('total_messages', 'N/A')}[/]")
                    console.print(f"  Clusters created: [cyan]{stats.get('clusters_created', 'N/A')}[/]")
                    console.print(f"  Compression ratio: [cyan]{stats.get('compression_ratio', 'N/A')}[/]")
                    console.print(f"  Tokens saved: [cyan]{stats.get('tokens_saved', 'N/A')}[/]")
                else:
                    console.print("  [dim]No statistics available.[/]")

                # Show current context size if available
                if hasattr(agent, "session") and agent.session:
                    messages = (
                        agent.session.messages if hasattr(agent.session, "messages") else []
                    )
                    console.print(f"  Current messages in session: [cyan]{len(messages)}[/]")

                console.print("")
            else:
                console.print("[yellow]Intelligent context manager not active.[/]")
                console.print("[dim]Enable intelligent context with /context enable[/]")

        except ImportError:
            console.print("[yellow]Intelligent context module not available.[/]")
        except Exception as e:
            console.print(f"[yellow]Could not retrieve statistics: {e}[/]")
