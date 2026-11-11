"""Metric evidence is projected before persistence and each export boundary."""

import json
import sqlite3
import traceback
from dataclasses import asdict
from types import SimpleNamespace

import pytest

from henchman.metrics.exporter import MetricsExporter
from henchman.metrics.models import TokenMetric, UsageMetric
from henchman.metrics.storage import MetricsQueryParams, MetricsStorage
from henchman.utils.evidence_redaction import EvidenceRedactor


def test_metric_storage_projects_marked_and_environment_credentials_before_sql(tmp_path, monkeypatch):
    monkeypatch.setenv("METRICS_TEST_API_KEY", "environment-metric-canary")
    storage = MetricsStorage(tmp_path / "metrics.db", retention_days=None)
    metric = TokenMetric(model="environment-metric-canary", provider="provider", prompt_tokens=12,
        metadata={"echo": "marked-metric-canary", "nested": {"access_token": "marked-metric-canary"}})
    original = asdict(metric)
    storage.store_metric(metric)
    with sqlite3.connect(storage.db_path) as connection:
        raw = repr(connection.execute("SELECT * FROM metrics").fetchall())
    for secret in ("environment-metric-canary", "marked-metric-canary"):
        assert secret not in raw
        assert secret.encode() not in storage.db_path.read_bytes()
    assert asdict(metric) == original
    row = storage.get_metrics()[0]
    assert row["prompt_tokens"] == 12 and row["id"] == metric.id
    assert json.loads(row["metadata"])["nested"]["access_token"] == "[REDACTED]"


def test_metric_policy_retains_rotation_and_preserves_fixed_schema(tmp_path, monkeypatch):
    policy = EvidenceRedactor(["model"])
    policy.register_config({"api_key": "${METRICS_PRIVATE_VALUE}"})
    monkeypatch.setenv("METRICS_PRIVATE_VALUE", "first-metric-canary")
    storage = MetricsStorage(tmp_path / "metrics.db", evidence_redactor=policy, retention_days=None)
    metric = TokenMetric(id="model", session_id="model", model="first-metric-canary", prompt_tokens=0)
    storage.store_metric(metric)
    monkeypatch.setenv("METRICS_PRIVATE_VALUE", "second-metric-canary")
    storage.store_metric(TokenMetric(model="first-metric-canary second-metric-canary"))
    rows = storage.get_metrics(session_id="model")
    assert len(rows) == 1 and rows[0]["id"] == rows[0]["session_id"] == "model"
    assert rows[0]["model"] == "[REDACTED]" and rows[0]["prompt_tokens"] == 0
    assert "first-metric-canary" not in repr(storage.get_metrics())
    assert "second-metric-canary" not in repr(storage.get_metrics())


def test_legacy_metric_reads_project_all_marked_rows_without_rewriting(tmp_path):
    storage = MetricsStorage(tmp_path / "metrics.db", retention_days=None)
    first, second = UsageMetric(command="legacy", session_id="session"), UsageMetric(command="legacy")
    storage.store_metric(first)
    storage.store_metric(second)
    with sqlite3.connect(storage.db_path) as connection:
        connection.execute("UPDATE metrics SET command = ?", ("legacy-metric-canary",))
        connection.execute("UPDATE metrics SET metadata = ? WHERE id = ?",
                           (json.dumps({"password": "legacy-metric-canary"}), second.id))
    before = storage.db_path.read_bytes()
    rows = storage.get_metrics()
    assert "legacy-metric-canary" not in repr(rows)
    assert "legacy-metric-canary" not in repr(storage.get_metrics_with_params(MetricsQueryParams(session_id="session")))
    assert "legacy-metric-canary" not in repr(storage.get_session_metrics("session"))
    assert storage.db_path.read_bytes() == before


@pytest.mark.parametrize("format_name", ["json", "csv", "prometheus", "summary"])
def test_exporter_projects_custom_storage_evidence_and_filters(tmp_path, monkeypatch, format_name):
    from henchman.metrics import exporter as module

    rows = [{"id": "id", "metric_type": "token_usage", "total_tokens": 4,
             "model": "marked-export-canary", "metadata": json.dumps({"api_key": "marked-export-canary"})}]
    original = json.loads(json.dumps(rows))
    calls = []
    storage = SimpleNamespace(get_metrics=lambda **filters: calls.append(filters) or rows)
    exporter = MetricsExporter(storage)
    payloads = []
    monkeypatch.setattr(module._requests, "post", lambda endpoint, **kwargs:
                        payloads.append((endpoint, kwargs["data"])) or SimpleNamespace(raise_for_status=lambda: None))
    if format_name in {"json", "csv"}:
        path = tmp_path / format_name
        getattr(exporter, "export_to_" + format_name)(path, unused_secret="marked-export-canary")
        output = path.read_text()
    elif format_name == "summary":
        output = repr(exporter.export_summary(unused_secret="marked-export-canary"))
    else:
        exporter.export_to_prometheus("https://metrics.invalid", unused_secret="marked-export-canary")
        assert payloads[0][0] == "https://metrics.invalid"
        output = payloads[0][1]
    assert "marked-export-canary" not in output
    assert rows == original and len(calls) == 1


