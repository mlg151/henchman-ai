"""Tests for henchman.metrics.exporter."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from henchman.metrics.exporter import MetricsExporter


@pytest.fixture()
def mock_storage() -> MagicMock:
    """Create a mock metrics storage."""
    storage = MagicMock()
    storage.get_metrics.return_value = [
        {
            "id": "metric-1",
            "metric_type": "token_usage",
            "total_tokens": 100,
        }
    ]
    return storage


@pytest.fixture()
def exporter(mock_storage: MagicMock) -> MetricsExporter:
    """Create a MetricsExporter with mock storage."""
    return MetricsExporter(metrics_storage=mock_storage)


class TestMetricsExporterInit:
    """Tests for MetricsExporter initialization."""

    def test_init(self, mock_storage: MagicMock) -> None:
        """Test MetricsExporter stores the storage reference."""
        e = MetricsExporter(metrics_storage=mock_storage)
        assert e.metrics_storage is mock_storage


class TestExportToJson:
    """Tests for MetricsExporter.export_to_json."""

    def test_exports_to_file(self, exporter: MetricsExporter, tmp_path: Path) -> None:
        """Test that export_to_json writes a JSON file."""
        filepath = str(tmp_path / "output.json")
        exporter.export_to_json(filepath)

        assert Path(filepath).exists()
        with open(filepath) as f:
            data = json.load(f)

        assert "metrics" in data
        assert "count" in data
        assert "exported_at" in data
        assert "filters" in data

    def test_creates_parent_directories(
        self, exporter: MetricsExporter, tmp_path: Path
    ) -> None:
        """Test that missing parent directories are created."""
        filepath = str(tmp_path / "nested" / "deep" / "output.json")
        exporter.export_to_json(filepath)
        assert Path(filepath).exists()

    def test_filters_passed_to_storage(
        self, exporter: MetricsExporter, tmp_path: Path, mock_storage: MagicMock
    ) -> None:
        """Test that filters are passed to storage.get_metrics."""
        filepath = str(tmp_path / "filtered.json")
        exporter.export_to_json(filepath, session_id="sess-1", limit=10)
        mock_storage.get_metrics.assert_called_once_with(
            metric_type=None,
            session_id="sess-1",
            agent_id=None,
            start_date=None,
            end_date=None,
            limit=10,
        )

    def test_count_matches_metrics(
        self, exporter: MetricsExporter, tmp_path: Path
    ) -> None:
        """Test that count field matches number of metrics."""
        filepath = str(tmp_path / "count_test.json")
        exporter.export_to_json(filepath)

        with open(filepath) as f:
            data = json.load(f)

        assert data["count"] == len(data["metrics"])

    def test_no_filters_uses_defaults(
        self, exporter: MetricsExporter, tmp_path: Path, mock_storage: MagicMock
    ) -> None:
        """Test that calling with no filters uses None defaults."""
        filepath = str(tmp_path / "no_filter.json")
        exporter.export_to_json(filepath)
        mock_storage.get_metrics.assert_called_once_with(
            metric_type=None,
            session_id=None,
            agent_id=None,
            start_date=None,
            end_date=None,
            limit=None,
        )

    def test_filters_in_output(
        self, exporter: MetricsExporter, tmp_path: Path
    ) -> None:
        """Test that filters are included in output."""
        filepath = str(tmp_path / "filters_test.json")
        exporter.export_to_json(filepath, session_id="test-session")

        with open(filepath) as f:
            data = json.load(f)

        assert data["filters"]["session_id"] == "test-session"


class TestExportToCsv:
    """Tests for MetricsExporter.export_to_csv."""

    def test_exports_to_csv_file(self, exporter: MetricsExporter, tmp_path: Path) -> None:
        """Test that export_to_csv writes a CSV file."""
        filepath = str(tmp_path / "output.csv")
        exporter.export_to_csv(filepath)

        assert Path(filepath).exists()
        with open(filepath, encoding="utf-8") as f:
            content = f.read()

        # Check CSV structure
        lines = content.strip().split("\n")
        assert len(lines) > 0
        assert "id,metric_type,total_tokens" in lines[0]  # Header
        assert "metric-1,token_usage,100" in lines[1]  # Data row

    def test_creates_parent_directories_csv(
        self, exporter: MetricsExporter, tmp_path: Path
    ) -> None:
        """Test that missing parent directories are created for CSV."""
        filepath = str(tmp_path / "nested" / "deep" / "output.csv")
        exporter.export_to_csv(filepath)
        assert Path(filepath).exists()

    def test_filters_passed_to_storage_csv(
        self, exporter: MetricsExporter, tmp_path: Path, mock_storage: MagicMock
    ) -> None:
        """Test that filters are passed to storage.get_metrics for CSV."""
        filepath = str(tmp_path / "filtered.csv")
        exporter.export_to_csv(filepath, session_id="sess-1", limit=10)
        mock_storage.get_metrics.assert_called_once_with(
            metric_type=None,
            session_id="sess-1",
            agent_id=None,
            start_date=None,
            end_date=None,
            limit=10,
        )

    def test_csv_with_complex_data(self, exporter: MetricsExporter, tmp_path: Path, mock_storage: MagicMock) -> None:
        """Test CSV export with complex nested data."""
        # Mock more complex data
        complex_data = [
            {
                "id": "metric-1",
                "metric_type": "token_usage",
                "total_tokens": 100,
                "details": {"prompt_tokens": 40, "completion_tokens": 60},
                "timestamp": "2024-01-15T10:30:00Z"
            },
            {
                "id": "metric-2",
                "metric_type": "tool_execution",
                "tool_name": "read_file",
                "execution_time_ms": 150.5,
                "success": True
            }
        ]
        mock_storage.get_metrics.return_value = complex_data

        filepath = str(tmp_path / "complex.csv")
        exporter.export_to_csv(filepath)

        assert Path(filepath).exists()
        with open(filepath, encoding="utf-8") as f:
            content = f.read()

        # Check CSV has headers and data rows
        lines = content.strip().split("\n")
        assert len(lines) == 3  # Header + 2 data rows

        # Check headers contain all expected fields (order doesn't matter)
        headers = lines[0].split(",")
        expected_fields = {"id", "metric_type", "total_tokens", "details", "timestamp", "tool_name", "execution_time_ms", "success"}
        assert set(headers) == expected_fields

        # Check data rows contain expected values using csv reader for proper parsing
        import csv
        import io

        # Parse CSV properly
        csv_reader = csv.DictReader(io.StringIO(content))
        rows = list(csv_reader)

        assert len(rows) == 2

        # First row should have metric-1 data
        row1 = rows[0]
        assert row1["id"] == "metric-1"
        assert row1["metric_type"] == "token_usage"
        assert row1["total_tokens"] == "100"
        # Details should be JSON string
        import json
        details = json.loads(row1["details"])
        assert details["prompt_tokens"] == 40
        assert details["completion_tokens"] == 60

        # Second row should have metric-2 data
        row2 = rows[1]
        assert row2["id"] == "metric-2"
        assert row2["metric_type"] == "tool_execution"
        assert row2["tool_name"] == "read_file"
        assert row2["execution_time_ms"] == "150.5"
        assert row2["success"] == "True"

    def test_csv_empty_metrics(
        self, exporter: MetricsExporter, tmp_path: Path, mock_storage: MagicMock
    ) -> None:
        """Test CSV export with empty metrics (should create empty CSV with headers)."""
        # Setup mock to return empty list
        mock_storage.get_metrics.return_value = []

        filepath = str(tmp_path / "empty.csv")
        exporter.export_to_csv(filepath)

        assert Path(filepath).exists()
        with open(filepath, encoding="utf-8") as f:
            content = f.read()

        # Should have just headers
        lines = content.strip().split("\n")
        assert len(lines) == 1
        assert "id,metric_type,timestamp" in lines[0]


class TestExportToPrometheus:
    """Tests for MetricsExporter.export_to_prometheus."""

    def test_exports_to_prometheus(self, exporter: MetricsExporter, mock_storage: MagicMock) -> None:
        """Test that export_to_prometheus formats metrics for Prometheus."""
        # Mock the requests.post method
        from unittest.mock import patch

        with patch('requests.post') as mock_post:
            mock_post.return_value.status_code = 200

            exporter.export_to_prometheus("http://localhost:9091/metrics/job/henchman")

            # Verify request was made
            mock_post.assert_called_once()

            # Verify URL
            args, kwargs = mock_post.call_args
            assert args[0] == "http://localhost:9091/metrics/job/henchman"

            # Verify data contains Prometheus format
            assert "data" in kwargs
            data = kwargs["data"]
            assert isinstance(data, str)
            assert "# TYPE" in data  # Prometheus type definitions
            assert "henchman_" in data  # Metric prefixes

    def test_filters_passed_to_storage_prometheus(
        self, exporter: MetricsExporter, mock_storage: MagicMock
    ) -> None:
        """Test that filters are passed to storage.get_metrics for Prometheus."""
        from unittest.mock import patch

        with patch('requests.post') as mock_post:
            mock_post.return_value.status_code = 200

            exporter.export_to_prometheus(
                "http://localhost:9091",
                session_id="sess-1",
                limit=10
            )

            mock_storage.get_metrics.assert_called_once_with(
                metric_type=None,
                session_id="sess-1",
                agent_id=None,
                start_date=None,
                end_date=None,
                limit=10,
            )

    def test_handles_prometheus_error(self, exporter: MetricsExporter, mock_storage: MagicMock) -> None:
        """Test that Prometheus export handles HTTP errors."""
        from unittest.mock import patch

        import requests

        with patch('requests.post') as mock_post:
            mock_post.return_value.status_code = 500
            mock_post.return_value.raise_for_status.side_effect = requests.exceptions.HTTPError("Server error")

            # Should raise ConnectionError
            with pytest.raises(ConnectionError, match="Failed to connect to Prometheus endpoint"):
                exporter.export_to_prometheus("http://localhost:9091")

            # Verify request was attempted
            mock_post.assert_called_once()

    def test_prometheus_empty_endpoint(self, exporter: MetricsExporter) -> None:
        """Test that Prometheus export raises error for empty endpoint."""
        with pytest.raises(ValueError, match="Prometheus endpoint cannot be empty"):
            exporter.export_to_prometheus("")

        with pytest.raises(ValueError, match="Prometheus endpoint cannot be empty"):
            exporter.export_to_prometheus(None)  # type: ignore[arg-type]

    def test_prometheus_empty_metrics(
        self, exporter: MetricsExporter, mock_storage: MagicMock
    ) -> None:
        """Test that Prometheus export handles empty metrics gracefully."""
        from unittest.mock import patch

        # Mock empty metrics
        mock_storage.get_metrics.return_value = []

        with patch('requests.post') as mock_post:
            exporter.export_to_prometheus("http://localhost:9091")

            # Should not make any HTTP request when metrics are empty
            mock_post.assert_not_called()

    def test_prometheus_format_correct(self, exporter: MetricsExporter, tmp_path: Path, mock_storage: MagicMock) -> None:
        """Test that Prometheus format is correctly generated."""
        # Create more realistic metric data
        metric_data = [
            {
                "id": "metric-1",
                "metric_type": "token_usage",
                "total_tokens": 150,
                "prompt_tokens": 50,
                "completion_tokens": 100,
                "timestamp": "2024-01-15T10:30:00Z",
                "model": "gpt-4"
            },
            {
                "id": "metric-2",
                "metric_type": "tool_execution_time",
                "tool_name": "read_file",
                "execution_time_ms": 245.7,
                "success": True,
                "timestamp": "2024-01-15T10:31:00Z"
            }
        ]
        mock_storage.get_metrics.return_value = metric_data

        from unittest.mock import patch

        with patch('requests.post') as mock_post:
            mock_post.return_value.status_code = 200

            exporter.export_to_prometheus("http://localhost:9091")

            # Get the data that was sent
            args, kwargs = mock_post.call_args
            data = kwargs["data"]

            # Check Prometheus format
            assert "# TYPE henchman_token_usage gauge" in data
            assert "# TYPE henchman_tool_execution_time gauge" in data
            assert 'henchman_token_usage{completion_tokens="100",model="gpt-4",prompt_tokens="50"} 150' in data
            assert 'henchman_tool_execution_time{success="True",tool_name="read_file"} 245.7' in data

    def test_prometheus_nan_infinity_values(
        self, exporter: MetricsExporter, mock_storage: MagicMock
    ) -> None:
        """Test that Prometheus export handles NaN and infinity values."""
        from unittest.mock import patch

        # Mock metrics with NaN and infinity
        nan_inf_metrics = [
            {
                "id": "metric-nan",
                "metric_type": "test",
                "value": float("nan"),
                "label": "has_nan"
            },
            {
                "id": "metric-inf",
                "metric_type": "test",
                "value": float("inf"),
                "label": "has_inf"
            },
            {
                "id": "metric-neg-inf",
                "metric_type": "test",
                "value": float("-inf"),
                "label": "has_neg_inf"
            }
        ]
        mock_storage.get_metrics.return_value = nan_inf_metrics

        with patch('requests.post') as mock_post:
            mock_post.return_value.status_code = 200

            exporter.export_to_prometheus("http://localhost:9091")

            # Get the data that was sent
            args, kwargs = mock_post.call_args
            data = kwargs["data"]

            # NaN and infinity values should be skipped, so no metric lines
            # Should only have TYPE line
            assert "# TYPE henchman_test gauge" in data
            # Should not have any metric lines with values
            lines = data.split("\n")
            metric_lines = [line for line in lines if line and not line.startswith("#")]
            assert len(metric_lines) == 0  # All NaN/inf values skipped

    def test_prometheus_no_numeric_values(
        self, exporter: MetricsExporter, mock_storage: MagicMock
    ) -> None:
        """Test that Prometheus export handles metrics without numeric values."""
        from unittest.mock import patch

        # Mock metrics without numeric fields
        non_numeric_metrics = [
            {
                "id": "metric-1",
                "metric_type": "event",
                "event_name": "session_started",
                "timestamp": "2024-01-15T10:30:00Z"
            },
            {
                "id": "metric-2",
                "metric_type": "event",
                "event_name": "session_ended",
                "timestamp": "2024-01-15T11:30:00Z"
            }
        ]
        mock_storage.get_metrics.return_value = non_numeric_metrics

        with patch('requests.post') as mock_post:
            mock_post.return_value.status_code = 200

            exporter.export_to_prometheus("http://localhost:9091")

            # Get the data that was sent
            args, kwargs = mock_post.call_args
            data = kwargs["data"]

            # Should use default value of 1.0 for metrics without numeric values
            assert "# TYPE henchman_event gauge" in data
            assert 'henchman_event{event_name="session_started"}' in data
            assert 'henchman_event{event_name="session_ended"}' in data
            # Check that value is 1.0
            lines = data.split("\n")
            for line in lines:
                if 'session_started' in line or 'session_ended' in line:
                    assert line.endswith(" 1.0")

    def test_build_prometheus_labels(
        self, exporter: MetricsExporter
    ) -> None:
        """Test the PrometheusFormatter._build_labels method."""
        from henchman.metrics.exporter import PrometheusFormatter
        # Test with various metric structures
        test_cases = [
            {
                "metric": {
                    "id": "test-1",
                    "metric_type": "test",
                    "value": 100,
                    "label1": "value1",
                    "label2": "value2",
                    "excluded": None,  # Should be skipped
                    "nested": {"key": "value"},  # Should be skipped
                    "list": [1, 2, 3],  # Should be skipped
                },
                "expected_labels": 2  # label1 and label2
            },
            {
                "metric": {
                    "id": "test-2",
                    "metric_type": "test",
                    "total_tokens": 150,  # In exclude_fields
                    "timestamp": "2024-01-15T10:30:00Z",  # In exclude_fields
                    "details": {"foo": "bar"},  # In exclude_fields
                    "valid_label": "test_value"
                },
                "expected_labels": 1  # Only valid_label
            },
            {
                "metric": {
                    "id": "test-3",
                    "metric_type": "test",
                    "value": 200,
                    "label_with_special_chars": 'test"value\\with"quotes',
                    "label_with_newline": "test\nvalue"
                },
                "expected_labels": 2  # Both labels, sanitized
            }
        ]

        for test_case in test_cases:
            labels = PrometheusFormatter._build_labels(test_case["metric"])
            if test_case["expected_labels"] > 0:
                # Count labels by counting commas + 1
                label_count = labels.count(",") + 1 if labels else 0
                assert label_count == test_case["expected_labels"]
                # Check that special characters are escaped
                if 'label_with_special_chars' in test_case["metric"]:
                    assert '\\\\' in labels  # Escaped backslash
                    assert '\\"' in labels  # Escaped quote
                if 'label_with_newline' in test_case["metric"]:
                    assert "\n" not in labels  # Newline removed
            else:
                assert labels == ""  # Empty string for no labels


class TestExportSummary:
    """Tests for MetricsExporter.export_summary."""

    def test_exports_summary_statistics(self, exporter: MetricsExporter, mock_storage: MagicMock) -> None:
        """Test that export_summary returns summary statistics."""
        summary = exporter.export_summary()

        assert isinstance(summary, dict)
        assert "total_metrics" in summary
        assert "metric_types" in summary
        assert "time_range" in summary
        assert summary["total_metrics"] == 1  # From mock data

    def test_filters_passed_to_storage_summary(
        self, exporter: MetricsExporter, mock_storage: MagicMock
    ) -> None:
        """Test that filters are passed to storage.get_metrics for summary."""
        exporter.export_summary(session_id="sess-1", limit=10)

        mock_storage.get_metrics.assert_called_once_with(
            metric_type=None,
            session_id="sess-1",
            agent_id=None,
            start_date=None,
            end_date=None,
            limit=10,
        )

    def test_summary_with_complex_data(self, exporter: MetricsExporter, mock_storage: MagicMock) -> None:
        """Test summary export with complex data."""
        # Mock more complex data
        complex_data = [
            {
                "id": "metric-1",
                "metric_type": "token_usage",
                "total_tokens": 100,
                "timestamp": "2024-01-15T10:30:00Z"
            },
            {
                "id": "metric-2",
                "metric_type": "token_usage",
                "total_tokens": 200,
                "timestamp": "2024-01-15T10:31:00Z"
            },
            {
                "id": "metric-3",
                "metric_type": "tool_execution",
                "execution_time_ms": 150.5,
                "timestamp": "2024-01-15T10:32:00Z"
            }
        ]
        mock_storage.get_metrics.return_value = complex_data

        summary = exporter.export_summary()

        assert summary["total_metrics"] == 3
        assert "token_usage" in summary["metric_types"]
        assert summary["metric_types"]["token_usage"]["count"] == 2
        assert "fields" in summary["metric_types"]["token_usage"]
        assert "total_tokens" in summary["metric_types"]["token_usage"]["fields"]
        assert summary["metric_types"]["token_usage"]["fields"]["total_tokens"]["sum"] == 300
        assert summary["metric_types"]["token_usage"]["fields"]["total_tokens"]["avg"] == 150.0
        assert "tool_execution" in summary["metric_types"]
        assert summary["metric_types"]["tool_execution"]["count"] == 1
        assert "execution_time_ms" in summary["metric_types"]["tool_execution"]["fields"]

    def test_empty_summary(self, exporter: MetricsExporter, mock_storage: MagicMock) -> None:
        """Test summary export with no metrics."""
        mock_storage.get_metrics.return_value = []

        summary = exporter.export_summary()

        assert summary["total_metrics"] == 0
        assert summary["metric_types"] == {}
        assert summary["time_range"]["start"] is None
        assert summary["time_range"]["end"] is None

    def test_summary_with_invalid_timestamps(self, exporter: MetricsExporter, mock_storage: MagicMock) -> None:
        """Test summary export with invalid timestamp formats."""
        complex_data = [
            {
                "id": "metric-1",
                "metric_type": "token_usage",
                "total_tokens": 100,
                "timestamp": "invalid-date-format"
            },
            {
                "id": "metric-2",
                "metric_type": "token_usage",
                "total_tokens": 200,
                "timestamp": None
            }
        ]
        mock_storage.get_metrics.return_value = complex_data

        summary = exporter.export_summary()

        # Should still work despite invalid timestamps
        assert summary["total_metrics"] == 2
        assert summary["time_range"]["start"] is None  # Invalid timestamps ignored
        assert summary["time_range"]["end"] is None

    def test_summary_with_non_numeric_metrics(
        self, exporter: MetricsExporter, mock_storage: MagicMock
    ) -> None:
        """Test summary export with metrics that have no numeric fields."""
        # Mock metrics with only string/non-numeric fields
        non_numeric_metrics = [
            {
                "id": "metric-1",
                "metric_type": "event",
                "event_name": "session_started",
                "timestamp": "2024-01-15T10:30:00Z",
                "status": "success"
            },
            {
                "id": "metric-2",
                "metric_type": "event",
                "event_name": "session_ended",
                "timestamp": "2024-01-15T11:30:00Z",
                "status": "success"
            }
        ]
        mock_storage.get_metrics.return_value = non_numeric_metrics

        summary = exporter.export_summary()

        # Should still have summary structure
        assert summary["total_metrics"] == 2
        assert "event" in summary["metric_types"]
        assert summary["metric_types"]["event"]["count"] == 2
        # Should have fields but no numeric statistics
        assert "fields" in summary["metric_types"]["event"]
        # Since there are no numeric fields, fields dict should be empty
        assert summary["metric_types"]["event"]["fields"] == {}


class TestGetAvailableFormats:
    """Tests for MetricsExporter.get_available_formats."""

    def test_returns_list(self, exporter: MetricsExporter) -> None:
        """Test that get_available_formats returns a list."""
        formats = exporter.get_available_formats()
        assert isinstance(formats, list)

    def test_json_is_available(self, exporter: MetricsExporter) -> None:
        """Test that JSON format is listed as available."""
        formats = exporter.get_available_formats()
        assert "json" in formats

    def test_csv_is_available(self, exporter: MetricsExporter) -> None:
        """Test that CSV format is listed as available."""
        formats = exporter.get_available_formats()
        assert "csv" in formats

    def test_prometheus_is_available(self, exporter: MetricsExporter) -> None:
        """Test that Prometheus format is listed as available."""
        formats = exporter.get_available_formats()
        assert "prometheus" in formats


class TestGetCurrentTimestamp:
    """Tests for timestamp generation."""

    def test_returns_string(self) -> None:
        """Test that ISO formatted string is returned."""
        from datetime import datetime

        from henchman.metrics.exporter import SummaryCalculator

        # SummaryCalculator.calculate uses it internally and returns it in exported_at
        summary = SummaryCalculator.calculate([], {})
        ts = summary["exported_at"]
        assert isinstance(ts, str)
        # Should be parseable as ISO format
        parsed = datetime.fromisoformat(ts)
        assert parsed is not None
