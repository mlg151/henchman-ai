"""Metrics storage backend for Henchman-AI.

Provides persistent storage for metrics with configurable retention.
"""

import json
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from henchman.metrics.models import (
    BaseMetric,
    CostMetric,
    MetricType,
    PerformanceMetric,
    TokenMetric,
    ToolMetric,
    UsageMetric,
)


@dataclass
class MetricsQueryParams:
    """Parameters for querying metrics with filtering options."""

    metric_type: MetricType | None = None
    session_id: str | None = None
    agent_id: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    limit: int | None = None


class SessionMetricsAnalyzer:
    """Analyzes metrics for specific sessions."""

    def __init__(self, storage: "MetricsStorage") -> None:
        """Initialize analyzer with storage reference.

        Args:
            storage: MetricsStorage instance to query.
        """
        self.storage = storage

    def get_session_metrics(self, session_id: str) -> dict[str, Any]:
        """Get all metrics for a specific session.

        Args:
            session_id: Session identifier.

        Returns:
            Dictionary with session metrics summary.
        """
        with self.storage._get_connection() as conn:
            cursor = conn.cursor()

            token_stats = self._get_session_metric_by_type(cursor, session_id, "token_usage")
            cost_stats = self._get_session_metric_by_type(cursor, session_id, "cost")
            tool_stats = self._get_session_metric_by_type(cursor, session_id, "tool_performance")
            usage_patterns = self._get_session_usage_patterns(cursor, session_id)

        return {
            "session_id": session_id,
            "token_usage": dict(token_stats) if token_stats else {},
            "cost": dict(cost_stats) if cost_stats else {},
            "tool_performance": dict(tool_stats) if tool_stats else {},
            "usage_patterns": [dict(row) for row in usage_patterns],
        }

    def _get_session_metrics_by_type(
        self, cursor: sqlite3.Cursor, session_id: str, metric_type: str, select_clause: str,
    ) -> tuple[Any, ...] | None:
        """Get session metrics by type with parameterized query.

        Args:
            cursor: Database cursor.
            session_id: Session identifier.
            metric_type: Type of metric to query.
            select_clause: SELECT clause for the specific metric type.

        Returns:
            Query result row or None.
        """
        query = f"""
            SELECT {select_clause}
            FROM metrics
            WHERE session_id = ? AND metric_type = ?
        """
        cursor.execute(query, (session_id, metric_type))
        return cursor.fetchone()  # type: ignore[no-any-return]

    def _get_session_aggregated_metrics(
        self, cursor: sqlite3.Cursor, session_id: str, metric_type: str,
    ) -> tuple[Any, ...] | None:
        """Get aggregated metrics for a session by metric type.

        Args:
            cursor: Database cursor.
            session_id: Session identifier.
            metric_type: Type of metric to query.

        Returns:
            Query result row or None.
        """
        # Define select clauses for each metric type
        select_clauses = {
            "token_usage": """
                SUM(prompt_tokens) as total_prompt_tokens,
                SUM(completion_tokens) as total_completion_tokens,
                SUM(total_tokens) as total_tokens,
                COUNT(DISTINCT model) as unique_models
            """,
            "cost": """
                SUM(prompt_cost) as total_prompt_cost,
                SUM(completion_cost) as total_completion_cost,
                SUM(total_cost) as total_cost
            """,
            "tool_performance": """
                COUNT(*) as total_tool_calls,
                COUNT(CASE WHEN success = 1 THEN 1 END) as successful_calls,
                COUNT(CASE WHEN success = 0 THEN 1 END) as failed_calls,
                AVG(execution_time_ms) as avg_execution_time
            """,
        }

        if metric_type not in select_clauses:
            return None

        return self._get_session_metrics_by_type(
            cursor, session_id, metric_type, select_clauses[metric_type],
        )

    def _get_session_metric_by_type(
        self, cursor: sqlite3.Cursor, session_id: str, metric_type: str,
    ) -> tuple[Any, ...] | None:
        """Get session metrics by type.

        Args:
            cursor: Database cursor.
            session_id: Session identifier.
            metric_type: Type of metric to query ('token_usage', 'cost', or 'tool_performance').

        Returns:
            Query result row or None.
        """
        return self._get_session_aggregated_metrics(cursor, session_id, metric_type)

    def _get_session_usage_patterns(
        self, cursor: sqlite3.Cursor, session_id: str,
    ) -> list[sqlite3.Row]:
        """Get usage patterns for a session."""
        cursor.execute(
            """
            SELECT
                command,
                COUNT(*) as execution_count,
                AVG(duration_ms) as avg_duration,
                SUM(tool_calls_count) as total_tool_calls
            FROM metrics
            WHERE session_id = ? AND metric_type = 'usage_pattern'
            GROUP BY command
            ORDER BY execution_count DESC
        """,
            (session_id,),
        )
        return cursor.fetchall()


