"""Intelligent context management commands."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from henchman.cli.commands import Command, CommandContext
from henchman.cli.console_helpers import ConsoleHelper
from henchman.config import load_settings
from henchman.config.settings import save_settings

if TYPE_CHECKING:
    from collections.abc import Callable

    from rich.console import Console

    from henchman.config.schema import ContextSettings
    from henchman.core.agent import Agent


# Constants
_MAX_TOKENS_THRESHOLD: int = 100
_MAX_TOKENS_MIN_VALUE: int = 1000
_COMPACTION_THRESHOLD_MIN_VALUE: float = 0.1
_PERCENTAGE_MULTIPLIER: int = 100  # For converting decimal to percentage


@dataclass
class StrategyParameters:
    """Data class for strategy parameters to reduce primitive obsession.

    Attributes:
        max_tokens: Maximum tokens before compaction.
        compaction_threshold: Compaction threshold (0.1-1.0).
        importance_threshold: Importance threshold (0.0-1.0).
        cluster_similarity_threshold: Cluster similarity threshold (0.0-1.0).
        adaptive_compression: Whether adaptive compression is enabled.
    """

    max_tokens: int
    compaction_threshold: float
    importance_threshold: float
    cluster_similarity_threshold: float
    adaptive_compression: bool


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

    def get_display_label(self: RangeParameterConfig) -> str:
        """Get display label for the parameter.

        Returns:
            Display label.
        """
        return self.label or self.param_name.replace("_", " ").capitalize()

    def validate_value(self: RangeParameterConfig, value: float) -> None:
        """Validate value against range constraints.

        Args:
            value: Value to validate.

        Raises:
            ValueError: If value is outside valid range.
        """
        display_label = self.get_display_label()
        if self.max_val is not None:
            if not self.min_val <= value <= self.max_val:
                msg = f"{display_label} must be between {self.min_val} and {self.max_val}"
                raise ValueError(
                    msg,
                )
        elif value < self.min_val:
            msg = f"{display_label} must be at least {self.min_val}"
            raise ValueError(msg)

    def parse_value(self: RangeParameterConfig, value_str: str) -> float | int:
        """Parse string value to appropriate type.

        Args:
            value_str: String value to parse.

        Returns:
            Parsed value as float or int.
        """
        return int(value_str) if self.is_int else float(value_str)


class ContextConsoleHelper:
    """Helper class for context command console output operations.

    Consolidates console output logic to eliminate duplication and feature envy.
    """

    def __init__(self: ContextConsoleHelper, console_helper: ConsoleHelper | None = None) -> None:
        """Initialize the context console helper.

        Args:
            console_helper: Console helper instance to use. If None, creates a new one.
        """
        self._console_helper = console_helper or ConsoleHelper()

    def print_status_info(
        self: ContextConsoleHelper, console: Console, context_settings: ContextSettings,
    ) -> None:
        """Print intelligent context status information.

        Args:
            console: Console for output.
            context_settings: Context settings to display.
        """
        self._console_helper.print_status_header(console, "Intelligent Context Management")
        self._print_context_settings(console, context_settings, show_intelligent_context=True)
        self._print_available_commands(console)

    def print_strategy_usage(self: ContextConsoleHelper, console: Console) -> None:
        """Print strategy command usage help.

        Args:
            console: Console for output.
        """
        self._console_helper.print_error_message(
            console, "Missing parameter or value", "/context strategy set <parameter> <value>",
        )
        self._print_strategy_parameters(console)

    def print_strategy_status(
        self: ContextConsoleHelper, console: Console, context_settings: ContextSettings,
    ) -> None:
        """Show current compression strategy settings.

        Args:
            console: Console for output.
            context_settings: Context settings to display.
        """
        self._console_helper.print_status_header(console, "Compression Strategy Settings")
        self._print_context_settings(console, context_settings, show_intelligent_context=False)
        console.print("")
        self._console_helper.print_command_help(
            console, "/context strategy set <parameter> <value>", "change settings",
        )
        console.print("")

    def _print_context_settings(
        self: ContextConsoleHelper,
        console: Console,
        context_settings: ContextSettings,
        *,
        show_intelligent_context: bool = False,
    ) -> None:
        """Print context settings with consistent formatting.

        Args:
            console: Console for output.
            context_settings: Context settings to display.
            show_intelligent_context: Whether to show intelligent context status.
        """
        if show_intelligent_context:
            self._console_helper.print_enabled_status(
                console, "Status", is_enabled=context_settings.intelligent_context,
            )

        self._console_helper.print_enabled_status(
            console, "Adaptive compression", is_enabled=context_settings.adaptive_compression,
        )
        self._console_helper.print_status_value(console, "Max tokens", context_settings.max_tokens)
        self._console_helper.print_status_value(
            console, "Compaction threshold",
            f"{context_settings.compaction_threshold * _PERCENTAGE_MULTIPLIER:.0f}%",
        )
        self._console_helper.print_status_value(
            console, "Importance threshold", context_settings.importance_threshold,
        )
        self._console_helper.print_status_value(
            console, "Cluster similarity", context_settings.cluster_similarity_threshold,
        )

    def _print_available_commands(self: ContextConsoleHelper, console: Console) -> None:
        """Print available context commands.

        Args:
            console: Console for output.
        """
        console.print("")
        commands = [
            ("/context enable", "enable intelligent context"),
            ("/context disable", "disable intelligent context"),
            ("/context strategy", "manage compression strategies"),
            ("/context stats", "view usage statistics"),
        ]
        for command, description in commands:
            self._console_helper.print_command_help(console, command, description)
        console.print("")

    def _print_strategy_parameters(self: ContextConsoleHelper, console: Console) -> None:
        """Print parameter list for strategy command.

        Args:
            console: Console for output.
        """
        parameters = [
            ("max_tokens <int>", "Maximum tokens before compaction"),
            ("threshold <float>", "Compaction threshold (0.1-1.0)"),
            ("importance <float>", "Importance threshold (0.0-1.0)"),
            ("similarity <float>", "Cluster similarity threshold (0.0-1.0)"),
            ("adaptive <on|off>", "Enable/disable adaptive compression"),
        ]
        ConsoleHelper.print_parameter_list(console, parameters)


class StrategyManager:
    """Manages compression strategy settings to reduce ContextCommand size."""

    # Command argument indices
    _STRATEGY_ACTION_IDX = 0
    _STRATEGY_PARAM_IDX = 1
    _STRATEGY_VALUE_IDX = 2
    _MIN_SET_ARGS = 3

    def __init__(self: StrategyManager) -> None:
        self._parameter_configs = {
            "max_tokens": RangeParameterConfig(
                param_name="max_tokens", min_val=_MAX_TOKENS_MIN_VALUE, is_int=True,
            ),
            "threshold": RangeParameterConfig(
                param_name="compaction_threshold",
                min_val=_COMPACTION_THRESHOLD_MIN_VALUE,
                max_val=1.0,
                label="Threshold",
            ),
            "importance": RangeParameterConfig(
                param_name="importance_threshold", min_val=0.0, max_val=1.0,
            ),
            "similarity": RangeParameterConfig(
                param_name="cluster_similarity_threshold", min_val=0.0, max_val=1.0,
            ),
        }
        self._console_helper = ContextConsoleHelper()

    async def manage_strategy(self: StrategyManager, ctx: CommandContext, args: list[str]) -> None:
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
            if len(args) < self._MIN_SET_ARGS:  # Need at least 'set', 'parameter' and 'value'
                self._console_helper.print_strategy_usage(ctx.console)
                return

            param = args[self._STRATEGY_PARAM_IDX]
            value = args[self._STRATEGY_VALUE_IDX]
            await self._set_strategy_parameter(ctx, param, value)
        else:
            ctx.console.print("[yellow]Usage: /context strategy [set <parameter> <value>][/]")

    async def _show_strategy_status(self: StrategyManager, ctx: CommandContext) -> None:
        """Show current compression strategy settings.

        Args:
            ctx: Command context.
        """
        context_settings = self._load_context_settings()
        self._console_helper.print_strategy_status(ctx.console, context_settings)

    def _load_context_settings(self: StrategyManager) -> ContextSettings:
        """Load context settings from configuration.

        Returns:
            Context settings object.
        """
        settings = load_settings()
        return settings.context

    async def _set_strategy_parameter(
        self: StrategyManager, ctx: CommandContext, param: str, value: str | None,
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

        if param in self._parameter_configs:
            await self._handle_range_parameter(ctx, value, self._parameter_configs[param])
        elif param == "adaptive":
            await self._handle_adaptive_parameter(ctx, value)
        else:
            ctx.console.print(f"[red]Unknown parameter: {param}[/]")
            ctx.console.print("\nValid parameters:")
            ctx.console.print("  max_tokens, threshold, importance, similarity, adaptive")
            return

    async def _update_context_setting(
        self: StrategyManager,
        ctx: CommandContext,
        param_name: str,
        *,
        value: float | bool,
        display_value: str,
    ) -> None:
        """Helper to update a context setting and save it.

        Args:
            ctx: Command context.
            param_name: Name of the setting in ContextSettings.
            value: New value for the setting (int, float, or bool).
            display_value: Formatted value string for success message.
        """
        settings = load_settings()
        setattr(settings.context, param_name, value)
        save_settings(settings)
        ctx.console.print(
            f"[green]✓ {param_name.replace('_', ' ').capitalize()} set to {display_value}[/]",
        )

    async def _handle_range_parameter(
        self: StrategyManager, ctx: CommandContext, value: str, config: RangeParameterConfig,
    ) -> None:
        """Generic handler for range-validated parameters (DRY)."""
        val = config.parse_value(value)
        config.validate_value(val)
        await self._update_context_setting(ctx, config.param_name, value=val, display_value=str(val))  # noqa: E501

    async def _handle_adaptive_parameter(
        self: StrategyManager, ctx: CommandContext, value: str,
    ) -> None:
        """Handle adaptive parameter setting."""
        lower_value = value.lower()
        if lower_value in ["on", "true", "yes", "1"]:
            await self._update_context_setting(ctx, "adaptive_compression", value=True, display_value="enabled")  # noqa: E501
        elif lower_value in ["off", "false", "no", "0"]:
            await self._update_context_setting(ctx, "adaptive_compression", value=False, display_value="disabled")  # noqa: E501
        else:
            msg = "Value must be 'on' or 'off'"
            raise ValueError(msg)


class ContextCommand(Command):
    """Manage intelligent context settings."""

    # Command argument indices
    _SUBCOMMAND_IDX = 0

    def __init__(self: ContextCommand) -> None:
        super().__init__()
        self._console_helper = ContextConsoleHelper()
        self._strategy_manager = StrategyManager()
        self._statistics_manager = StatisticsManager()

    @property
    def name(self: ContextCommand) -> str:
        """Command name."""
        return "context"

    @property
    def description(self: ContextCommand) -> str:
        """Command description."""
        return "Manage intelligent context settings"

    @property
    def usage(self: ContextCommand) -> str:
        """Command usage."""
        return "/context [enable|disable|strategy|stats]"

    async def execute(self: ContextCommand, ctx: CommandContext) -> None:
        """Execute the context command.

        Args:
            ctx: Command context.
        """
        if not ctx.args:
            await self._show_status(ctx)
            return

        subcommand = ctx.args[self._SUBCOMMAND_IDX].lower()

        if subcommand == "enable":
            await self._enable_intelligent_context(ctx)
        elif subcommand == "disable":
            await self._disable_intelligent_context(ctx)
        elif subcommand == "strategy":
            await self._strategy_manager.manage_strategy(ctx, ctx.args[1:])
        elif subcommand == "stats":
            await self._statistics_manager.show_stats(ctx)
        else:
            await self._show_help_message(ctx)

    async def _show_help_message(self: ContextCommand, ctx: CommandContext) -> None:
        """Show detailed help message."""
        self._print_help_message(ctx.console)

    def _print_help_message(self: ContextCommand, console: Console) -> None:
        """Print detailed help message to console.

        Args:
            console: Console for output.
        """
        commands = [
            ("enable", "Enable intelligent context management"),
            ("disable", "Disable intelligent context management"),
            ("strategy", "Set compression strategy"),
            ("stats", "Show context usage statistics"),
        ]
        ConsoleHelper.print_usage_help(console, self.usage, commands, header="Subcommands:")

    def _show_context_info(
        self: ContextCommand,
        ctx: CommandContext,
        display_func: Callable[[Console, ContextSettings], None],
    ) -> None:
        """Helper method to show context information using a display function.

        Args:
            ctx: Command context.
            display_func: Function to display the context information.
        """
        settings = load_settings()
        context_settings = settings.context
        display_func(ctx.console, context_settings)

    async def _show_status(self: ContextCommand, ctx: CommandContext) -> None:
        """Show current intelligent context status.

        Args:
            ctx: Command context.
        """
        self._show_context_info(ctx, self._console_helper.print_status_info)

    async def _enable_intelligent_context(self: ContextCommand, ctx: CommandContext) -> None:
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

    async def _disable_intelligent_context(self: ContextCommand, ctx: CommandContext) -> None:
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


class StatisticsManager:
    """Manages context usage statistics display to reduce ContextCommand size."""

    async def show_stats(self: StatisticsManager, ctx: CommandContext) -> None:
        """Show context usage statistics.

        Args:
            ctx: Command context.
        """
        if not ctx.agent:
            ctx.console.print("[yellow]No active agent. Cannot show context statistics.[/]")
            return

        self._print_stats_info(ctx.console, ctx.agent)

    def _print_stats_info(self: StatisticsManager, console: Console, agent: Agent) -> None:
        """Print context usage statistics.

        Args:
            console: Console for output.
            agent: Agent to get statistics from.
        """
        # Try to get statistics from the agent's context manager
        try:
            from henchman.utils.intelligent_context import (  # noqa: PLC0415
                IntelligentContextManager,
            )

            if hasattr(agent, "compactor") and isinstance(
                agent.compactor, IntelligentContextManager,
            ):
                compactor = agent.compactor
                stats = compactor.get_statistics() if hasattr(compactor, "get_statistics") else {}
                self._print_stats_with_compactor(console, agent, stats)
            else:
                self._print_no_compactor_message(console)

        except ImportError:
            console.print("[yellow]Intelligent context module not available.[/]")
        except Exception as e:  # noqa: BLE001
            console.print(f"[yellow]Could not retrieve statistics: {e}[/]")

    def _print_stats_with_compactor(
        self: StatisticsManager, console: Console, agent: Agent, stats: dict[str, Any],
    ) -> None:
        """Print statistics when compactor is available.

        Args:
            console: Console for output.
            agent: Agent to get statistics from.
            stats: Statistics dictionary.
        """
        console.print("\n[bold blue]Context Usage Statistics[/]\n")

        if stats:
            self._print_statistics_values(console, stats)
        else:
            console.print("  [dim]No statistics available.[/]")

        # Show current context size if available
        self._print_current_context_size(console, agent)

        console.print("")

    def _print_statistics_values(
        self: StatisticsManager, console: Console, stats: dict[str, Any],
    ) -> None:
        """Print statistics values.

        Args:
            console: Console for output.
            stats: Statistics dictionary.
        """
        console.print(f"  Total messages: [cyan]{stats.get('total_messages', 'N/A')}[/]")
        console.print(f"  Clusters created: [cyan]{stats.get('clusters_created', 'N/A')}[/]")
        console.print(f"  Compression ratio: [cyan]{stats.get('compression_ratio', 'N/A')}[/]")
        console.print(f"  Tokens saved: [cyan]{stats.get('tokens_saved', 'N/A')}[/]")

    def _print_current_context_size(
        self: StatisticsManager, console: Console, agent: Agent,
    ) -> None:
        """Print current context size.

        Args:
            console: Console for output.
            agent: Agent to get session from.
        """
        if hasattr(agent, "session") and agent.session:
            messages = agent.session.messages if hasattr(agent.session, "messages") else []
            console.print(f"  Current messages in session: [cyan]{len(messages)}[/]")

    def _print_no_compactor_message(self: StatisticsManager, console: Console) -> None:
        """Print message when no compactor is active.

        Args:
            console: Console for output.
        """
        console.print("[yellow]Intelligent context manager not active.[/]")
        console.print("[dim]Enable intelligent context with /context enable[/]")
