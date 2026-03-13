"""Tests for henchman.metrics.storage."""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from henchman.metrics.models import (
    CostMetric,
    MetricType,
    PerformanceMetric,
    TokenMetric,
    ToolMetric,
    UsageMetric,
)
from henchman.metrics.storage import (
    DatabaseSchemaManager,
    MetricsAggregator,
    MetricsQueryParams,
    MetricsStorage,
    _create_base_metric_dict,
)


@pytest.fixture()
def tmp_storage(tmp_path: Path) -> MetricsStorage:
    """Create a MetricsStorage instance using a temporary database."""
    return MetricsStorage(
        db_path=tmp_path / "test_metrics.db",
        retention_days=None,
        max_metrics=None,
    )


@pytest.fixture()
def storage_with_data(tmp_storage: MetricsStorage) -> MetricsStorage:
    """Storage pre-populated with various metric types."""
    token = TokenMetric(
        session_id="s1",
        agent_id="a1",
        model="gpt-4",
        provider="openai",
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
    )
    cost = CostMetric(
        session_id="s1",
        agent_id="a1",
        model="gpt-4",
        provider="openai",
        prompt_cost=0.01,
        completion_cost=0.02,
        total_cost=0.03,
    )
    tool = ToolMetric(
        session_id="s1",
        tool_name="read_file",
        tool_category="read",
        execution_time_ms=100.0,
        success=True,
    )
    usage = UsageMetric(
        session_id="s1",
        command="chat",
        duration_ms=5000.0,
        tool_calls_count=3,
    )
    perf = PerformanceMetric(
        session_id="s1",
        event_type="tool_execution",
        latency_ms=50.0,
    )
    for m in [token, cost, tool, usage, perf]:
        tmp_storage.store_metric(m)
    return tmp_storage


class TestCreateBaseMetricDict:
    """Tests for _create_base_metric_dict helper."""

    def test_base_fields(self) -> None:
        """Test that base fields are populated correctly."""
        m = TokenMetric(session_id="s1", agent_id="a1", user_id="u1")
        result = _create_base_metric_dict(m)
        assert result["id"] == m.id
        assert result["session_id"] == "s1"
        assert result["agent_id"] == "a1"
        assert result["user_id"] == "u1"
        assert result["metric_type"] == "token_usage"

    def test_metadata_serialized(self) -> None:
        """Test metadata dict is JSON-serialized."""
        import json

        m = TokenMetric(metadata={"foo": "bar"})
        result = _create_base_metric_dict(m)
        assert result["metadata"] == json.dumps({"foo": "bar"})

    def test_empty_metadata_is_none(self) -> None:
        """Test empty metadata produces None in dict."""
        m = TokenMetric()
        result = _create_base_metric_dict(m)
        assert result["metadata"] is None


class TestMetricsQueryParams:
    """Tests for MetricsQueryParams.build_query."""

    def test_no_filters(self) -> None:
        """Test query with no filters."""
        params = MetricsQueryParams()
        query, vals = params.build_query()
        assert "WHERE 1=1" in query
        assert "ORDER BY timestamp DESC" in query
        assert vals == []

    def test_metric_type_filter(self) -> None:
        """Test query with metric_type filter."""
        params = MetricsQueryParams(metric_type=MetricType.TOKEN_USAGE)
        query, vals = params.build_query()
        assert "metric_type = ?" in query
        assert "token_usage" in vals

    def test_session_id_filter(self) -> None:
        """Test query with session_id filter."""
        params = MetricsQueryParams(session_id="sess-1")
        query, vals = params.build_query()
        assert "session_id = ?" in query
        assert "sess-1" in vals

    def test_agent_id_filter(self) -> None:
        """Test query with agent_id filter."""
        params = MetricsQueryParams(agent_id="agent-1")
        query, vals = params.build_query()
        assert "agent_id = ?" in query
        assert "agent-1" in vals

    def test_date_filters(self) -> None:
        """Test query with start/end date filters."""
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 12, 31, tzinfo=timezone.utc)
        params = MetricsQueryParams(start_date=start, end_date=end)
        query, vals = params.build_query()
        assert "timestamp >=" in query
        assert "timestamp <=" in query
        assert start.isoformat() in vals
        assert end.isoformat() in vals

    def test_limit_filter(self) -> None:
        """Test query with limit."""
        params = MetricsQueryParams(limit=10)
        query, vals = params.build_query()
        assert "LIMIT ?" in query
        assert 10 in vals

    def test_all_filters(self) -> None:
        """Test query with all filters set."""
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 12, 31, tzinfo=timezone.utc)
        params = MetricsQueryParams(
            metric_type=MetricType.COST,
            session_id="s1",
            agent_id="a1",
            start_date=start,
            end_date=end,
            limit=5,
        )
        query, vals = params.build_query()
        # metric_type, session_id, agent_id, start_date, end_date, limit = 6
        assert len(vals) == 6
        assert 5 in vals