class DatabaseSchemaManager:
    """Manages database schema creation and indexing."""

    # SQL column definitions as constants for better maintainability
    _METRICS_TABLE_COLUMNS = [
        "id TEXT PRIMARY KEY",
        "timestamp DATETIME NOT NULL",
        "metric_type TEXT NOT NULL",
        "session_id TEXT",
        "agent_id TEXT",
        "user_id TEXT",
        "model TEXT",
        "provider TEXT",
        "prompt_tokens INTEGER",
        "completion_tokens INTEGER",
        "total_tokens INTEGER",
        "cached_tokens INTEGER",
        "token_limit INTEGER",
        "token_ratio REAL",
        "prompt_cost REAL",
        "completion_cost REAL",
        "total_cost REAL",
        "currency TEXT",
        "cost_per_token REAL",
        "estimated_cost REAL",
        "tool_name TEXT",
        "tool_category TEXT",
        "execution_time_ms REAL",
        "success BOOLEAN",
        "error_type TEXT",
        "input_size INTEGER",
        "output_size INTEGER",
        "cache_hit BOOLEAN",
        "command TEXT",
        "subcommand TEXT",
        "workflow_type TEXT",
        "duration_ms REAL",
        "tool_calls_count INTEGER",
        "agent_switches INTEGER",
        "context_compactions INTEGER",
        "user_feedback TEXT",
        "event_type TEXT",
        "latency_ms REAL",
        "memory_usage_mb REAL",
        "cpu_usage_percent REAL",
        "concurrent_operations INTEGER",
        "queue_depth INTEGER",
        "metadata TEXT",
    ]

    def create_metrics_table(self, cursor: sqlite3.Cursor) -> None:
        """Create the main metrics table with all columns."""
        columns_sql = ",\n                ".join(self._METRICS_TABLE_COLUMNS)
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS metrics (
                {columns_sql}
            )
        """)

    def create_indexes(self, cursor: sqlite3.Cursor) -> None:
        """Create indexes for common queries."""
        indexes = [
            ("idx_metric_type", "metric_type"),
            ("idx_timestamp", "timestamp"),
            ("idx_session_id", "session_id"),
            ("idx_agent_id", "agent_id"),
            ("idx_model", "model"),
            ("idx_tool_name", "tool_name"),
            ("idx_command", "command"),
        ]

        for index_name, column_name in indexes:
            cursor.execute(f"CREATE INDEX IF NOT EXISTS {index_name} ON metrics({column_name})")


class MetricsAggregator:
    """Handles aggregation and statistical analysis of metrics."""

    def __init__(self, storage: "MetricsStorage") -> None:
        """Initialize aggregator with storage reference.

        Args:
            storage: MetricsStorage instance to query.
        """
        self.storage = storage

    def get_aggregated_stats(
        self,
        metric_type: MetricType,
        group_by: str = "day",
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Get aggregated statistics for metrics.

        Args:
            metric_type: Type of metrics to aggregate.
            group_by: Grouping interval ('hour', 'day', 'week', 'month').
            start_date: Start date for aggregation.
            end_date: End date for aggregation.

        Returns:
            List of aggregated statistics.
        """
        time_format = self._get_time_format_for_grouping(group_by)
        query = self._build_aggregation_query(metric_type, time_format)
        params = self._build_aggregation_params(metric_type, start_date, end_date)

        return self._execute_aggregation_query(query, params)

    def _get_time_format_for_grouping(self, group_by: str) -> str:
        """Get SQL time format string for the specified grouping interval.

        Args:
            group_by: Grouping interval ('hour', 'day', 'week', 'month').

        Returns:
            SQL time format string.

        Raises:
            ValueError: If group_by is not a valid grouping interval.
        """
        time_formats = {
            "hour": "strftime('%Y-%m-%d %H:00:00', timestamp)",
            "day": "date(timestamp)",
            "week": "strftime('%Y-W%W', timestamp)",
            "month": "strftime('%Y-%m', timestamp)",
        }

        if group_by not in time_formats:
            msg = f"Invalid group_by: {group_by}. Must be one of: {list(time_formats.keys())}"
            raise ValueError(
                msg,
            )

        return time_formats[group_by]

    # Metric aggregation definitions as a class constant
    _METRIC_AGGREGATIONS: dict[MetricType, str] = {
        MetricType.TOKEN_USAGE: """
            SUM(prompt_tokens) as total_prompt_tokens,
            SUM(completion_tokens) as total_completion_tokens,
            SUM(total_tokens) as total_tokens,
            AVG(token_ratio) as avg_token_ratio
        """,
        MetricType.COST: """
            SUM(prompt_cost) as total_prompt_cost,
            SUM(completion_cost) as total_completion_cost,
            SUM(total_cost) as total_cost,
            AVG(cost_per_token) as avg_cost_per_token
        """,
        MetricType.TOOL_PERFORMANCE: """
            COUNT(CASE WHEN success = 1 THEN 1 END) as successful_calls,
            COUNT(CASE WHEN success = 0 THEN 1 END) as failed_calls,
            AVG(execution_time_ms) as avg_execution_time,
            SUM(input_size) as total_input_size,
            SUM(output_size) as total_output_size
        """,
        MetricType.USAGE_PATTERN: """
            COUNT(DISTINCT command) as unique_commands,
            SUM(tool_calls_count) as total_tool_calls,
            SUM(agent_switches) as total_agent_switches,
            SUM(context_compactions) as total_context_compactions,
            AVG(duration_ms) as avg_duration
        """,
    }

    def _build_aggregation_query(self, metric_type: MetricType, time_format: str) -> str:
        """Build the SQL query for metric aggregation.

        Args:
            metric_type: Type of metric to aggregate.
            time_format: SQL time format string for grouping.

        Returns:
            SQL query string for aggregation.
        """
        base_query = f"""
            SELECT
                {time_format} as period,
                COUNT(*) as count
        """

        aggregation_clause = self._METRIC_AGGREGATIONS.get(metric_type, "")
        if aggregation_clause:
            base_query += f",{aggregation_clause}"

        base_query += """
            FROM metrics
            WHERE metric_type = ?
        """

        return base_query

    def _build_aggregation_params(
        self,
        metric_type: MetricType,
        start_date: datetime | None,
        end_date: datetime | None,
    ) -> list[Any]:
        """Build parameters for the aggregation query."""
        params: list[Any] = [metric_type.value]

        query_parts = []
        if start_date:
            query_parts.append(" AND timestamp >= ?")
            params.append(start_date.isoformat())

        if end_date:
            query_parts.append(" AND timestamp <= ?")
            params.append(end_date.isoformat())

        return params

    def _execute_aggregation_query(self, query: str, params: list[Any]) -> list[dict[str, Any]]:
        """Execute the aggregation query and return results."""
        query += """
            GROUP BY period
            ORDER BY period DESC
        """

        with self.storage._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()

        return [dict(row) for row in rows]


