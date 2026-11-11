"""Operational diagnostic evidence is projected before storage and on legacy reads."""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from decimal import Decimal

import pytest

from henchman.ops.observability import (
    CostTrackingService,
    DiagnosticTrackingService,
    TelemetryService,
)
from henchman.ops.store import OpsStore
from henchman.providers.usage import TokenPricing
from henchman.utils.evidence_redaction import EvidenceRedactor

OLD = 'ops-private-"old"'
NEW = "ops-private-new"


def test_diagnostic_projects_before_sqlite_and_keeps_input_detached(tmp_path):
    path = tmp_path / "only-owned.sqlite"
    store = OpsStore(path)
    raw = {"api_key": OLD, "failure": "rejected " + OLD, "nested": {"echo": OLD}}
    saved = DiagnosticTrackingService(store=store).record("fixture", status="fail", details=raw)
    assert raw["api_key"] == OLD
    assert OLD not in json.dumps(saved, ensure_ascii=False)
    assert saved["payload"]["failure"] == "rejected [REDACTED]"
    with closing(sqlite3.connect(path)) as connection:
        payload = connection.execute("SELECT payload_json FROM ops_events").fetchone()[0]
    assert OLD not in payload and json.dumps(OLD)[1:-1] not in payload
    assert saved == store.list_ops_events("diagnostic")[0]
    saved["payload"]["nested"]["echo"] = "changed returned copy"
    assert store.list_ops_events()[0]["payload"]["nested"]["echo"] == "[REDACTED]"


def test_retained_policy_environment_rotation_and_configuration_metadata(tmp_path, monkeypatch):
    monkeypatch.setenv("HENCHMAN_API_KEY", OLD)
    policy = EvidenceRedactor(["configured-private"])
    store = OpsStore(tmp_path / "ops.sqlite", evidence_redactor=policy)
    monkeypatch.setenv("HENCHMAN_API_KEY", NEW)
    result = TelemetryService(store=store).record("request", tokens=17, tool_calls=2, payload={
        "metadata": {"echo": f"{OLD} {NEW} configured-private", "api_key": "marked-private"},
        "earlier_echo": "marked-private",
    })
    text = json.dumps(result)
    assert all(value not in text for value in (OLD, NEW, "configured-private", "marked-private"))
    assert result["payload"]["tokens"] == 17
    assert result["payload"]["tool_calls"] == 2


def test_legacy_read_collects_marked_values_across_rows_without_rewriting(tmp_path):
    path = tmp_path / "legacy.sqlite"
    store = OpsStore(path)
    rows = [
        ("a" * 32, "diagnostic", "first", json.dumps({"failure": OLD}), "2026-11-08T00:00:00+00:00"),
        ("b" * 32, "diagnostic", "second", json.dumps({"api_key": OLD}), "2026-11-08T00:00:01+00:00"),
    ]
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.executemany("INSERT INTO ops_events VALUES (?, ?, ?, ?, ?)", rows)
    before = path.read_bytes()
    found = store.list_ops_events("diagnostic")
    assert found[0]["payload"]["failure"] == "[REDACTED]"
    assert [row["event_id"] for row in found] == ["a" * 32, "b" * 32]
    assert path.read_bytes() == before


def test_short_secret_preserves_accounting_structure_and_generated_correlation(tmp_path):
    policy = EvidenceRedactor(["0", "cost", "reported", "status"])
    store = OpsStore(tmp_path / "ops.sqlite", evidence_redactor=policy)
    cost = CostTrackingService(store=store)
    rate = Decimal("0.000000000000000000123")
    cost.record_usage(provider="provider0", model="model0", prompt_tokens=1000, completion_tokens=0,
                      pricing=TokenPricing(input_per_1k=rate, output_per_1k=Decimal(0)), reported_cost=0)
    result = store.list_ops_events("cost")[0]
    assert result["category"] == "cost"
    assert len(result["event_id"]) == 32 and "[REDACTED]" not in result["created_at"]
    assert result["payload"]["pricing"]["input_per_1k"] == str(rate)
    assert result["payload"]["cost_source"] == result["payload"]["usage_source"] == "reported"
    assert result["payload"]["provider"] == "provider[REDACTED]"
    assert cost.summary()["total_cost"] == 0
    status = DiagnosticTrackingService(store=store).record("check0", status="fail", details={})
    assert status["payload"]["status"] == "fail"


def test_arbitrary_identity_shaped_metadata_has_no_trusted_bypass(tmp_path):
    store = OpsStore(tmp_path / "ops.sqlite")
    result = store.record_ops_event(category=OLD, event_type=OLD, payload={
        "api_key": OLD, "event_id": OLD, "created_at": OLD, "status": OLD,
        "pricing": {"input_per_1k": OLD}, "currency": OLD,
    })
    assert OLD not in json.dumps(result, ensure_ascii=False)
    assert result["payload"]["event_id"] == "[REDACTED]"


def test_diagnostic_metadata_cannot_impersonate_cost_control_fields(tmp_path):
    policy = EvidenceRedactor(["0.125", "USD", "reported"])
    store = OpsStore(tmp_path / "ops.sqlite", evidence_redactor=policy)
    result = DiagnosticTrackingService(store=store).record("check", status="fail", details={
        "pricing": {"input_per_1k": "0.125", "currency": "USD"},
        "currency": "USD", "cost_source": "reported",
    })
    assert result["payload"]["pricing"]["input_per_1k"] == "[REDACTED]"
    assert result["payload"]["pricing"]["currency"] == "[REDACTED]"
    assert result["payload"]["currency"] == "[REDACTED]"
    assert result["payload"]["cost_source"] == "[REDACTED]"


def test_failed_write_keeps_original_error_and_does_not_publish_record(tmp_path, monkeypatch):
    path = tmp_path / "ops.sqlite"
    store = OpsStore(path)
    failure = sqlite3.OperationalError("fixture write denied")

    def fail():
        raise failure

    with monkeypatch.context() as patch:
        patch.setattr(store, "_connect", fail)
        with pytest.raises(sqlite3.OperationalError) as caught:
            DiagnosticTrackingService(store=store).record("check", status="fail", details={"api_key": OLD})
    assert caught.value is failure
    assert store.list_ops_events() == []
    assert OLD.encode() not in path.read_bytes()


def test_authority_state_and_credential_tables_are_not_evidence_rewritten(tmp_path):
    store = OpsStore(tmp_path / "ops.sqlite", evidence_redactor=EvidenceRedactor([OLD]))
    raw = {"api_key": OLD, "generation": 7}
    store.put_state("retained-authority", raw)
    assert store.get_state("retained-authority") == raw


def test_malformed_legacy_json_fails_value_free_without_erasing_original(tmp_path):
    path = tmp_path / "legacy.sqlite"
    store = OpsStore(path)
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.execute("INSERT INTO ops_events VALUES (?, ?, ?, ?, ?)",
                           ("c" * 32, "diagnostic", "bad", OLD, "2026-11-08T00:00:00+00:00"))
    before = path.read_bytes()
    with pytest.raises(ValueError) as caught:
        store.list_ops_events()
    assert OLD not in str(caught.value)
    assert "Stored operational event payload is invalid" in str(caught.value)
    assert path.read_bytes() == before
