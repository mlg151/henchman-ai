"""Metrics storage backend for Henchman-AI.

Provides persistent storage for metrics with configurable retention.
"""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Generator, Optional, Union

from henchman.metrics.models import (
    BaseMetric,
    CostMetric,
    MetricType,
    PerformanceMetric,
    ToolMetric,
    TokenMetric,
    UsageMetric,
)


class MetricsStorage:
    """SQLite-based storage for metrics with configurable retention.

    Attributes:
        db_path: Path to SQLite database file.
        retention_days: Number of days to retain metrics (None for infinite).
        max_metrics: Maximum number of metrics to store (None for unlimited).
    """

    def __init__(
        self,
        db_path: Optional[Union[str, Path]] = None,
        retention_days: Optional[int] = 30,
        max_metrics: Optional[int] = 100000,
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
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Create metrics table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS metrics (
                    id TEXT PRIMARY KEY,
                    timestamp DATETIME NOT NULL,
                    metric_type TEXT NOT NULL,
                    session_id TEXT,
                    agent_id TEXT,
                    user_id TEXT,
                    model TEXT,
                    provider TEXT,
                    prompt_tokens INTEGER,
                    completion_tokens INTEGER,
                    total_tokens INTEGER,
                    cached_tokens INTEGER,
                    token_limit INTEGER,
                    token_ratio REAL,
                    prompt_cost REAL,
                    completion_cost REAL,
                    total_cost REAL,
                    currency TEXT,
                    cost_per_token REAL,
                    estimated_cost REAL,
                    tool_name TEXT,
                    tool_category TEXT,
                    execution_time_ms REAL,
                    success BOOLEAN,
                    error_type TEXT,
                    input_size INTEGER,
                    output_size INTEGER,
                    cache_hit BOOLEAN,
                    command TEXT,
                    subcommand TEXT,
                    workflow_type TEXT,
                    duration_ms REAL,
                    tool_calls_count INTEGER,
                    agent_switches INTEGER,
                    context_compactions INTEGER,
                    user_feedback TEXT,
                    event_type TEXT,
                    latency_ms REAL,
                    memory_usage_mb REAL,
                    cpu_usage_percent REAL,
                    concurrent_operations INTEGER,
                    queue_depth INTEGER,
                    metadata TEXT
                )
            """)

            # Create indexes for common queries
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_metric_type ON metrics(metric_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON metrics(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_session_id ON metrics(session_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_agent_id ON metrics(agent_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_model ON metrics(model)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tool_name ON metrics(tool_name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_command ON metrics(command)")

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
        base_dict = {
            "id": metric.id,
            "timestamp": metric.timestamp.isoformat(),
            "metric_type": metric.metric_type.value,
            "session_id": metric.session_id,
            "agent_id": metric.agent_id,
            "user_id": metric.user_id,
            "metadata": json.dumps(metric.metadata) if metric.metadata else None,
        }

        # Add type-specific fields
        if isinstance(metric, TokenMetric):
            base_dict.update({
                "model": metric.model,
                "provider": metric.provider,
                "prompt_tokens": metric.prompt_tokens,
                "completion_tokens": metric.completion_tokens,
                "total_tokens": metric.total_tokens,
                "cached_tokens": metric.cached_tokens,
                "token_limit": metric.token_limit,
                "token_ratio": metric.token_ratio,
            })
        elif isinstance(metric, CostMetric):
            base_dict.update({
                "model": metric.model,
                "provider": metric.provider,
                "prompt_cost": metric.prompt_cost,
                "completion_cost": metric.completion_cost,
                "total_cost": metric.total_cost,
                "currency": metric.currency,
                "cost_per_token": metric.cost_per_token,
                "estimated_cost": metric.estimated_cost,
            })
        elif isinstance(metric, ToolMetric):
            base_dict.update({
                "tool_name": metric.tool_name,
                "tool_category": metric.tool_category,
                "execution_time_ms": metric.execution_time_ms,
                "success": metric.success,
                "error_type": metric.error_type,
                "input_size": metric.input_size,
                "output_size": metric.output_size,
                "cache_hit": metric.cache_hit,
            })
        elif isinstance(metric, UsageMetric):
            base_dict.update({
                "command": metric.command,
                "subcommand": metric.subcommand,
                "workflow_type": metric.workflow_type,
                "duration_ms": metric.duration_ms,
                "tool_calls_count": metric.tool_calls_count,
                "agent_switches": metric.agent_switches,
                "context_compactions": metric.context_compactions,
                "user_feedback": metric.user_feedback,
            })
        elif isinstance(metric, PerformanceMetric):
            base_dict.update({
                "event_type": metric.event_type,
                "latency_ms": metric.latency_ms,
                "memory_usage_mb": metric.memory_usage_mb,
                "cpu_usage_percent": metric.cpu_usage_percent,
                "concurrent_operations": metric.concurrent_operations,
                "queue_depth": metric.queue_depth,
            })

        return base_dict

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
            count = cursor.fetchone()[0]

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
        metric_type: Optional[MetricType] = None,
        session_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: Optional[int] = None,
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
        query = "SELECT * FROM metrics WHERE 1=1"
        params: list[Any] = []

        if metric_type:
            query += " AND metric_type = ?"
            params.append(metric_type.value)

        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)

        if agent_id:
            query += " AND agent_id = ?"
            params.append(agent_id)

        if start_date:
            query += " AND timestamp >= ?"
            params.append(start_date.isoformat())

        if end_date:
            query += " AND timestamp <= ?"
            params.append(end_date.isoformat())

        query += " ORDER BY timestamp DESC"

        if limit:
            query += " LIMIT ?"
            params.append(limit)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()

        return [dict(row) for row in rows]

    def get_aggregated_stats(
        self,
        metric_type: MetricType,
        group_by: str = "day",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
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
        if group_by == "hour":
            time_format = "strftime('%Y-%m-%d %H:00:00', timestamp)"
        elif group_by == "day":
            time_format = "date(timestamp)"
        elif group_by == "week":
            time_format = "strftime('%Y-W%W', timestamp)"
        elif group_by == "month":
            time_format = "strftime('%Y-%m', timestamp)"
        else:
            raise ValueError(f"Invalid group_by: {group_by}")

        query = f"""
            SELECT 
                {time_format} as period,
                COUNT(*) as count
        """

        # Add aggregation based on metric type
        if metric_type == MetricType.TOKEN_USAGE:
            query += """,
                SUM(prompt_tokens) as total_prompt_tokens,
                SUM(completion_tokens) as total_completion_tokens,
                SUM(total_tokens) as total_tokens,
                AVG(token_ratio) as avg_token_ratio
            """
        elif metric_type == MetricType.COST:
            query += """,
                SUM(prompt_cost) as total_prompt_cost,
                SUM(completion_cost) as total_completion_cost,
                SUM(total_cost) as total_cost,
                AVG(cost_per_token) as avg_cost_per_token
            """
        elif metric_type == MetricType.TOOL_PERFORMANCE:
            query += """,
                COUNT(CASE WHEN success = 1 THEN 1 END) as successful_calls,
                COUNT(CASE WHEN success = 0 THEN 1 END) as failed_calls,
                AVG(execution_time_ms) as avg_execution_time,
                SUM(input_size) as total_input_size,
                SUM(output_size) as total_output_size
            """
        elif metric_type == MetricType.USAGE_PATTERN:
            query += """,
                COUNT(DISTINCT command) as unique_commands,
                SUM(tool_calls_count) as total_tool_calls,
                SUM(agent_switches) as total_agent_switches,
                SUM(context_compactions) as total_context_compactions,
                AVG(duration_ms) as avg_duration
            """

        query += f"""
            FROM metrics
            WHERE metric_type = ?
        """

        params: list[Any] = [metric_type.value]

        if start_date:
            query += " AND timestamp >= ?"
            params.append(start_date.isoformat())

        if end_date:
            query += " AND timestamp <= ?"
            params.append(end_date.isoformat())

        query += f"""
            GROUP BY period
            ORDER BY period DESC
        """

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()

        return [dict(row) for row in rows]

    def get_session_metrics(self, session_id: str) -> dict[str, Any]:
        """Get all metrics for a specific session.

        Args:
            session_id: Session identifier.

        Returns:
            Dictionary with session metrics summary.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Get token usage summary
            cursor.execute("""
                SELECT 
                    SUM(prompt_tokens) as total_prompt_tokens,
                    SUM(completion_tokens) as total_completion_tokens,
                    SUM(total_tokens) as total_tokens,
                    COUNT(DISTINCT model) as unique_models
                FROM metrics 
                WHERE session_id = ? AND metric_type = 'token_usage'
            """, (session_id,))
            token_stats = cursor.fetchone()

            # Get cost summary
            cursor.execute("""
                SELECT 
                    SUM(prompt_cost) as total_prompt_cost,
                    SUM(completion_cost) as total_completion_cost,
                    SUM(total_cost) as total_cost
                FROM metrics 
                WHERE session_id = ? AND metric_type = 'cost'
            """, (session_id,))
            cost_stats = cursor.fetchone()

            # Get tool performance summary
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_tool_calls,
                    COUNT(CASE WHEN success = 1 THEN 1 END) as successful_calls,
                    COUNT(CASE WHEN success = 0 THEN 1 END) as failed_calls,
                    AVG(execution_time_ms) as avg_execution_time
                FROM metrics 
                WHERE session_id = ? AND metric_type = 'tool_performance'
            """, (session_id,))
            tool_stats = cursor.fetchone()

            # Get usage pattern
            cursor.execute("""
                SELECT 
                    command,
                    COUNT(*) as execution_count,
                    AVG(duration_ms) as avg_duration,
                    SUM(tool_calls_count) as total_tool_calls
                FROM metrics 
                WHERE session_id = ? AND metric_type = 'usage_pattern'
                GROUP BY command
                ORDER BY execution_count DESC
            """, (session_id,))
            usage_patterns = cursor.fetchall()

        return {
            "session_id": session_id,
            "token_usage": dict(token_stats) if token_stats else {},
            "cost": dict(cost_stats) if cost_stats else {},
            "tool_performance": dict(tool_stats) if tool_stats else {},
            "usage_patterns": [dict(row) for row in usage_patterns],
        }

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