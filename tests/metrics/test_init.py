"""Tests for henchman.metrics.__init__ (public API)."""

from henchman.metrics import (
    CostData,
    CostMetric,
    Dashboard,
    MetricsCollector,
    MetricsExporter,
    MetricsStorage,
    MetricType,
    PerformanceEventData,
    PerformanceMetric,
    TokenMetric,
    TokenUsageData,
    ToolMetric,
    UsageMetric,
)


class TestMetricsPublicApi:
    """Tests for the public API exposed by henchman.metrics."""

    def test_all_exports_importable(self) -> None:
        """Test that all expected names can be imported from the package."""
        assert CostData is not None
        assert CostMetric is not None
        assert Dashboard is not None
        assert MetricType is not None
        assert MetricsCollector is not None
        assert MetricsExporter is not None
        assert MetricsStorage is not None
        assert PerformanceEventData is not None
        assert PerformanceMetric is not None
        assert TokenMetric is not None
        assert TokenUsageData is not None
        assert ToolMetric is not None
        assert UsageMetric is not None

    def test_all_in_dunder_all(self) -> None:
        """Test that __all__ contains the expected names."""
        import henchman.metrics as m

        expected = {
            "CostData",
            "CostMetric",
            "Dashboard",
            "MetricType",
            "MetricsCollector",
            "MetricsExporter",
            "MetricsStorage",
            "PerformanceEventData",
            "PerformanceMetric",
            "TokenMetric",
            "TokenUsageData",
            "ToolMetric",
            "UsageMetric",
        }
        assert expected == set(m.__all__)