class TestDatabaseSchemaManager:
    """Tests for DatabaseSchemaManager."""

    def test_create_tables_and_indexes(self, tmp_path: Path) -> None:
        """Test that tables and indexes are created."""
        db_path = tmp_path / "schema_test.db"
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        manager = DatabaseSchemaManager()
        manager.create_metrics_table(cursor)
        manager.create_indexes(cursor)
        conn.commit()

        # Verify table was created
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='metrics'")
        assert cursor.fetchone() is not None

        # Verify indexes were created
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
        index_names = {row["name"] for row in cursor.fetchall()}
        assert "idx_metric_type" in index_names
        assert "idx_timestamp" in index_names
        assert "idx_session_id" in index_names
        conn.close()


class TestMetricsStorage:
    """Tests for MetricsStorage."""

    def test_init_with_path(self, tmp_path: Path) -> None:
        """Test initialization with explicit path."""
        db_path = tmp_path / "test.db"
        storage = MetricsStorage(db_path=db_path, retention_days=7, max_metrics=1000)
        assert storage.db_path == db_path
        assert storage.retention_days == 7
        assert storage.max_metrics == 1000
        assert db_path.exists()

    def test_init_with_string_path(self, tmp_path: Path) -> None:
        """Test initialization with string path."""
        db_path = str(tmp_path / "string_test.db")
        storage = MetricsStorage(db_path=db_path)
        assert isinstance(storage.db_path, Path)

    def test_store_and_retrieve_token_metric(self, tmp_storage: MetricsStorage) -> None:
        """Test storing and retrieving a TokenMetric."""
        metric = TokenMetric(
            session_id="s1",
            model="gpt-4",
            provider="openai",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
        )
        tmp_storage.store_metric(metric)
        results = tmp_storage.get_metrics(metric_type=MetricType.TOKEN_USAGE)
        assert len(results) == 1
        assert results[0]["model"] == "gpt-4"
        assert results[0]["total_tokens"] == 150

    def test_store_cost_metric(self, tmp_storage: MetricsStorage) -> None:
        """Test storing a CostMetric."""
        metric = CostMetric(
            model="gpt-4",
            provider="openai",
            prompt_cost=0.01,
            completion_cost=0.02,
            total_cost=0.03,
        )
        tmp_storage.store_metric(metric)
        results = tmp_storage.get_metrics(metric_type=MetricType.COST)
        assert len(results) == 1
        assert results[0]["total_cost"] == pytest.approx(0.03)

    def test_store_tool_metric(self, tmp_storage: MetricsStorage) -> None:
        """Test storing a ToolMetric."""
        metric = ToolMetric(
            tool_name="read_file",
            tool_category="read",
            execution_time_ms=100.0,
            success=True,
        )
        tmp_storage.store_metric(metric)
        results = tmp_storage.get_metrics(metric_type=MetricType.TOOL_PERFORMANCE)
        assert len(results) == 1
        assert results[0]["tool_name"] == "read_file"

    def test_store_usage_metric(self, tmp_storage: MetricsStorage) -> None:
        """Test storing a UsageMetric."""
        metric = UsageMetric(
            command="chat",
            duration_ms=5000.0,
            tool_calls_count=3,
        )
        tmp_storage.store_metric(metric)
        results = tmp_storage.get_metrics(metric_type=MetricType.USAGE_PATTERN)
        assert len(results) == 1
        assert results[0]["command"] == "chat"

    def test_store_performance_metric(self, tmp_storage: MetricsStorage) -> None:
        """Test storing a PerformanceMetric."""
        metric = PerformanceMetric(
            event_type="tool_execution",
            latency_ms=50.0,
            memory_usage_mb=256.0,
        )
        tmp_storage.store_metric(metric)
        results = tmp_storage.get_metrics(metric_type=MetricType.PERFORMANCE)
        assert len(results) == 1
        assert results[0]["event_type"] == "tool_execution"

    def test_get_metrics_session_filter(self, storage_with_data: MetricsStorage) -> None:
        """Test filtering metrics by session_id."""
        results = storage_with_data.get_metrics(session_id="s1")
        assert len(results) >= 1
        for r in results:
            assert r["session_id"] == "s1"

    def test_get_metrics_agent_filter(self, storage_with_data: MetricsStorage) -> None:
        """Test filtering metrics by agent_id."""
        results = storage_with_data.get_metrics(agent_id="a1")
        assert len(results) >= 1

    def test_get_metrics_date_filter(self, storage_with_data: MetricsStorage) -> None:
        """Test filtering metrics by date range."""
        start = datetime(2020, 1, 1, tzinfo=timezone.utc)
        end = datetime(2030, 1, 1, tzinfo=timezone.utc)
        results = storage_with_data.get_metrics(start_date=start, end_date=end)
        assert len(results) >= 1

    def test_get_metrics_limit(self, storage_with_data: MetricsStorage) -> None:
        """Test limiting metrics results."""
        results = storage_with_data.get_metrics(limit=2)
        assert len(results) == 2

    def test_get_metrics_with_params(self, storage_with_data: MetricsStorage) -> None:
        """Test get_metrics_with_params method."""
        params = MetricsQueryParams(session_id="s1", limit=3)
        results = storage_with_data.get_metrics_with_params(params)
        assert len(results) <= 3

    def test_clear_metrics(self, storage_with_data: MetricsStorage) -> None:
        """Test clearing all metrics."""
        storage_with_data.clear_metrics()
        results = storage_with_data.get_metrics()
        assert len(results) == 0

    def test_get_database_size(self, tmp_storage: MetricsStorage) -> None:
        """Test getting database size."""
        size = tmp_storage.get_database_size()
        assert size > 0

    def test_get_database_size_nonexistent(self, tmp_path: Path) -> None:
        """Test database size when file doesn't exist after removal."""
        storage = MetricsStorage(db_path=tmp_path / "gone.db")
        storage.db_path.unlink()
        assert storage.get_database_size() == 0

    def test_max_metrics_limit(self, tmp_path: Path) -> None:
        """Test that max_metrics limit is respected."""
        storage = MetricsStorage(
            db_path=tmp_path / "limited.db",
            max_metrics=2,
            retention_days=None,
        )
        for _ in range(5):
            storage.store_metric(TokenMetric())

        results = storage.get_metrics()
        assert len(results) <= 2

    def test_retention_cleanup(self, tmp_path: Path) -> None:
        """Test that old metrics are cleaned up."""
        storage = MetricsStorage(
            db_path=tmp_path / "retain.db",
            retention_days=1,
            max_metrics=None,
        )
        # Insert a metric with old timestamp directly
        old_metric = TokenMetric()
        storage.store_metric(old_metric)

        # Manually update timestamp to be old
        with storage._get_connection() as conn:
            conn.execute(
                "UPDATE metrics SET timestamp = '2000-01-01T00:00:00' WHERE id = ?",
                (old_metric.id,),
            )
            conn.commit()

        # Store another metric to trigger cleanup
        storage.store_metric(TokenMetric())

        results = storage.get_metrics()
        # Old metric should be cleaned up
        ids = [r["id"] for r in results]
        assert old_metric.id not in ids

    def test_get_aggregated_stats_token(self, storage_with_data: MetricsStorage) -> None:
        """Test aggregated stats for token usage."""
        results = storage_with_data.get_aggregated_stats(
            MetricType.TOKEN_USAGE,
            group_by="day",
        )
        assert isinstance(results, list)

    def test_get_aggregated_stats_cost(self, storage_with_data: MetricsStorage) -> None:
        """Test aggregated stats for cost."""
        results = storage_with_data.get_aggregated_stats(MetricType.COST, group_by="month")
        assert isinstance(results, list)

    def test_get_aggregated_stats_tool(self, storage_with_data: MetricsStorage) -> None:
        """Test aggregated stats for tool performance."""
        results = storage_with_data.get_aggregated_stats(
            MetricType.TOOL_PERFORMANCE, group_by="week"
        )
        assert isinstance(results, list)

    def test_get_aggregated_stats_usage(self, storage_with_data: MetricsStorage) -> None:
        """Test aggregated stats for usage patterns."""
        results = storage_with_data.get_aggregated_stats(
            MetricType.USAGE_PATTERN, group_by="hour"
        )
        assert isinstance(results, list)

    def test_get_aggregated_stats_performance(self, storage_with_data: MetricsStorage) -> None:
        """Test aggregated stats for performance metrics."""
        results = storage_with_data.get_aggregated_stats(
            MetricType.PERFORMANCE, group_by="day"
        )
        assert isinstance(results, list)

    def test_get_aggregated_stats_with_dates(self, storage_with_data: MetricsStorage) -> None:
        """Test aggregated stats with date range."""
        start = datetime(2020, 1, 1, tzinfo=timezone.utc)
        end = datetime(2030, 1, 1, tzinfo=timezone.utc)
        results = storage_with_data.get_aggregated_stats(
            MetricType.TOKEN_USAGE,
            group_by="day",
            start_date=start,
            end_date=end,
        )
        assert isinstance(results, list)

    def test_get_session_metrics(self, storage_with_data: MetricsStorage) -> None:
        """Test getting session-specific metrics."""
        result = storage_with_data.get_session_metrics("s1")
        assert result["session_id"] == "s1"
        assert "token_usage" in result
        assert "cost" in result
        assert "tool_performance" in result
        assert "usage_patterns" in result

    def test_get_session_metrics_empty(self, tmp_storage: MetricsStorage) -> None:
        """Test getting session metrics for non-existent session returns empty sub-dicts."""
        result = tmp_storage.get_session_metrics("nonexistent")
        assert result["session_id"] == "nonexistent"
        # Returns dict (possibly with None values) or empty dict
        assert isinstance(result["token_usage"], dict)

    def test_default_db_path(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Test initialization with default db_path using appdirs."""
        import appdirs

        monkeypatch.setattr(appdirs, "user_data_dir", lambda _: str(tmp_path))
        storage = MetricsStorage(db_path=None)
        assert storage.db_path.exists()


class TestMetricsAggregator:
    """Tests for MetricsAggregator."""

    def test_invalid_group_by_raises(self, tmp_storage: MetricsStorage) -> None:
        """Test that invalid group_by raises ValueError."""
        aggregator = MetricsAggregator(tmp_storage)
        with pytest.raises(ValueError, match="Invalid group_by"):
            aggregator.get_aggregated_stats(MetricType.TOKEN_USAGE, group_by="decade")

    def test_valid_group_by_values(self, tmp_storage: MetricsStorage) -> None:
        """Test all valid group_by values work."""
        aggregator = MetricsAggregator(tmp_storage)
        for group_by in ["hour", "day", "week", "month"]:
            result = aggregator.get_aggregated_stats(MetricType.TOKEN_USAGE, group_by=group_by)
            assert isinstance(result, list)


class TestSessionMetricsAnalyzer:
    """Tests for SessionMetricsAnalyzer."""

    def test_get_session_metrics_with_tool_failure(self, tmp_path: Path) -> None:
        """Test session metrics include failed tool metrics."""
        storage = MetricsStorage(
            db_path=tmp_path / "analyzer.db",
            retention_days=None,
            max_metrics=None,
        )
        storage.store_metric(
            ToolMetric(
                session_id="s2",
                tool_name="shell",
                success=False,
                error_type="TimeoutError",
            )
        )
        result = storage.get_session_metrics("s2")
        assert result["session_id"] == "s2"

    def test_usage_patterns_returned(self, tmp_path: Path) -> None:
        """Test usage patterns are returned for a session."""
        storage = MetricsStorage(
            db_path=tmp_path / "patterns.db",
            retention_days=None,
            max_metrics=None,
        )
        for _ in range(3):
            storage.store_metric(
                UsageMetric(session_id="s3", command="chat", tool_calls_count=2)
            )
        result = storage.get_session_metrics("s3")
        assert len(result["usage_patterns"]) == 1
        assert result["usage_patterns"][0]["command"] == "chat"
        assert result["usage_patterns"][0]["execution_count"] == 3

    def test_get_session_aggregated_metrics_unknown_type(
        self, tmp_path: Path
    ) -> None:
        """Test _get_session_aggregated_metrics returns None for unknown metric type."""
        storage = MetricsStorage(
            db_path=tmp_path / "unknown.db",
            retention_days=None,
            max_metrics=None,
        )
        analyzer = storage.session_analyzer
        with storage._get_connection() as conn:
            cursor = conn.cursor()
            result = analyzer._get_session_aggregated_metrics(
                cursor, "s1", "unknown_type"
            )
        assert result is None

    def test_store_base_metric_no_type_match(self, tmp_path: Path) -> None:
        """Test storing a BaseMetric (no specific field mapping) works."""
        from henchman.metrics.models import BaseMetric

        storage = MetricsStorage(
            db_path=tmp_path / "base.db",
            retention_days=None,
            max_metrics=None,
        )
        # BaseMetric won't match any entry in _FIELD_MAPPINGS, hitting the
        # no-break path in _add_metric_specific_fields
        metric = BaseMetric(session_id="s1")
        storage.store_metric(metric)
        results = storage.get_metrics()
        assert len(results) == 1

    def test_should_store_metric_count_result_none(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test _should_store_metric returns True when COUNT query returns None."""
        storage = MetricsStorage(
            db_path=tmp_path / "mock_count.db",
            retention_days=None,
            max_metrics=10,
        )
        # Monkeypatch fetchone to return None to hit line 729
        original_get_connection = storage._get_connection

        from collections.abc import Generator
        from contextlib import contextmanager

        @contextmanager
        def mock_get_connection() -> Generator:
            """Mock connection with cursor that returns None for COUNT."""
            conn = sqlite3.connect(str(storage.db_path))
            conn.row_factory = sqlite3.Row
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = None
            conn_mock = MagicMock()
            conn_mock.cursor.return_value = mock_cursor
            try:
                yield conn_mock
            finally:
                conn.close()

        monkeypatch.setattr(storage, "_get_connection", mock_get_connection)
        result = storage._should_store_metric()
        assert result is True
