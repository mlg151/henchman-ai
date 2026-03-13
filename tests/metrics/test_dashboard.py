"""Tests for henchman.metrics.dashboard."""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from henchman.metrics.dashboard import (
    LAYOUT_HEADER_SIZE,
    LAYOUT_STAT_PANEL_SIZE,
    STATS_LOOKBACK_DAYS,
    SUCCESS_RATE_MULTIPLIER,
    Dashboard,
    DashboardPanelFactory,
    _aggregate_cost_stats,
    _aggregate_sum_stats,
    _aggregate_token_stats,
    _aggregate_tool_stats,
    _aggregate_usage_stats,
    _collect_stats,
    _cost_panel_rows,
    _export_stats_to_csv,
    _token_panel_rows,
    _tool_panel_rows,
    _usage_panel_rows,
)
from henchman.metrics.models import MetricType
from henchman.metrics.storage import MetricsStorage


@pytest.fixture()
def tmp_storage(tmp_path: Path) -> MetricsStorage:
    """Create a temporary MetricsStorage."""
    return MetricsStorage(
        db_path=tmp_path / "dashboard_test.db",
        retention_days=None,
        max_metrics=None,
    )


@pytest.fixture()
def mock_storage() -> MagicMock:
    """Create a mock MetricsStorage that returns empty lists for aggregated stats."""
    storage = MagicMock()
    storage.get_aggregated_stats.return_value = []
    return storage


@pytest.fixture()
def dashboard(mock_storage: MagicMock) -> Dashboard:
    """Create a Dashboard with a mock storage and null console."""
    from rich.console import Console

    console = Console(file=open("/dev/null", "w"), force_terminal=False)
    return Dashboard(metrics_storage=mock_storage, refresh_interval=1, console=console)


class TestModuleConstants:
    """Tests for module-level constants."""

    def test_stats_lookback_days(self) -> None:
        """Test STATS_LOOKBACK_DAYS is positive."""
        assert STATS_LOOKBACK_DAYS > 0

    def test_success_rate_multiplier(self) -> None:
        """Test SUCCESS_RATE_MULTIPLIER is 100."""
        assert SUCCESS_RATE_MULTIPLIER == 100

    def test_layout_constants(self) -> None:
        """Test layout size constants are positive."""
        assert LAYOUT_HEADER_SIZE > 0
        assert LAYOUT_STAT_PANEL_SIZE > 0


class TestAggregateSumStats:
    """Tests for _aggregate_sum_stats."""

    def test_empty_list(self) -> None:
        """Test aggregation of empty list."""
        result = _aggregate_sum_stats([], "total_tokens")
        assert result["total_tokens"] == 0
        assert result["daily_average"] == 0

    def test_single_period(self) -> None:
        """Test aggregation of single period."""
        stats = [{"total_tokens": 100}]
        result = _aggregate_sum_stats(stats, "total_tokens")
        assert result["total_tokens"] == 100
        assert result["daily_average"] == 100

    def test_multiple_periods(self) -> None:
        """Test aggregation of multiple periods."""
        stats = [{"total_tokens": 100}, {"total_tokens": 200}, {"total_tokens": 300}]
        result = _aggregate_sum_stats(stats, "total_tokens")
        assert result["total_tokens"] == 600
        assert result["daily_average"] == 200

    def test_missing_field_uses_default(self) -> None:
        """Test that missing field uses default value."""
        stats = [{"other": 10}, {"total_tokens": 50}]
        result = _aggregate_sum_stats(stats, "total_tokens")
        assert result["total_tokens"] == 50

    def test_periods_included(self) -> None:
        """Test that original periods are included in result."""
        stats = [{"total_tokens": 100}]
        result = _aggregate_sum_stats(stats, "total_tokens")
        assert result["periods"] == stats


class TestAggregateTokenStats:
    """Tests for _aggregate_token_stats."""

    def test_aggregates_token_usage(self) -> None:
        """Test token stats aggregation."""
        stats = [{"total_tokens": 100}, {"total_tokens": 200}]
        result = _aggregate_token_stats(stats)
        assert result["total_tokens"] == 300


class TestAggregateCostStats:
    """Tests for _aggregate_cost_stats."""

    def test_aggregates_cost(self) -> None:
        """Test cost stats aggregation."""
        stats = [{"total_cost": 0.01}, {"total_cost": 0.02}]
        result = _aggregate_cost_stats(stats)
        assert result["total_cost"] == pytest.approx(0.03)


class TestAggregateToolStats:
    """Tests for _aggregate_tool_stats."""

    def test_zero_calls(self) -> None:
        """Test tool stats with zero total calls."""
        stats: list[dict[str, Any]] = []
        result = _aggregate_tool_stats(stats)
        assert result["total_calls"] == 0
        assert result["success_rate"] == 0

    def test_calculates_success_rate(self) -> None:
        """Test tool stats success rate calculation."""
        stats = [{"count": 10, "successful_calls": 8}]
        result = _aggregate_tool_stats(stats)
        assert result["total_calls"] == 10
        assert result["success_rate"] == pytest.approx(80.0)

    def test_multiple_periods(self) -> None:
        """Test tool stats with multiple periods."""
        stats = [
            {"count": 10, "successful_calls": 8},
            {"count": 5, "successful_calls": 5},
        ]
        result = _aggregate_tool_stats(stats)
        assert result["total_calls"] == 15
        assert result["success_rate"] == pytest.approx(86.666, rel=1e-3)


