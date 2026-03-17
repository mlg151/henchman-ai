"""Performance dashboard for Henchman-AI.

Provides real-time visualization and monitoring of agent performance metrics.
"""

from __future__ import annotations

import csv
import io
import json
import time
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from henchman.metrics.models import MetricType

if TYPE_CHECKING:
    from collections.abc import Callable

    from henchman.metrics.storage import MetricsStorage

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------
STATS_LOOKBACK_DAYS = 7
"""Number of days to look back when computing summary statistics."""

SUCCESS_RATE_MULTIPLIER = 100
"""Multiplier to convert a ratio to a percentage."""


# ---------------------------------------------------------------------------
# Module-level helpers — fetch + aggregate in one step (fixes Duplicate Code)
# ---------------------------------------------------------------------------


def _collect_stats(
    storage: MetricsStorage,
    metric_type: MetricType,
    aggregator: Callable[[list[dict[str, Any]]], dict[str, Any]],
    start_date: datetime,
    end_date: datetime,
) -> dict[str, Any]:
    """Fetch and aggregate metrics for one metric type.

    Args:
        storage: Metrics storage backend.
        metric_type: Which metric type to query.
        aggregator: Function that reduces a list of period records into a summary dict.
        start_date: Query start date.
        end_date: Query end date.

    Returns:
        Aggregated summary or empty dict when no records exist.
    """
    records = storage.get_aggregated_stats(
        metric_type,
        group_by="day",
        start_date=start_date,
        end_date=end_date,
    )
    return aggregator(records) if records else {}


def _aggregate_sum_stats(
    stats: list[dict[str, Any]],
    total_field: str,
    default: float = 0,
) -> dict[str, Any]:
    """Generic aggregator: sum a single numeric field across period records.

    Args:
        stats: List of period stat dicts.
        total_field: Name of the field to sum.
        default: Default value when the field is missing.

    Returns:
        Dict with total, daily_average and the original periods.
    """
    total = sum(stat.get(total_field, default) for stat in stats)
    return {
        total_field: total,
        "daily_average": total / len(stats) if stats else default,
        "periods": stats,
    }