class MetricsStorage:
    """SQLite-based storage for metrics with configurable retention.

    Attributes:
        db_path: Path to SQLite database file.
        retention_days: Number of days to retain metrics (None for infinite).
        max_metrics: Maximum number of metrics to store (None for unlimited).
        aggregator: MetricsAggregator instance for statistical analysis.
    """

    def __init__(
        self,
        db_path: str | Path | None = None,
        retention_days: int | None = 30,
        max_metrics: int | None = 100000,
    ) -> None:
        """Initialize metrics storage.

        Args:
            db_path: Path to SQLite database file.
            retention_days: Number of days to retain metrics.
            max_metrics: Maximum number of metrics to store.
        """
        if db_path is None:
            # Default to user data directory
            import appdirs

            data_dir = Path(appdirs.user_data_dir("henchman"))
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = data_dir / "metrics.db"
        elif isinstance(db_path, str):
            db_path = Path(db_path)

        self.db_path = Path(db_path)
        self.retention_days = retention_days
        self.max_metrics = max_metrics
        self.aggregator = MetricsAggregator(self)
        self.session_analyzer = SessionMetricsAnalyzer(self)

        # Ensure parent directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize database
        self._init_database()

    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Get a database connection with proper configuration.

        Yields:
            SQLite connection.
        """
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_database(self) -> None:
        """Initialize database schema."""
        schema_manager = DatabaseSchemaManager()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            schema_manager.create_metrics_table(cursor)
            schema_manager.create_indexes(cursor)
            conn.commit()

    def store_metric(self, metric: BaseMetric) -> None:
        """Store a metric in the database.

        Args:
            metric: Metric to store.
        """
        if not self._should_store_metric():
            return

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Convert metric to dictionary
            metric_dict = self._metric_to_dict(metric)

            # Prepare column names and values
            columns = list(metric_dict.keys())
            placeholders = ", ".join(["?"] * len(columns))
            values = list(metric_dict.values())

            # Insert metric
            cursor.execute(
                f"INSERT INTO metrics ({', '.join(columns)}) VALUES ({placeholders})",
                values,
            )

            conn.commit()

        # Clean up old metrics if retention is enabled
        self._cleanup_old_metrics()

    def _metric_to_dict(self, metric: BaseMetric) -> dict[str, Any]:
        """Convert a metric to dictionary for database storage.

        Args:
            metric: Metric to convert.

        Returns:
            Dictionary representation of metric.
        """
        base_dict = self._create_base_metric_dict(metric)
        self._add_metric_specific_fields(metric, base_dict)
        return base_dict

    @staticmethod
    def _create_base_metric_dict(metric: BaseMetric) -> dict[str, Any]:
        """Create the base dictionary with common metric fields.

        Args:
            metric: Metric to convert.

        Returns:
            Dictionary with base metric fields.
        """
        return {
            "id": metric.id,
            "timestamp": metric.timestamp.isoformat(),
            "metric_type": metric.metric_type.value,
            "session_id": metric.session_id,
            "agent_id": metric.agent_id,
            "user_id": metric.user_id,
            "metadata": json.dumps(metric.metadata) if metric.metadata else None,
        }

    # Class constant for field mappings
    _FIELD_MAPPINGS = {
        TokenMetric: {
            "model": "model",
            "provider": "provider",
            "prompt_tokens": "prompt_tokens",
            "completion_tokens": "completion_tokens",
            "total_tokens": "total_tokens",
            "cached_tokens": "cached_tokens",
            "token_limit": "token_limit",
            "token_ratio": "token_ratio",
        },
        CostMetric: {
            "model": "model",
            "provider": "provider",
            "prompt_cost": "prompt_cost",
            "completion_cost": "completion_cost",
            "total_cost": "total_cost",
            "currency": "currency",
            "cost_per_token": "cost_per_token",
            "estimated_cost": "estimated_cost",
        },
        ToolMetric: {
            "tool_name": "tool_name",
            "tool_category": "tool_category",
            "execution_time_ms": "execution_time_ms",
            "success": "success",
            "error_type": "error_type",
            "input_size": "input_size",
            "output_size": "output_size",
            "cache_hit": "cache_hit",
        },
        UsageMetric: {
            "command": "command",
            "subcommand": "subcommand",
            "workflow_type": "workflow_type",
            "duration_ms": "duration_ms",
            "tool_calls_count": "tool_calls_count",
            "agent_switches": "agent_switches",
            "context_compactions": "context_compactions",
            "user_feedback": "user_feedback",
        },
        PerformanceMetric: {
            "event_type": "event_type",
            "latency_ms": "latency_ms",
            "memory_usage_mb": "memory_usage_mb",
            "cpu_usage_percent": "cpu_usage_percent",
            "concurrent_operations": "concurrent_operations",
            "queue_depth": "queue_depth",
        },
    }

    def _add_metric_specific_fields(self, metric: BaseMetric, base_dict: dict[str, Any]) -> None:
        """Add type-specific fields to the metric dictionary."""
        # Find the appropriate mapping and apply it
        for metric_type, mapping in self._FIELD_MAPPINGS.items():
            if isinstance(metric, metric_type):
                self._apply_field_mapping(metric, base_dict, mapping)
                break

    def _apply_field_mapping(
        self, metric: BaseMetric, base_dict: dict[str, Any], mapping: dict[str, str],
    ) -> None:
        """Apply field mapping from metric to base dictionary.

        Args:
            metric: Source metric object.
            base_dict: Target dictionary to update.
            mapping: Dictionary mapping database column names to metric attribute names.
        """
        for db_column, attr_name in mapping.items():
            value = getattr(metric, attr_name, None)
            if value is not None:
                base_dict[db_column] = value

    def _should_store_metric(self) -> bool:
        """Check if a metric should be stored based on limits.

        Returns:
            True if metric should be stored, False otherwise.
        """
        if self.max_metrics is None:
            return True

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM metrics")
            count_result = cursor.fetchone()
            if count_result is None:
                return True
            count: int = count_result[0]

        return count < self.max_metrics

    def _cleanup_old_metrics(self) -> None:
        """Clean up metrics older than retention period."""
        if self.retention_days is None:
            return

        cutoff_date = datetime.now() - timedelta(days=self.retention_days)
        cutoff_str = cutoff_date.isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM metrics WHERE timestamp < ?", (cutoff_str,))
            conn.commit()

    def get_metrics(
        self,
        metric_type: MetricType | None = None,
        session_id: str | None = None,
        agent_id: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieve metrics with optional filtering.

        Args:
            metric_type: Filter by metric type.
            session_id: Filter by session ID.
            agent_id: Filter by agent ID.
            start_date: Filter by start date.
            end_date: Filter by end date.
            limit: Maximum number of metrics to return.

        Returns:
            List of metric dictionaries.
        """
        query_params = MetricsQueryParams(
            metric_type=metric_type,
            session_id=session_id,
            agent_id=agent_id,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )
        return self._execute_metrics_query(query_params)

    def get_metrics_with_params(self, query_params: MetricsQueryParams) -> list[dict[str, Any]]:
        """Retrieve metrics using a MetricsQueryParams object.

        Args:
            query_params: Parameters for filtering metrics.

        Returns:
            List of metric dictionaries.
        """
        return self._execute_metrics_query(query_params)

    def _execute_metrics_query(self, query_params: MetricsQueryParams) -> list[dict[str, Any]]:
        """Execute a metrics query with the given parameters.

        Args:
            query_params: Parameters for filtering metrics.

        Returns:
            List of metric dictionaries.
        """
        query, params = self._build_metrics_query(query_params)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()

        return [dict(row) for row in rows]

    def _build_metrics_query(self, query_params: MetricsQueryParams) -> tuple[str, list[Any]]:
        """Build SQL query and parameters for retrieving metrics.

        Args:
            query_params: Parameters for filtering metrics.

        Returns:
            Tuple of (query_string, parameters_list).
        """
        query = "SELECT * FROM metrics WHERE 1=1"
        params: list[Any] = []

        if query_params.metric_type:
            query += " AND metric_type = ?"
            params.append(query_params.metric_type.value)

        if query_params.session_id:
            query += " AND session_id = ?"
            params.append(query_params.session_id)

        if query_params.agent_id:
            query += " AND agent_id = ?"
            params.append(query_params.agent_id)

        if query_params.start_date:
            query += " AND timestamp >= ?"
            params.append(query_params.start_date.isoformat())

        if query_params.end_date:
            query += " AND timestamp <= ?"
            params.append(query_params.end_date.isoformat())

        query += " ORDER BY timestamp DESC"

        if query_params.limit:
            query += " LIMIT ?"
            params.append(query_params.limit)

        return query, params

    def get_aggregated_stats(
        self,
        metric_type: MetricType,
        group_by: str = "day",
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Get aggregated statistics for metrics.

        Args:
            metric_type: Type of metrics to aggregate.
            group_by: Grouping interval ('hour', 'day', 'week', 'month').
            start_date: Start date for aggregation.
            end_date: End date for aggregation.

        Returns:
            List of aggregated statistics.
        """
        return self.aggregator.get_aggregated_stats(metric_type, group_by, start_date, end_date)

    def get_session_metrics(self, session_id: str) -> dict[str, Any]:
        """Get all metrics for a specific session.

        Args:
            session_id: Session identifier.

        Returns:
            Dictionary with session metrics summary.
        """
        return self.session_analyzer.get_session_metrics(session_id)

    def clear_metrics(self) -> None:
        """Clear all metrics from storage."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM metrics")
            conn.commit()

    def get_database_size(self) -> int:
        """Get the size of the database file in bytes.

        Returns:
            Size in bytes.
        """
        if self.db_path.exists():
            return self.db_path.stat().st_size
        return 0