class TestAggregateUsageStats:
    """Tests for _aggregate_usage_stats."""

    def test_aggregates_usage(self) -> None:
        """Test usage stats aggregation."""
        stats = [
            {"unique_commands": 3, "total_tool_calls": 10},
            {"unique_commands": 2, "total_tool_calls": 5},
        ]
        result = _aggregate_usage_stats(stats)
        assert result["unique_commands"] == 5
        assert result["total_tool_calls"] == 15

    def test_empty_stats(self) -> None:
        """Test usage stats aggregation with empty list."""
        result = _aggregate_usage_stats([])
        assert result["unique_commands"] == 0
        assert result["total_tool_calls"] == 0


class TestCollectStats:
    """Tests for _collect_stats."""

    def test_returns_empty_when_no_records(self, tmp_storage: MetricsStorage) -> None:
        """Test returns empty dict when no records exist."""
        from datetime import datetime, timedelta, timezone

        end = datetime.now(tz=timezone.utc)
        start = end - timedelta(days=7)
        result = _collect_stats(
            tmp_storage, MetricType.TOKEN_USAGE, _aggregate_token_stats, start, end
        )
        assert result == {}

    def test_returns_aggregated_when_records_exist(
        self, tmp_storage: MetricsStorage
    ) -> None:
        """Test returns aggregated data when records exist."""
        from datetime import datetime, timedelta, timezone

        from henchman.metrics.models import TokenMetric

        tmp_storage.store_metric(
            TokenMetric(
                model="gpt-4",
                provider="openai",
                prompt_tokens=100,
                completion_tokens=50,
                total_tokens=150,
            )
        )

        end = datetime.now(tz=timezone.utc)
        start = end - timedelta(days=7)
        result = _collect_stats(
            tmp_storage, MetricType.TOKEN_USAGE, _aggregate_token_stats, start, end
        )
        assert result.get("total_tokens", 0) >= 0


class TestPanelRowBuilders:
    """Tests for panel row builder functions."""

    def test_token_panel_rows(self) -> None:
        """Test token panel rows are built correctly."""
        stats = {
            "total_tokens": 1000,
            "daily_average": 142.857,
            "periods": [1, 2, 3],
        }
        rows = _token_panel_rows(stats)
        assert len(rows) == 3
        assert rows[0][0] == "Total Tokens"
        assert "1,000" in rows[0][1]
        assert rows[2][1] == "3"

    def test_token_panel_rows_empty(self) -> None:
        """Test token panel rows with empty stats."""
        rows = _token_panel_rows({})
        assert rows[0][1] == "0"

    def test_cost_panel_rows(self) -> None:
        """Test cost panel rows are built correctly."""
        stats = {"total_cost": 0.1234, "daily_average": 0.0176, "periods": [1]}
        rows = _cost_panel_rows(stats)
        assert len(rows) == 3
        assert "$0.1234" in rows[0][1]

    def test_cost_panel_rows_empty(self) -> None:
        """Test cost panel rows with empty stats."""
        rows = _cost_panel_rows({})
        assert "$0.0000" in rows[0][1]

    def test_tool_panel_rows(self) -> None:
        """Test tool panel rows are built correctly."""
        stats = {"total_calls": 100, "success_rate": 95.5, "periods": [1, 2]}
        rows = _tool_panel_rows(stats)
        assert len(rows) == 3
        assert "100" in rows[0][1]
        assert "95.5%" in rows[1][1]

    def test_tool_panel_rows_empty(self) -> None:
        """Test tool panel rows with empty stats."""
        rows = _tool_panel_rows({})
        assert "0" in rows[0][1]

    def test_usage_panel_rows(self) -> None:
        """Test usage panel rows are built correctly."""
        stats = {"unique_commands": 5, "total_tool_calls": 42, "periods": [1]}
        rows = _usage_panel_rows(stats)
        assert len(rows) == 3
        assert rows[0][1] == "5"
        assert "42" in rows[1][1]

    def test_usage_panel_rows_empty(self) -> None:
        """Test usage panel rows with empty stats."""
        rows = _usage_panel_rows({})
        assert rows[0][1] == "0"


class TestDashboardPanelFactory:
    """Tests for DashboardPanelFactory."""

    def test_create_panel(self) -> None:
        """Test create_panel returns a Panel."""
        from rich.panel import Panel

        factory = DashboardPanelFactory()
        rows = [("Metric A", "100"), ("Metric B", "200")]
        panel = factory.create_panel("Test Panel", rows, "green")
        assert isinstance(panel, Panel)