def test_export_failure_projects_diagnostics_without_attaching_raw_exception(tmp_path, monkeypatch, caplog):
    from henchman.metrics import exporter as module

    policy = EvidenceRedactor(["failure-metric-canary"])
    storage = MetricsStorage(tmp_path / "metrics.db", evidence_redactor=policy)
    storage.store_metric(TokenMetric(total_tokens=1))
    exporter = MetricsExporter(storage)
    sent = []

    def fail(endpoint, **_kwargs):
        sent.append(endpoint)
        raise module._requests.exceptions.RequestException("connection failure-metric-canary")

    monkeypatch.setattr(module._requests, "post", fail)
    endpoint = "https://metrics.invalid/failure-metric-canary"
    with pytest.raises(ConnectionError) as caught:
        exporter.export_to_prometheus(endpoint)
    assert sent == ["https://metrics.invalid/failure-metric-canary"]
    assert "failure-metric-canary" not in "".join(traceback.format_exception(caught.value))
    assert "failure-metric-canary" not in caplog.text
    assert all(record.exc_info is None for record in caplog.records)


def test_direct_legacy_session_summary_collects_its_marked_metadata(tmp_path):
    storage = MetricsStorage(tmp_path / "metrics.db", retention_days=None)
    metric = UsageMetric(command="legacy", session_id="session")
    storage.store_metric(metric)
    with sqlite3.connect(storage.db_path) as connection:
        connection.execute("UPDATE metrics SET command = ?, metadata = ? WHERE id = ?",
                           ("summary-metric-canary", json.dumps({"password": "summary-metric-canary"}), metric.id))
    before = storage.db_path.read_bytes()
    assert "summary-metric-canary" not in repr(storage.get_session_metrics("session"))
    assert storage.db_path.read_bytes() == before


def test_malformed_legacy_metadata_is_an_explicit_value_free_failure(tmp_path):
    storage = MetricsStorage(tmp_path / "metrics.db", retention_days=None)
    storage.store_metric(UsageMetric(command="legacy"))
    with sqlite3.connect(storage.db_path) as connection:
        connection.execute("UPDATE metrics SET metadata = ?", ('{"password":"malformed-canary',))
    with pytest.raises(ValueError, match="Stored metric metadata is invalid") as caught:
        storage.get_metrics()
    assert "malformed-canary" not in str(caught.value)


@pytest.mark.parametrize("format_name", ["json", "csv", "prometheus"])
def test_marked_export_filter_registers_before_projecting_row_echoes(tmp_path, monkeypatch, format_name):
    from henchman.metrics import exporter as module

    rows = [{"id": "id", "metric_type": "token_usage", "model": "filter-only-canary", "metadata": "{}"}]
    storage = SimpleNamespace(get_metrics=lambda **_filters: rows)
    exporter = MetricsExporter(storage)
    payloads = []
    monkeypatch.setattr(module._requests, "post", lambda _endpoint, **kwargs:
                        payloads.append(kwargs["data"]) or SimpleNamespace(raise_for_status=lambda: None))
    if format_name == "prometheus":
        exporter.export_to_prometheus("https://metrics.invalid", unused_secret="filter-only-canary")
        output = payloads[0]
    else:
        path = tmp_path / format_name
        getattr(exporter, "export_to_" + format_name)(path, unused_secret="filter-only-canary")
        output = path.read_text()
    assert "filter-only-canary" not in output
    assert rows[0]["model"] == "filter-only-canary"


