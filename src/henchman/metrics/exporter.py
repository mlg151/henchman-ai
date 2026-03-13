"""Metrics export module for Henchman-AI.

This module provides classes for exporting agent performance metrics to various formats
and destinations. It supports JSON, CSV, and Prometheus export formats, as well as
summary statistics calculation.

Classes:
    PrometheusFormatter: Formats metrics for Prometheus exposition format.
    SummaryCalculator: Calculates summary statistics for metrics data.
    MetricsExporter: Main exporter class that handles export to multiple formats.

The module is designed to work with the MetricsStorage system to retrieve and
process agent performance metrics for analysis and monitoring.
"""

from __future__ import annotations

import contextlib
import json
import logging
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from henchman.metrics.storage import MetricsStorage

# Constants for metrics export
MIN_PRINTABLE_ASCII = 32
DEFAULT_PROMETHEUS_VALUE = 1.0
PROMETHEUS_CONTENT_TYPE = "text/plain; version=0.0.4"
DEFAULT_TIMEOUT = 30.0

logger = logging.getLogger(__name__)


class PrometheusFormatter:
    """Helper class to format metrics for Prometheus."""

    # Fields to exclude from labels
    EXCLUDE_FIELDS: ClassVar[set[str]] = {
        "id",
        "total_tokens",
        "execution_time_ms",
        "duration_ms",
        "value",
        "timestamp",
        "metric_type",
        "details",
        "data",
    }

    # Value fields to extract from metrics
    VALUE_FIELDS: ClassVar[list[str]] = [
        "total_tokens",
        "execution_time_ms",
        "duration_ms",
        "value",
    ]

    @classmethod
    def format(cls: type[PrometheusFormatter], metrics: list[dict[str, Any]]) -> str:
        """Convert metrics to Prometheus exposition format.

        Args:
            metrics: List of metric dictionaries.

        Returns:
            String in Prometheus exposition format.
        """
        lines = []
        metric_groups = cls._group_by_type(metrics)

        for metric_type, metric_list in metric_groups.items():
            prom_name = cls._sanitize_name(f"henchman_{metric_type}")
            lines.append(f"# TYPE {prom_name} gauge")

            for metric in metric_list:
                line = cls._format_single_metric(prom_name, metric)
                if line:
                    lines.append(line)

        return "\n".join(lines) + "\n"

    @classmethod
    def _group_by_type(
        cls: type[PrometheusFormatter], metrics: list[dict[str, Any]]
    ) -> dict[str, list[dict[str, Any]]]:
        """Group metrics by their type."""
        groups: dict[str, list[dict[str, Any]]] = {}
        for metric in metrics:
            m_type = metric.get("metric_type", "unknown")
            groups.setdefault(m_type, []).append(metric)
        return groups

    @classmethod
    def _format_single_metric(
        cls: type[PrometheusFormatter], prom_name: str, metric: dict[str, Any]
    ) -> str | None:
        """Format a single metric entry."""
        value = cls._extract_value(metric)
        if value is None or math.isnan(value) or math.isinf(value):
            return None

        labels = cls._build_labels(metric)
        return f"{prom_name}{{{labels}}} {value}" if labels else f"{prom_name} {value}"

    @classmethod
    def _extract_value(cls: type[PrometheusFormatter], metric: dict[str, Any]) -> float | None:
        """Extract numeric value from metric."""
        for key in cls.VALUE_FIELDS:
            val = metric.get(key)
            if isinstance(val, (int, float)):
                return float(val)
        return DEFAULT_PROMETHEUS_VALUE

    @classmethod
    def _sanitize_name(cls: type[PrometheusFormatter], name: str) -> str:
        """Sanitize name for Prometheus."""
        sanitized = re.sub(r"[^a-zA-Z0-9_:]", "_", name)
        if sanitized and sanitized[0].isdigit():
            sanitized = f"metric_{sanitized}"
        return sanitized

    @classmethod
    def _build_labels(cls: type[PrometheusFormatter], metric: dict[str, Any]) -> str:
        """Build Prometheus labels string."""
        labels = []
        for key, value in metric.items():
            if (
                key in cls.EXCLUDE_FIELDS
                or value is None
                or isinstance(value, (dict, list))
            ):
                continue

            str_val = str(value).replace("\\", "\\\\").replace('"', '\\"')
            str_val = "".join(c for c in str_val if ord(c) >= MIN_PRINTABLE_ASCII)
            label_name = cls._sanitize_name(key)
            labels.append(f'{label_name}="{str_val}"')

        return ",".join(sorted(labels))