def _aggregate_token_stats(stats: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate token usage statistics."""
    return _aggregate_sum_stats(stats, "total_tokens")


def _aggregate_cost_stats(stats: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate cost statistics."""
    return _aggregate_sum_stats(stats, "total_cost", default=0.0)


def _aggregate_tool_stats(stats: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate tool performance statistics."""
    total_calls = sum(stat.get("count", 0) for stat in stats)
    successful_calls = sum(stat.get("successful_calls", 0) for stat in stats)
    return {
        "total_calls": total_calls,
        "success_rate": (
            (successful_calls / total_calls * SUCCESS_RATE_MULTIPLIER) if total_calls > 0 else 0
        ),
        "periods": stats,
    }


def _aggregate_usage_stats(stats: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate usage pattern statistics."""
    return {
        "unique_commands": sum(stat.get("unique_commands", 0) for stat in stats),
        "total_tool_calls": sum(stat.get("total_tool_calls", 0) for stat in stats),
        "periods": stats,
    }


# ---------------------------------------------------------------------------
# Panel factory
# ---------------------------------------------------------------------------


def _create_metric_panel(title: str, rows: list[tuple[str, str]], color: str) -> Panel:
    """Create a Rich panel containing a two-column metric table.

    Args:
        title: Panel border title.
        rows: Sequence of (label, formatted_value) pairs.
        color: Rich colour applied to the value column and border.

    Returns:
        Configured Rich Panel.
    """
    table = Table(show_header=False, box=None)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style=color)
    for label, value in rows:
        table.add_row(label, value)
    return Panel(table, title=title, border_style=color)


class DashboardPanelFactory:
    """Factory for creating Rich dashboard panels with a uniform layout."""

    @staticmethod
    def create_panel(
        title: str,
        rows: list[tuple[str, str]],
        color: str,
    ) -> Panel:
        """Create a Rich panel containing a two-column metric table.

        Args:
            title: Panel border title.
            rows: Sequence of (label, formatted_value) pairs.
            color: Rich colour applied to the value column and border.

        Returns:
            Configured Rich Panel.
        """
        return _create_metric_panel(title, rows, color)


# ---------------------------------------------------------------------------
# Panel row builders — module-level to avoid Duplicate Code on instance methods
# ---------------------------------------------------------------------------


def _token_panel_rows(token_stats: dict[str, Any]) -> list[tuple[str, str]]:
    """Build row data for the token usage panel."""
    total = token_stats.get("total_tokens", 0)
    daily = token_stats.get("daily_average", 0)
    period_count = len(token_stats.get("periods", []))
    return [
        ("Total Tokens", f"{total:,}"),
        ("Daily Average", f"{daily:,.0f}"),
        ("Periods", str(period_count)),
    ]


def _cost_panel_rows(cost_stats: dict[str, Any]) -> list[tuple[str, str]]:
    """Build row data for the cost panel."""
    return [
        ("Total Cost", f"${cost_stats.get('total_cost', 0.0):.4f}"),
        ("Daily Average", f"${cost_stats.get('daily_average', 0.0):.4f}"),
        ("Periods", str(len(cost_stats.get("periods", [])))),
    ]


def _tool_panel_rows(tool_stats: dict[str, Any]) -> list[tuple[str, str]]:
    """Build row data for the tool performance panel."""
    periods = tool_stats.get("periods", [])
    return [
        ("Total Calls", f"{tool_stats.get('total_calls', 0):,}"),
        ("Success Rate", f"{tool_stats.get('success_rate', 0.0):.1f}%"),
        ("Periods", str(len(periods))),
    ]


def _usage_panel_rows(usage_stats: dict[str, Any]) -> list[tuple[str, str]]:
    """Build row data for the usage patterns panel."""
    return [
        ("Unique Commands", str(usage_stats.get("unique_commands", 0))),
        ("Total Tool Calls", f"{usage_stats.get('total_tool_calls', 0):,}"),
        ("Periods", str(len(usage_stats.get("periods", [])))),
    ]


def _write_token_csv_rows(writer: csv.writer, token_usage: dict[str, Any]) -> None:
    """Write token-usage rows to *writer*."""
    writer.writerow(["Total Tokens", token_usage.get("total_tokens", 0), "tokens"])
    writer.writerow(["Daily Average Tokens", token_usage.get("daily_average", 0), "tokens"])


def _write_cost_csv_rows(writer: csv.writer, costs: dict[str, Any]) -> None:
    """Write cost rows to *writer*."""
    writer.writerow(["Total Cost", costs.get("total_cost", 0), "USD"])
    writer.writerow(["Daily Average Cost", costs.get("daily_average", 0), "USD"])


def _write_tool_csv_rows(writer: csv.writer, tool_performance: dict[str, Any]) -> None:
    """Write tool-performance rows to *writer*."""
    writer.writerow(["Total Tool Calls", tool_performance.get("total_calls", 0), "calls"])
    writer.writerow(["Success Rate", tool_performance.get("success_rate", 0), "%"])


def _export_stats_to_csv(stats: dict[str, Any]) -> str:
    """Serialise summary stats as a CSV string.

    Args:
        stats: Summary statistics dict as returned by ``Dashboard.get_summary_stats``.

    Returns:
        CSV-formatted string.
    """
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Metric", "Value", "Unit"])
    if stats.get("token_usage"):
        _write_token_csv_rows(writer, stats["token_usage"])
    if stats.get("costs"):
        _write_cost_csv_rows(writer, stats["costs"])
    if stats.get("tool_performance"):
        _write_tool_csv_rows(writer, stats["tool_performance"])
    return output.getvalue()


# Layout size constants
LAYOUT_HEADER_SIZE = 3
"""Number of rows for the dashboard header panel."""

LAYOUT_STAT_PANEL_SIZE = 8
"""Number of rows for each statistics panel."""


def _build_summary_stats(
    storage: MetricsStorage,
    start_date: datetime,
    end_date: datetime,
) -> dict[str, Any]:
    """Build the full summary stats dict from storage for the given time range."""
    return {
        "time_period": {
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
        },
        "token_usage": _collect_stats(
            storage, MetricType.TOKEN_USAGE, _aggregate_token_stats, start_date, end_date,
        ),
        "costs": _collect_stats(
            storage, MetricType.COST, _aggregate_cost_stats, start_date, end_date,
        ),
        "tool_performance": _collect_stats(
            storage, MetricType.TOOL_PERFORMANCE, _aggregate_tool_stats, start_date, end_date,
        ),
        "usage_patterns": _collect_stats(
            storage, MetricType.USAGE_PATTERN, _aggregate_usage_stats, start_date, end_date,
        ),
    }


def _populate_layout_panels(
    layout: Layout,
    stats: dict[str, Any],
    factory: DashboardPanelFactory,
) -> None:
    """Update the four data panels inside a dashboard layout."""
    layout["token_stats"].update(
        factory.create_panel("Token Usage", _token_panel_rows(stats.get("token_usage", {})), "green"),
    )
    layout["cost_stats"].update(
        factory.create_panel("Costs", _cost_panel_rows(stats.get("costs", {})), "yellow"),
    )
    layout["tool_stats"].update(
        factory.create_panel("Tool Performance", _tool_panel_rows(stats.get("tool_performance", {})), "magenta"),
    )
    layout["usage_stats"].update(
        factory.create_panel("Usage Patterns", _usage_panel_rows(stats.get("usage_patterns", {})), "cyan"),
    )


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


class Dashboard:
    """Performance dashboard for monitoring Henchman-AI metrics.

    Attributes:
        metrics_storage: Storage backend for metrics data.
        refresh_interval: Interval for dashboard refresh in seconds.
        console: Rich console for output.
        live_display: Live display for real-time updates.
    """

    def __init__(
        self: Dashboard,
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
        self._panel_factory = DashboardPanelFactory()

    def display(self: Dashboard) -> None:
        """Display the dashboard interface.

        Returns:
            None
        """
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

    def refresh(self: Dashboard) -> None:
        """Refresh dashboard data.

        Returns:
            None
        """
        if self.live_display:
            self.live_display.update(self._create_layout())

    def get_summary_stats(self: Dashboard) -> dict[str, Any]:
        """Get summary statistics from metrics.

        Returns:
            Dictionary of summary statistics.
        """
        end_date = datetime.now(tz=timezone.utc)
        start_date = end_date - timedelta(days=STATS_LOOKBACK_DAYS)
        return _build_summary_stats(self.metrics_storage, start_date, end_date)

    def export_data(self: Dashboard, format: str = "json") -> str:
        """Export dashboard data in specified format.

        Args:
            format: Output format (json or csv).

        Returns:
            Exported data as string.

        Raises:
            ValueError: If the format is not supported.
        """
        stats = self.get_summary_stats()

        if format.lower() == "json":
            return json.dumps(stats, indent=2, default=str)
        if format.lower() == "csv":
            return _export_stats_to_csv(stats)
        msg = f"Unsupported format: {format}. Supported formats: json, csv"
        raise ValueError(msg)

    def close(self: Dashboard) -> None:
        """Close dashboard and release resources.

        Returns:
            None
        """
        self._running = False
        if self.live_display:
            self.live_display.stop()

    def _create_layout(self: Dashboard) -> Layout:
        """Create the dashboard layout."""
        layout = Layout()
        layout.split(
            Layout(name="header", size=LAYOUT_HEADER_SIZE),
            Layout(name="main"),
        )
        layout["main"].split_row(
            Layout(name="left", ratio=1),
            Layout(name="right", ratio=1),
        )
        layout["left"].split(
            Layout(name="token_stats", size=LAYOUT_STAT_PANEL_SIZE),
            Layout(name="cost_stats", size=LAYOUT_STAT_PANEL_SIZE),
        )
        layout["right"].split(
            Layout(name="tool_stats", size=LAYOUT_STAT_PANEL_SIZE),
            Layout(name="usage_stats", size=LAYOUT_STAT_PANEL_SIZE),
        )
        layout["header"].update(self._create_header())
        _populate_layout_panels(layout, self.get_summary_stats(), self._panel_factory)
        return layout

    def _create_header(self: Dashboard) -> Panel:
        """Create dashboard header."""
        title = Text("Henchman-AI Performance Dashboard", style="bold blue")
        timestamp_str = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        timestamp = Text(f"Last updated: {timestamp_str}", style="dim")
        header_text = Text.assemble(title, "\n", timestamp)
        return Panel(header_text, border_style="blue")