@pytest.mark.parametrize("format_name", ["json", "csv"])
def test_export_filesystem_failures_project_path_and_keep_errno(tmp_path, format_name):
    storage = MetricsStorage(tmp_path / "metrics.db", evidence_redactor=EvidenceRedactor(["path-metric-canary"]))
    storage.store_metric(TokenMetric(total_tokens=1))
    path = tmp_path / "path-metric-canary"
    path.mkdir()
    # Windows reports a directory write as PermissionError; compare the native
    # error instead of requiring POSIX's IsADirectoryError/EISDIR spelling.
    with pytest.raises(OSError) as original, path.open("w"):
        pass
    with pytest.raises(type(original.value)) as caught:
        getattr(MetricsExporter(storage), "export_to_" + format_name)(path)
    assert caught.value.errno == original.value.errno
    assert getattr(caught.value, "winerror", None) == getattr(original.value, "winerror", None)
    assert "path-metric-canary" not in str(caught.value)
    assert "path-metric-canary" not in "".join(traceback.format_exception(caught.value))


def test_explicit_export_policy_cannot_discard_rotating_storage_credentials(tmp_path, monkeypatch):
    from henchman.metrics import exporter as module

    inherited = EvidenceRedactor()
    storage = MetricsStorage(tmp_path / "metrics.db", evidence_redactor=inherited)
    storage.store_metric(TokenMetric(total_tokens=1))
    exporter = MetricsExporter(storage, evidence_redactor=EvidenceRedactor(["explicit-canary"]))
    inherited.register_secret("later-storage-canary")

    def fail(_endpoint, **_kwargs):
        raise module._requests.exceptions.RequestException("explicit-canary later-storage-canary")

    monkeypatch.setattr(module._requests, "post", fail)
    with pytest.raises(ConnectionError) as caught:
        exporter.export_to_prometheus("https://metrics.invalid")
    assert "explicit-canary" not in str(caught.value)
    assert "later-storage-canary" not in str(caught.value)


@pytest.mark.parametrize("format_name", ["json", "csv", "prometheus", "summary"])
def test_storage_query_os_failure_is_projected_before_export(tmp_path, format_name):
    import errno

    def fail(**_kwargs):
        raise OSError(errno.EIO, "query-metric-canary")

    exporter = MetricsExporter(SimpleNamespace(get_metrics=fail), evidence_redactor=EvidenceRedactor(["query-metric-canary"]))
    with pytest.raises(OSError) as caught:
        if format_name in {"json", "csv"}:
            getattr(exporter, "export_to_" + format_name)(tmp_path / format_name)
        elif format_name == "prometheus":
            exporter.export_to_prometheus("https://metrics.invalid")
        else:
            exporter.export_summary()
    assert caught.value.errno == errno.EIO
    assert "query-metric-canary" not in "".join(traceback.format_exception(caught.value))


def test_export_refreshes_policy_after_legacy_metadata_is_read(tmp_path, monkeypatch):
    from henchman.metrics import exporter as module

    storage = MetricsStorage(tmp_path / "metrics.db")
    storage.store_metric(TokenMetric(total_tokens=1))
    with sqlite3.connect(storage.db_path) as connection:
        connection.execute("UPDATE metrics SET metadata = ?", (json.dumps({"api_key": "learned-metric-canary"}),))
    exporter = MetricsExporter(storage, evidence_redactor=EvidenceRedactor())

    def fail(_endpoint, **_kwargs):
        raise module._requests.exceptions.RequestException("learned-metric-canary")

    monkeypatch.setattr(module._requests, "post", fail)
    with pytest.raises(ConnectionError) as caught:
        exporter.export_to_prometheus("https://metrics.invalid")
    assert "learned-metric-canary" not in str(caught.value)


@pytest.mark.parametrize("boundary", ["query", "write", "http"])
def test_export_failure_refreshes_credentials_learned_at_that_boundary(tmp_path, monkeypatch, boundary):
    from henchman.metrics import exporter as module

    inherited = EvidenceRedactor()
    storage = MetricsStorage(tmp_path / "metrics.db", evidence_redactor=inherited)
    storage.store_metric(TokenMetric(total_tokens=1))
    exporter = MetricsExporter(storage, evidence_redactor=EvidenceRedactor())

    def fail(*_args, **_kwargs):
        inherited.register_secret("boundary-metric-canary")
        if boundary == "http":
            raise module._requests.exceptions.RequestException("boundary-metric-canary")
        raise OSError(5, "boundary-metric-canary")

    if boundary == "query":
        monkeypatch.setattr(storage, "get_metrics", fail)
    elif boundary == "write":
        monkeypatch.setattr(module, "_write_metrics_csv", fail)
    else:
        monkeypatch.setattr(module._requests, "post", fail)
    with pytest.raises(OSError) as caught:
        if boundary == "http":
            exporter.export_to_prometheus("https://metrics.invalid")
        else:
            exporter.export_to_csv(tmp_path / "metrics.csv")
    assert "boundary-metric-canary" not in "".join(traceback.format_exception(caught.value))