class SummaryCalculator:
    """Helper class to calculate metric summaries."""

    @classmethod
    def calculate(
        cls: type[SummaryCalculator], metrics: list[dict[str, Any]], filters: dict[str, Any]
    ) -> dict[str, Any]:
        """Calculate summary statistics for metrics.
        
        Args:
            metrics: List of metric dictionaries to analyze.
            filters: Dictionary of filters applied to the metrics.
            
        Returns:
            Dictionary containing summary statistics including total metrics count,
            metric type distribution, time range, and filter information.
        """
        summary: dict[str, Any] = {
            "total_metrics": len(metrics),
            "metric_types": {},
            "time_range": {"start": None, "end": None},
            "exported_at": datetime.now(tz=timezone.utc).isoformat(),
            "filters": filters,
        }

        if not metrics:
            return summary

        groups, timestamps = cls._group_and_extract_ts(metrics)
        if timestamps:
            summary["time_range"]["start"] = min(timestamps).isoformat()
            summary["time_range"]["end"] = max(timestamps).isoformat()

        for m_type, m_list in groups.items():
            summary["metric_types"][m_type] = cls._calculate_type_stats(m_list)

        return summary

    @classmethod
    def _group_and_extract_ts(
        cls: type[SummaryCalculator], metrics: list[dict[str, Any]]
    ) -> tuple[dict[str, list[dict[str, Any]]], list[datetime]]:
        """Group metrics and extract timestamps."""
        groups: dict[str, list[dict[str, Any]]] = {}
        timestamps = []
        for m in metrics:
            m_type = m.get("metric_type", "unknown")
            groups.setdefault(m_type, []).append(m)

            ts_str = m.get("timestamp")
            if ts_str:
                with contextlib.suppress(ValueError, AttributeError):
                    timestamps.append(datetime.fromisoformat(ts_str.replace("Z", "+00:00")))
        return groups, timestamps

    @classmethod
    def _calculate_type_stats(
        cls: type[SummaryCalculator], metrics: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Calculate statistics for a specific metric type."""
        numeric_fields = {
            k
            for m in metrics
            for k, v in m.items()
            if isinstance(v, (int, float)) and k != "id"
        }

        fields_stats = {}
        for field in numeric_fields:
            vals = [
                m[field]
                for m in metrics
                if field in m and isinstance(m[field], (int, float))
            ]
            if vals:
                fields_stats[field] = {
                    "count": len(vals),
                    "sum": sum(vals),
                    "avg": sum(vals) / len(vals),
                    "min": min(vals),
                    "max": max(vals),
                }

        return {"count": len(metrics), "fields": fields_stats}


class MetricsExporter:
    """Exports metrics data to various formats and destinations.

    Attributes:
        metrics_storage: Storage backend for metrics data.
    """

    def __init__(self: MetricsExporter, metrics_storage: MetricsStorage) -> None:
        """Initialize the metrics exporter.

        Args:
            metrics_storage: Storage backend for metrics data.
        """
        self.metrics_storage = metrics_storage

    def _get_filtered_metrics(self: MetricsExporter, **filters: Any) -> list[dict[str, Any]]:
        """Retrieve filtered metrics from storage."""
        return self.metrics_storage.get_metrics(
            metric_type=filters.get("metric_type"),
            session_id=filters.get("session_id"),
            agent_id=filters.get("agent_id"),
            start_date=filters.get("start_date"),
            end_date=filters.get("end_date"),
            limit=filters.get("limit"),
        )

    def export_to_json(self: MetricsExporter, filepath: str | Path, **filters: Any) -> None:
        """Export metrics to JSON file.
        
        Args:
            filepath: Path where the JSON file should be saved.
            filters: Keyword arguments for filtering metrics (e.g., metric_type,
                session_id, agent_id, start_date, end_date, limit).
        
        Returns:
            None
        """
        metrics = self._get_filtered_metrics(**filters)
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)

        with path.open("w", encoding="utf-8") as f:
            json.dump(
                {
                    "metrics": metrics,
                    "count": len(metrics),
                    "exported_at": datetime.now(tz=timezone.utc).isoformat(),
                    "filters": filters,
                },
                f,
                indent=2,
                default=str,
            )

    def export_to_csv(self: MetricsExporter, filepath: str | Path, **filters: Any) -> None:
        """Export metrics to CSV file.
        
        Args:
            filepath: Path where the CSV file should be saved.
            filters: Keyword arguments for filtering metrics (e.g., metric_type,
                session_id, agent_id, start_date, end_date, limit).
        
        Returns:
            None
        """
        import csv

        metrics = self._get_filtered_metrics(**filters)
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)

        if not metrics:
            with path.open("w", newline="", encoding="utf-8") as f:
                f.write("id,metric_type,timestamp\n")
            return

        fieldnames = sorted({k for m in metrics for k in m})
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for m in metrics:
                writer.writerow(
                    {
                        k: (
                            json.dumps(v, default=str)
                            if isinstance(v, (dict, list))
                            else ("" if v is None else str(v))
                        )
                        for k in fieldnames
                        for v in [m.get(k)]
                    }
                )

    def export_to_prometheus(self: MetricsExporter, endpoint: str, **filters: Any) -> None:
        """Export metrics to Prometheus endpoint.
        
        Args:
            endpoint: Prometheus push gateway endpoint URL.
            filters: Keyword arguments for filtering metrics (e.g., metric_type,
                session_id, agent_id, start_date, end_date, limit).
        
        Returns:
            None
        """
        import requests

        if not endpoint:
            msg = "Prometheus endpoint cannot be empty"
            raise ValueError(msg)

        metrics = self._get_filtered_metrics(**filters)
        if not metrics:
            return

        prom_data = PrometheusFormatter.format(metrics)
        try:
            resp = requests.post(
                endpoint,
                data=prom_data,
                headers={"Content-Type": PROMETHEUS_CONTENT_TYPE},
                timeout=DEFAULT_TIMEOUT,
            )
            resp.raise_for_status()
        except requests.exceptions.RequestException as e:
            logger.warning("Failed to export metrics to Prometheus: %s", e)
            msg = f"Failed to connect to Prometheus endpoint: {e}"
            raise ConnectionError(msg) from e

    def export_summary(self: MetricsExporter, **filters: Any) -> dict[str, Any]:
        """Export summary statistics.
        
        Args:
            filters: Keyword arguments for filtering metrics (e.g., metric_type,
                session_id, agent_id, start_date, end_date, limit).
        
        Returns:
            Dictionary containing summary statistics.
        """
        metrics = self._get_filtered_metrics(**filters)
        return SummaryCalculator.calculate(metrics, filters)

    def get_available_formats(self: MetricsExporter) -> list[str]:
        """Get list of available export formats.
        
        Returns:
            List of available export format names.
        """
        return ["json", "csv", "prometheus"]
