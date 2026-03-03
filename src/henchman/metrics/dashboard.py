"""Performance dashboard for Henchman-AI.

Provides real-time visualization and monitoring of agent performance metrics.
"""

import json
import time
from datetime import datetime, timedelta
from typing import Any

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from henchman.metrics.models import MetricType
from henchman.metrics.storage import MetricsStorage


class Dashboard:
    """Performance dashboard for monitoring Henchman-AI metrics.

    This class provides visualization and monitoring capabilities for
    token usage, costs, tool performance, and usage analytics.

    Attributes:
        metrics_storage: Storage backend for metrics data.
        refresh_interval: Interval for dashboard refresh in seconds.
        console: Rich console for output.
        live_display: Live display for real-time updates.
    """

    def __init__(
        self,
        metrics_storage: MetricsStorage,
        refresh_interval: int = 5,
        console: Console | None = None,
    ) -> None:
        """Initialize the dashboard.

        Args:
            metrics_storage: Storage backend for metrics data.
            refresh_interval: Interval for dashboard refresh in seconds.
            console: Optional Rich console instance.
        """
        self.metrics_storage = metrics_storage
        self.refresh_interval = refresh_interval
        self.console = console or Console()
        self.live_display: Live | None = None
        self._running = False

    def display(self) -> None:
        """Display the dashboard interface."""
        self._running = True
        self.live_display = Live(
            self._create_layout(),
            console=self.console,
            refresh_per_second=1,
            screen=True,
        )

        with self.live_display:
            while self._running:
                self.refresh()
                time.sleep(self.refresh_interval)

    def refresh(self) -> None:
        """Refresh dashboard data."""
        if self.live_display:
            self.live_display.update(self._create_layout())

    def get_summary_stats(self) -> dict[str, Any]:
        """Get summary statistics from metrics.

        Returns:
            Dictionary of summary statistics.
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)

        stats: dict[str, Any] = {
            "time_period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            },
            "token_usage": {},
            "costs": {},
            "tool_performance": {},
            "usage_patterns": {},
        }

        # Get token usage stats
        token_stats = self.metrics_storage.get_aggregated_stats(
            MetricType.TOKEN_USAGE,
            group_by="day",
            start_date=start_date,
            end_date=end_date,
        )
        if token_stats:
            total_tokens = sum(stat.get("total_tokens", 0) for stat in token_stats)
            stats["token_usage"] = {
                "total_tokens": total_tokens,
                "daily_average": total_tokens / len(token_stats) if token_stats else 0,
                "periods": token_stats,
            }

        # Get cost stats
        cost_stats = self.metrics_storage.get_aggregated_stats(
            MetricType.COST,
            group_by="day",
            start_date=start_date,
            end_date=end_date,
        )
        if cost_stats:
            total_cost = sum(stat.get("total_cost", 0.0) for stat in cost_stats)
            stats["costs"] = {
                "total_cost": total_cost,
                "daily_average": total_cost / len(cost_stats) if cost_stats else 0.0,
                "periods": cost_stats,
            }

        # Get tool performance stats
        tool_stats = self.metrics_storage.get_aggregated_stats(
            MetricType.TOOL_PERFORMANCE,
            group_by="day",
            start_date=start_date,
            end_date=end_date,
        )
        if tool_stats:
            total_calls = sum(stat.get("count", 0) for stat in tool_stats)
            successful_calls = sum(stat.get("successful_calls", 0) for stat in tool_stats)
            stats["tool_performance"] = {
                "total_calls": total_calls,
                "success_rate": (successful_calls / total_calls * 100) if total_calls > 0 else 0,
                "periods": tool_stats,
            }

        # Get usage patterns
        usage_stats = self.metrics_storage.get_aggregated_stats(
            MetricType.USAGE_PATTERN,
            group_by="day",
            start_date=start_date,
            end_date=end_date,
        )
        if usage_stats:
            total_commands = sum(stat.get("unique_commands", 0) for stat in usage_stats)
            total_tool_calls = sum(stat.get("total_tool_calls", 0) for stat in usage_stats)
            stats["usage_patterns"] = {
                "unique_commands": total_commands,
                "total_tool_calls": total_tool_calls,
                "periods": usage_stats,
            }

        return stats

    def export_data(self, format: str = "json") -> str:
        """Export dashboard data in specified format.

        Args:
            format: Output format (json, csv, etc.)

        Returns:
            Exported data as string.
        """
        stats = self.get_summary_stats()

        if format.lower() == "json":
            return json.dumps(stats, indent=2, default=str)
        if format.lower() == "csv":
            # Simple CSV export of key metrics
            import csv
            import io

            output = io.StringIO()
            writer = csv.writer(output)

            # Write header
            writer.writerow(["Metric", "Value", "Unit"])

            # Write token usage
            if stats.get("token_usage"):
                writer.writerow(["Total Tokens", stats["token_usage"].get("total_tokens", 0), "tokens"])
                writer.writerow(["Daily Average Tokens", stats["token_usage"].get("daily_average", 0), "tokens"])

            # Write costs
            if stats.get("costs"):
                writer.writerow(["Total Cost", stats["costs"].get("total_cost", 0), "USD"])
                writer.writerow(["Daily Average Cost", stats["costs"].get("daily_average", 0), "USD"])

            # Write tool performance
            if stats.get("tool_performance"):
                writer.writerow(["Total Tool Calls", stats["tool_performance"].get("total_calls", 0), "calls"])
                writer.writerow(["Success Rate", stats["tool_performance"].get("success_rate", 0), "%"])

            return output.getvalue()
        msg = f"Unsupported format: {format}. Supported formats: json, csv"
        raise ValueError(msg)

    def close(self) -> None:
        """Close dashboard and release resources."""
        self._running = False
        if self.live_display:
            self.live_display.stop()

    def _create_layout(self) -> Layout:
        """Create the dashboard layout.

        Returns:
            Rich Layout object.
        """
        layout = Layout()

        # Split into header and main area
        layout.split(
            Layout(name="header", size=3),
            Layout(name="main"),
        )

        # Further split main area
        layout["main"].split_row(
            Layout(name="left", ratio=1),
            Layout(name="right", ratio=1),
        )

        # Split left column
        layout["left"].split(
            Layout(name="token_stats", size=8),
            Layout(name="cost_stats", size=8),
        )

        # Split right column
        layout["right"].split(
            Layout(name="tool_stats", size=8),
            Layout(name="usage_stats", size=8),
        )

        # Update all panels
        layout["header"].update(self._create_header())
        layout["token_stats"].update(self._create_token_panel())
        layout["cost_stats"].update(self._create_cost_panel())
        layout["tool_stats"].update(self._create_tool_panel())
        layout["usage_stats"].update(self._create_usage_panel())

        return layout

    def _create_header(self) -> Panel:
        """Create dashboard header.

        Returns:
            Rich Panel with header.
        """
        title = Text("Henchman-AI Performance Dashboard", style="bold blue")
        timestamp = Text(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", style="dim")
        header_text = Text.assemble(title, "\n", timestamp)
        return Panel(header_text, border_style="blue")

    def _create_token_panel(self) -> Panel:
        """Create token usage panel.

        Returns:
            Rich Panel with token statistics.
        """
        stats = self.get_summary_stats()
        token_stats = stats.get("token_usage", {})

        table = Table(title="Token Usage (Last 7 Days)", show_header=False, box=None)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        total_tokens = token_stats.get("total_tokens", 0)
        daily_avg = token_stats.get("daily_average", 0)

        table.add_row("Total Tokens", f"{total_tokens:,}")
        table.add_row("Daily Average", f"{daily_avg:,.0f}")
        table.add_row("Periods", str(len(token_stats.get("periods", []))))

        return Panel(table, title="Token Usage", border_style="green")

    def _create_cost_panel(self) -> Panel:
        """Create cost panel.

        Returns:
            Rich Panel with cost statistics.
        """
        stats = self.get_summary_stats()
        cost_stats = stats.get("costs", {})

        table = Table(title="Costs (Last 7 Days)", show_header=False, box=None)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="yellow")

        total_cost = cost_stats.get("total_cost", 0.0)
        daily_avg = cost_stats.get("daily_average", 0.0)

        table.add_row("Total Cost", f"${total_cost:.4f}")
        table.add_row("Daily Average", f"${daily_avg:.4f}")
        table.add_row("Periods", str(len(cost_stats.get("periods", []))))

        return Panel(table, title="Costs", border_style="yellow")

    def _create_tool_panel(self) -> Panel:
        """Create tool performance panel.

        Returns:
            Rich Panel with tool statistics.
        """
        stats = self.get_summary_stats()
        tool_stats = stats.get("tool_performance", {})

        table = Table(title="Tool Performance (Last 7 Days)", show_header=False, box=None)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="magenta")

        total_calls = tool_stats.get("total_calls", 0)
        success_rate = tool_stats.get("success_rate", 0.0)

        table.add_row("Total Calls", f"{total_calls:,}")
        table.add_row("Success Rate", f"{success_rate:.1f}%")
        table.add_row("Periods", str(len(tool_stats.get("periods", []))))

        return Panel(table, title="Tool Performance", border_style="magenta")

    def _create_usage_panel(self) -> Panel:
        """Create usage patterns panel.

        Returns:
            Rich Panel with usage statistics.
        """
        stats = self.get_summary_stats()
        usage_stats = stats.get("usage_patterns", {})

        table = Table(title="Usage Patterns (Last 7 Days)", show_header=False, box=None)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="cyan")

        unique_commands = usage_stats.get("unique_commands", 0)
        total_tool_calls = usage_stats.get("total_tool_calls", 0)

        table.add_row("Unique Commands", str(unique_commands))
        table.add_row("Total Tool Calls", f"{total_tool_calls:,}")
        table.add_row("Periods", str(len(usage_stats.get("periods", []))))

        return Panel(table, title="Usage Patterns", border_style="cyan")
