"""Intelligent context management commands."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from henchman.cli.commands import Command, CommandContext
from henchman.cli.console_helpers import ConsoleHelper
from henchman.config import load_settings
from henchman.config.settings import save_settings

if TYPE_CHECKING:
    from rich.console import Console

    from henchman.config.schema import ContextSettings
    from henchman.core.agent import Agent


# Constants
_MAX_TOKENS_THRESHOLD: int = 100


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
        return self.label or self.param_name.replace("_", " ").capitalize()

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
        elif value < self.min_val:
            raise ValueError(f"{display_label} must be at least {self.min_val}")

    def parse_value(self, value_str: str) -> float | int:
        """Parse string value to appropriate type.

        Args:
            value_str: String value to parse.

        Returns:
            Parsed value as float or int.
        """
        return int(value_str) if self.is_int else float(value_str)


class ConsoleOutputHelper:
    """Helper class for console output operations to reduce feature envy."""

    def __init__(self, console: Console) -> None:
        """Initialize with console.

        Args:
            console: Console for output.
        """
        self._console = console

    def print_status_header(self, title: str) -> None:
        """Print status header.

        Args:
            title: Header title.
        """
        ConsoleHelper.print_status_header(self._console, title)

    def print_enabled_status(self, label: str, enabled: bool) -> None:
        """Print enabled/disabled status.

        Args:
            label: Status label.
            enabled: Whether the feature is enabled.
        """
        ConsoleHelper.print_enabled_status(self._console, label, enabled)

    def print_status_value(self, label: str, value: Any) -> None:
        """Print status value.

        Args:
            label: Value label.
            value: Value to display.
        """
        ConsoleHelper.print_status_value(self._console, label, value)

    def print_command_help(self, command: str, description: str) -> None:
        """Print command help.

        Args:
            command: Command syntax.
            description: Command description.
        """
        ConsoleHelper.print_command_help(self._console, command, description)

    def print_error_message(self, title: str, suggestion: str) -> None:
        """Print error message.

        Args:
            title: Error title.
            suggestion: Suggestion for correction.
        """
        ConsoleHelper.print_error_message(self._console, title, suggestion)

    def print_usage_help(
        self, usage: str, commands: list[tuple[str, str]], header: str = "Subcommands:"
    ) -> None:
        """Print usage help.

        Args:
            usage: Command usage syntax.
            commands: List of (command, description) tuples.
            header: Optional header text.
        """
        ConsoleHelper.print_usage_help(self._console, usage, commands, header)

    def print_line(self, text: str = "") -> None:
        """Print a line to console.

        Args:
            text: Text to print.
        """
        self._console.print(text)


class ContextConsoleHelper:
    """Helper class for context command console output operations.

    Consolidates console output logic to eliminate duplication and feature envy.
    """

    @staticmethod
    def print_status_info(console: Console, context_settings: ContextSettings) -> None:
        """Print intelligent context status information.

        Args:
            console: Console for output.
            context_settings: Context settings to display.
        """
        output_helper = ConsoleOutputHelper(console)
        ContextConsoleHelper._print_status_header(output_helper)
        ContextConsoleHelper._print_status_values(output_helper, context_settings)
        ContextConsoleHelper._print_status_commands(output_helper)

    @staticmethod
    def _print_status_header(output_helper: ConsoleOutputHelper) -> None:
        """Print status header.

        Args:
            output_helper: Console output helper.
        """
        output_helper.print_status_header("Intelligent Context Management")

    @staticmethod
    def _print_status_values(
        output_helper: ConsoleOutputHelper, context_settings: ContextSettings
    ) -> None:
        """Print status values.

        Args:
            output_helper: Console output helper.
            context_settings: Context settings to display.
        """
        output_helper.print_enabled_status("Status", context_settings.intelligent_context)
        output_helper.print_enabled_status(
            "Adaptive compression", context_settings.adaptive_compression
        )
        output_helper.print_status_value("Max tokens", context_settings.max_tokens)
        output_helper.print_status_value(
            "Compaction threshold", f"{context_settings.compaction_threshold * 100:.0f}%"
        )
        output_helper.print_status_value(
            "Importance threshold", context_settings.importance_threshold
        )
        output_helper.print_status_value(
            "Cluster similarity", context_settings.cluster_similarity_threshold
        )

    @staticmethod
    def _print_status_commands(output_helper: ConsoleOutputHelper) -> None:
        """Print available commands.

        Args:
            output_helper: Console output helper.
        """
        ContextConsoleHelper._print_command_list(
            output_helper,
            [
                ("/context enable", "enable intelligent context"),
                ("/context disable", "disable intelligent context"),
                ("/context strategy", "manage compression strategies"),
                ("/context stats", "view usage statistics"),
            ],
        )

    @staticmethod
    def print_strategy_usage(console: Console) -> None:
        """Print strategy command usage help.

        Args:
            console: Console for output.
        """
        output_helper = ConsoleOutputHelper(console)
        output_helper.print_error_message(
            "Missing parameter or value", "/context strategy set <parameter> <value>"
        )
        output_helper.print_line("\nParameters:")
        output_helper.print_line("  max_tokens <int>          - Maximum tokens before compaction")
        output_helper.print_line("  threshold <float>         - Compaction threshold (0.1-1.0)")
        output_helper.print_line("  importance <float>        - Importance threshold (0.0-1.0)")
        output_helper.print_line(
            "  similarity <float>        - Cluster similarity threshold (0.0-1.0)"
        )
        output_helper.print_line(
            "  adaptive <on|off>         - Enable/disable adaptive compression"
        )

    @staticmethod
    def print_strategy_status(console: Console, context_settings: ContextSettings) -> None:
        """Show current compression strategy settings.

        Args:
            console: Console for output.
            context_settings: Context settings to display.
        """
        output_helper = ConsoleOutputHelper(console)
        output_helper.print_line("\n[bold blue]Compression Strategy Settings[/]\n")
        output_helper.print_status_value("Max tokens", context_settings.max_tokens)
        output_helper.print_status_value(
            "Compaction threshold", context_settings.compaction_threshold
        )
        output_helper.print_status_value(
            "Importance threshold", context_settings.importance_threshold
        )
        output_helper.print_status_value(
            "Cluster similarity", context_settings.cluster_similarity_threshold
        )
        output_helper.print_enabled_status(
            "Adaptive compression", context_settings.adaptive_compression
        )
        output_helper.print_line("")
        output_helper.print_command_help(
            "/context strategy set <parameter> <value>", "change settings"
        )
        output_helper.print_line("")

    @staticmethod
    def _print_command_list(
        output_helper: ConsoleOutputHelper, commands: list[tuple[str, str]]
    ) -> None:
        """Print a list of commands (shared logic to eliminate duplication).

        Args:
            output_helper: Console output helper.
            commands: List of (command, description) tuples.
        """
        output_helper.print_line("")
        for command, description in commands:
            output_helper.print_command_help(command, description)
        output_helper.print_line("")


class StrategyManager:
    """Manages compression strategy settings to reduce ContextCommand size."""

    # Command argument indices
    _STRATEGY_ACTION_IDX = 0
    _STRATEGY_PARAM_IDX = 1
    _STRATEGY_VALUE_IDX = 2

    def __init__(self) -> None:
        """Initialize strategy manager."""
        self._parameter_configs = {
            "max_tokens": RangeParameterConfig(param_name="max_tokens", min_val=1000, is_int=True),
            "threshold": RangeParameterConfig(
                param_name="compaction_threshold", min_val=0.1, max_val=1.0, label="Threshold"
            ),
            "importance": RangeParameterConfig(
                param_name="importance_threshold", min_val=0.0, max_val=1.0
            ),
            "similarity": RangeParameterConfig(
                param_name="cluster_similarity_threshold", min_val=0.0, max_val=1.0
            ),
        }

    async def manage_strategy(self, ctx: CommandContext, args: list[str]) -> None:
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
                ContextConsoleHelper.print_strategy_usage(ctx.console)
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
        ContextConsoleHelper.print_strategy_status(ctx.console, context_settings)

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
        self, ctx: CommandContext, param_name: str, value: Any, display_value: str
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
        ctx.console.print(
            f"[green]✓ {param_name.replace('_', ' ').capitalize()} set to {display_value}[/]"
        )

    async def _handle_range_parameter(
        self, ctx: CommandContext, value: str, config: RangeParameterConfig
    ) -> None:
        """Generic handler for range-validated parameters (DRY)."""
        val = config.parse_value(value)
        config.validate_value(val)
        await self._update_context_setting(ctx, config.param_name, val, str(val))

    async def _handle_adaptive_parameter(self, ctx: CommandContext, value: str) -> None:
        """Handle adaptive parameter setting."""
        lower_value = value.lower()
        if lower_value in ["on", "true", "yes", "1"]:
            await self._update_context_setting(ctx, "adaptive_compression", True, "enabled")
        elif lower_value in ["off", "false", "no", "0"]:
            await self._update_context_setting(ctx, "adaptive_compression", False, "disabled")
        else:
            raise ValueError("Value must be 'on' or 'off'")


class ContextCommand(Command):
    """Manage intelligent context settings."""

    # Command argument indices
    _SUBCOMMAND_IDX = 0

    def __init__(self) -> None:
        """Initialize context command."""
        super().__init__()
        self._strategy_manager = StrategyManager()
        self._statistics_manager = StatisticsManager()

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
            "strategy": lambda c: self._strategy_manager.manage_strategy(c, c.args[1:]),
            "stats": lambda c: self._statistics_manager.show_stats(c),
        }

        handler = dispatch.get(subcommand)
        if handler:
            await handler(ctx)
        else:
            await self._show_help_message(ctx)

    async def _show_help_message(self, ctx: CommandContext) -> None:
        """Show detailed help message."""
        self._print_help_message(ctx.console)

    def _print_help_message(self, console: Console) -> None:
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

    async def _show_status(self, ctx: CommandContext) -> None:
        """Show current intelligent context status.

        Args:
            ctx: Command context.
        """
        settings = load_settings()
        context_settings = settings.context
        ContextConsoleHelper.print_status_info(ctx.console, context_settings)

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


class StatisticsManager:
    """Manages context usage statistics display to reduce ContextCommand size."""

    async def show_stats(self, ctx: CommandContext) -> None:
        """Show context usage statistics.

        Args:
            ctx: Command context.
        """
        if not ctx.agent:
            ctx.console.print("[yellow]No active agent. Cannot show context statistics.[/]")
            return

        self._print_stats_info(ctx.console, ctx.agent)

    def _print_stats_info(self, console: Console, agent: Agent) -> None:
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
                self._print_stats_with_compactor(console, agent, stats)
            else:
                self._print_no_compactor_message(console)

        except ImportError:
            console.print("[yellow]Intelligent context module not available.[/]")
        except Exception as e:
            console.print(f"[yellow]Could not retrieve statistics: {e}[/]")

    def _print_stats_with_compactor(
        self, console: Console, agent: Agent, stats: dict[str, Any]
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

    def _print_statistics_values(self, console: Console, stats: dict[str, Any]) -> None:
        """Print statistics values.

        Args:
            console: Console for output.
            stats: Statistics dictionary.
        """
        console.print(f"  Total messages: [cyan]{stats.get('total_messages', 'N/A')}[/]")
        console.print(f"  Clusters created: [cyan]{stats.get('clusters_created', 'N/A')}[/]")
        console.print(f"  Compression ratio: [cyan]{stats.get('compression_ratio', 'N/A')}[/]")
        console.print(f"  Tokens saved: [cyan]{stats.get('tokens_saved', 'N/A')}[/]")

    def _print_current_context_size(self, console: Console, agent: Agent) -> None:
        """Print current context size.

        Args:
            console: Console for output.
            agent: Agent to get session from.
        """
        if hasattr(agent, "session") and agent.session:
            messages = agent.session.messages if hasattr(agent.session, "messages") else []
            console.print(f"  Current messages in session: [cyan]{len(messages)}[/]")

    def _print_no_compactor_message(self, console: Console) -> None:
        """Print message when no compactor is active.

        Args:
            console: Console for output.
        """
        console.print("[yellow]Intelligent context manager not active.[/]")
        console.print("[dim]Enable intelligent context with /context enable[/]")