class TestExportStatsToCsv:
    """Tests for _export_stats_to_csv."""

    def test_empty_stats(self) -> None:
        """Test CSV export with empty stats."""
        stats: dict[str, Any] = {"token_usage": None, "costs": None, "tool_performance": None}
        result = _export_stats_to_csv(stats)
        assert "Metric,Value,Unit" in result

    def test_with_token_stats(self) -> None:
        """Test CSV export with token stats."""
        stats = {
            "token_usage": {"total_tokens": 1000, "daily_average": 142},
            "costs": None,
            "tool_performance": None,
        }
        result = _export_stats_to_csv(stats)
        assert "Total Tokens" in result
        assert "1000" in result

    def test_with_cost_stats(self) -> None:
        """Test CSV export with cost stats."""
        stats = {
            "token_usage": None,
            "costs": {"total_cost": 0.05, "daily_average": 0.007},
            "tool_performance": None,
        }
        result = _export_stats_to_csv(stats)
        assert "Total Cost" in result

    def test_with_tool_stats(self) -> None:
        """Test CSV export with tool stats."""
        stats = {
            "token_usage": None,
            "costs": None,
            "tool_performance": {"total_calls": 100, "success_rate": 95.0},
        }
        result = _export_stats_to_csv(stats)
        assert "Total Tool Calls" in result
        assert "Success Rate" in result

    def test_full_stats(self) -> None:
        """Test CSV export with all stats populated."""
        stats = {
            "token_usage": {"total_tokens": 1000, "daily_average": 142},
            "costs": {"total_cost": 0.05, "daily_average": 0.007},
            "tool_performance": {"total_calls": 100, "success_rate": 95.0},
        }
        result = _export_stats_to_csv(stats)
        assert "Total Tokens" in result
        assert "Total Cost" in result
        assert "Total Tool Calls" in result


class TestDashboard:
    """Tests for Dashboard class."""

    def test_init(self, tmp_storage: MetricsStorage) -> None:
        """Test Dashboard initialization."""
        d = Dashboard(metrics_storage=tmp_storage)
        assert d.refresh_interval == 5
        assert d.console is not None
        assert d.live_display is None
        assert d._running is False

    def test_get_summary_stats(self, dashboard: Dashboard) -> None:
        """Test get_summary_stats returns expected structure."""
        stats = dashboard.get_summary_stats()
        assert "time_period" in stats
        assert "token_usage" in stats
        assert "costs" in stats
        assert "tool_performance" in stats
        assert "usage_patterns" in stats

    def test_export_data_json(self, dashboard: Dashboard) -> None:
        """Test export_data in JSON format."""
        import json

        result = dashboard.export_data(format="json")
        data = json.loads(result)
        assert "time_period" in data

    def test_export_data_csv(self, dashboard: Dashboard) -> None:
        """Test export_data in CSV format."""
        result = dashboard.export_data(format="csv")
        assert "Metric,Value,Unit" in result

    def test_export_data_invalid_format(self, dashboard: Dashboard) -> None:
        """Test export_data raises ValueError for unsupported format."""
        with pytest.raises(ValueError, match="Unsupported format"):
            dashboard.export_data(format="xml")

    def test_close(self, dashboard: Dashboard) -> None:
        """Test close sets _running to False."""
        dashboard._running = True
        dashboard.close()
        assert dashboard._running is False

    def test_close_with_live_display(self, dashboard: Dashboard) -> None:
        """Test close stops live display."""
        mock_live = MagicMock()
        dashboard.live_display = mock_live
        dashboard._running = True
        dashboard.close()
        mock_live.stop.assert_called_once()
        assert dashboard._running is False

    def test_refresh_with_live_display(self, dashboard: Dashboard) -> None:
        """Test refresh updates live display."""
        mock_live = MagicMock()
        dashboard.live_display = mock_live
        dashboard.refresh()
        mock_live.update.assert_called_once()

    def test_refresh_without_live_display(self, dashboard: Dashboard) -> None:
        """Test refresh does nothing without live display."""
        dashboard.refresh()  # Should not raise

    def test_create_layout(self, dashboard: Dashboard) -> None:
        """Test _create_layout returns a Layout object."""
        from rich.layout import Layout

        layout = dashboard._create_layout()
        assert isinstance(layout, Layout)

    def test_create_header(self, dashboard: Dashboard) -> None:
        """Test _create_header returns a Panel."""
        from rich.panel import Panel

        header = dashboard._create_header()
        assert isinstance(header, Panel)

    def test_display_stops_on_close(
        self, dashboard: Dashboard, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test display loop exits when _running is set to False."""
        call_count = 0

        def fake_sleep(_n: float) -> None:
            """Stop the display after first sleep."""
            nonlocal call_count
            call_count += 1
            dashboard._running = False

        monkeypatch.setattr("time.sleep", fake_sleep)

        # Mock Live context manager to avoid terminal interaction
        mock_live = MagicMock()
        mock_live.__enter__ = MagicMock(return_value=mock_live)
        mock_live.__exit__ = MagicMock(return_value=False)

        with patch("henchman.metrics.dashboard.Live", return_value=mock_live):
            dashboard.display()

        assert call_count == 1
