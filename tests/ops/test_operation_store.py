"""Durable operation starts commit before granting a single effect dispatch."""

import hashlib
import json
import sqlite3
import subprocess
import sys
from contextlib import closing
from dataclasses import replace
from pathlib import Path

import pytest

from henchman.core.operation_recovery import (
    OperationContext,
    OperationRecoveryError,
    OperationResult,
)
from henchman.ops.operation_store import OperationStore, PersistentOperationJournal
from henchman.ops.store import OpsStore
from henchman.utils.evidence_redaction import EvidenceRedactor

CONTEXT = OperationContext("project", "session", "run", "turn", "engineer", "call")
DIGEST = hashlib.sha256(b"marker operation").hexdigest()


def prepared(path: Path) -> tuple[OperationStore, PersistentOperationJournal]:
    store = OperationStore(path)
    journal = store.open_session("project", "session", create=True)
    journal.queue(CONTEXT, tool_name="shell", effect="effectful", input_digest=DIGEST, operation_id="op")
    return store, journal


def test_reopen_recovers_unknown_then_reconciles_late_result(tmp_path: Path) -> None:
    store, journal = prepared(tmp_path / "ops.db")
    permit = journal.start("op")
    assert permit is not None
    restored = OperationStore(store.path, expected_store_id=store.store_id).resume_session(journal.reference)
    assert restored.recover().blocking_operation_ids == ("op",)
    assert restored.report().records[0].state == "outcome_unknown"
    assert restored.start("op") is None
    result = OperationResult("marker exists", True)
    restored.finish(permit, result)
    restored.finish(permit, result)
    assert journal.report().records[0].state == "completed"


def test_reference_never_creates_or_selects_another_authority(tmp_path: Path) -> None:
    store, journal = prepared(tmp_path / "ops.db")
    with pytest.raises(OperationRecoveryError, match="missing_session"):
        store.open_session("project", "other")
    other = OperationStore(tmp_path / "other.db")
    with pytest.raises(OperationRecoveryError, match="store_identity_mismatch"):
        other.resume_session(journal.reference)
    with pytest.raises(OperationRecoveryError, match="store_identity_mismatch"):
        OperationStore(store.path, expected_store_id="wrong")
    store.path.unlink()
    with pytest.raises(OperationRecoveryError):
        OperationStore(store.path, expected_store_id=store.store_id)
    assert not store.path.exists()
    with pytest.raises(OperationRecoveryError):
        journal.start("op")
    assert not store.path.exists()


def test_existing_ops_schema_and_namespaces_remain_intact(tmp_path: Path) -> None:
    path = tmp_path / "ops.db"
    ops = OpsStore(path)
    ops.put_state("existing", {"preserve": True})
    ops.set_schema_version("other", 7)
    store, journal = prepared(path)
    assert journal.start("op") is not None
    assert ops.get_state("existing") == {"preserve": True}
    assert ops.get_schema_version("other") == 7
    assert ops.get_schema_version("operation_recovery") == 1
    assert OperationStore(path).store_id == store.store_id


def test_failed_start_commit_grants_no_permit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store, journal = prepared(tmp_path / "ops.db")
    def fail(_connection: sqlite3.Connection) -> None:
        raise sqlite3.OperationalError("commit failure")
    monkeypatch.setattr(store, "_commit", fail)
    with pytest.raises(OperationRecoveryError, match="store_unavailable"):
        journal.start("op")
    restored = OperationStore(store.path).resume_session(journal.reference)
    assert restored.report().records[0].state == "queued"
    assert restored.start("op") is not None


@pytest.mark.parametrize("stage", ["start:before_commit", "start:after_commit", "effect", "finish:before_commit", "finish:after_commit"])
def test_process_crash_at_dispatch_boundaries_never_replays_effect(tmp_path: Path, stage: str) -> None:
    store, journal = prepared(tmp_path / "ops.db")
    marker = tmp_path / "effect-count"
    script = '''
import os,sys
from pathlib import Path
from henchman.ops.operation_store import OperationStore
from henchman.core.operation_recovery import OperationResult
path,store_id,stage,marker=sys.argv[1:]
def crash(checkpoint):
    if checkpoint == stage:
        os._exit(73)
store=OperationStore(Path(path),expected_store_id=store_id,checkpoint=crash)
journal=store.open_session('project','session')
permit=journal.start('op')
if permit is not None:
    with open(marker,'a') as output:
        output.write('effect\\n')
        output.flush()
        os.fsync(output.fileno())
    if stage == 'effect': os._exit(73)
    journal.finish(permit,OperationResult('effect recorded',True))
'''
    child = subprocess.run([sys.executable, "-c", script, str(store.path), store.store_id, stage, str(marker)],
                           capture_output=True, text=True, timeout=20)
    assert child.returncode == 73, child.stderr
    restored = OperationStore(store.path, expected_store_id=store.store_id).resume_session(journal.reference)
    report = restored.recover()
    expected = "queued" if stage == "start:before_commit" else "completed" if stage == "finish:after_commit" else "outcome_unknown"
    assert report.records[0].state == expected
    if expected == "queued":
        assert restored.start("op") is not None
    else:
        assert restored.start("op") is None
    expected_effects = int(stage in {"effect", "finish:before_commit", "finish:after_commit"})
    assert (len(marker.read_text().splitlines()) if marker.exists() else 0) == expected_effects


def test_independent_processes_contend_for_one_dispatch(tmp_path: Path) -> None:
    store, journal = prepared(tmp_path / "ops.db")
    marker = tmp_path / "effect-count"
    script = '''
import sys,time
from pathlib import Path
from henchman.ops.operation_store import OperationStore
path,store_id,marker=sys.argv[1:]
journal=OperationStore(Path(path),expected_store_id=store_id).open_session('project','session')
permit=journal.start('op')
if permit is not None:
    with open(marker,'a') as output: output.write('effect\\n')
print(int(permit is not None))
'''
    children = [subprocess.Popen([sys.executable, "-c", script, str(store.path), store.store_id, str(marker)],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(4)]
    outputs = [child.communicate(timeout=20) for child in children]
    assert all(child.returncode == 0 for child in children), outputs
    assert sum(int(output[0].strip()) for output in outputs) == 1
    assert marker.read_text().splitlines() == ["effect"]
    assert journal.recover().records[0].state == "outcome_unknown"


def test_retry_authority_not_persisted_and_stale_decision_rejected(tmp_path: Path) -> None:
    store, journal = prepared(tmp_path / "ops.db")
    journal.start("op")
    unknown = journal.cancel("op")
    token = journal.authorize_retry("op", expected_revision=unknown.revision)
    restored = OperationStore(store.path).resume_session(journal.reference)
    with pytest.raises(OperationRecoveryError, match="invalid_retry_authorization"):
        restored.retry(token, operation_id="retry", note="explicit user action")
    restored.resolve("op", expected_revision=unknown.revision, decision="abandon", note="User verified ambiguity")
    with pytest.raises(OperationRecoveryError, match="stale_revision"):
        journal.retry(token, operation_id="retry", note="stale action")
    assert len(journal.report().records) == 1


def test_retry_authority_cannot_cross_session_with_matching_attempt_and_revision(tmp_path: Path) -> None:
    store, first = prepared(tmp_path / "ops.db")
    second = store.open_session("project", "second", create=True)
    second.queue(replace(CONTEXT, session_id="second"), tool_name="shell", effect="effectful",
                 input_digest=DIGEST, operation_id="op")
    first.start("op")
    first_unknown = first.cancel("op")
    second.start("op")
    second.cancel("op")
    token = first.authorize_retry("op", expected_revision=first_unknown.revision)
    with pytest.raises(OperationRecoveryError, match="retry_session_mismatch"):
        second.retry(token, operation_id="retry", note="This user action belongs to another session")
    assert len(first.report().records) == len(second.report().records) == 1
    assert first.report().blocking_operation_ids == second.report().blocking_operation_ids == ("op",)


def test_durable_retry_commits_new_attempt_and_old_uncertainty_atomically(tmp_path: Path) -> None:
    store, journal = prepared(tmp_path / "ops.db")
    journal.start("op")
    unknown = journal.cancel("op")
    token = journal.authorize_retry("op", expected_revision=unknown.revision)
    retry = journal.retry(token, operation_id="retry", note="Explicit user accepted duplicate-effect risk")
    assert retry.retry_of == "op"
    assert journal.start("retry") is not None
    restored = OperationStore(store.path).resume_session(journal.reference)
    assert restored.report().records[0].state == "outcome_unknown"
    assert restored.report().records[0].resolution == "retried"
    assert restored.recover().blocking_operation_ids == ("retry",)


@pytest.mark.parametrize("stage", ["retry:before_commit", "retry:after_commit"])
def test_failed_retry_acknowledgement_keeps_atomic_history_and_consumes_token(tmp_path: Path, stage: str) -> None:
    store, journal = prepared(tmp_path / "ops.db")
    journal.start("op")
    unknown = journal.cancel("op")
    token = journal.authorize_retry("op", expected_revision=unknown.revision)
    def fail(checkpoint: str) -> None:
        if checkpoint == stage:
            raise OSError("injected persistence failure")
    store._checkpoint = fail
    with pytest.raises(OperationRecoveryError, match="store_unavailable"):
        journal.retry(token, operation_id="retry", note="Explicit user retry")
    store._checkpoint = lambda _stage: None
    with pytest.raises(OperationRecoveryError, match="invalid_retry_authorization"):
        journal.retry(token, operation_id="again", note="Token cannot be repeated")
    report = OperationStore(store.path).resume_session(journal.reference).report()
    committed = stage == "retry:after_commit"
    assert len(report.records) == (2 if committed else 1)
    assert report.records[0].resolution == ("retried" if committed else None)
    assert report.records[0].state == "outcome_unknown"


@pytest.mark.parametrize("operation", ["start", "finish"])
def test_commit_acknowledgement_failure_never_releases_a_second_dispatch(tmp_path: Path, operation: str) -> None:
    store, journal = prepared(tmp_path / "ops.db")
    permit = journal.start("op") if operation == "finish" else None
    def fail(checkpoint: str) -> None:
        if checkpoint == f"{operation}:after_commit":
            raise OSError("committed acknowledgement lost")
    store._checkpoint = fail
    with pytest.raises(OperationRecoveryError, match="store_unavailable"):
        if operation == "start":
            journal.start("op")
        else:
            assert permit is not None
            journal.finish(permit, OperationResult("observed effect", True))
    store._checkpoint = lambda _stage: None
    assert journal.start("op") is None
    restored = OperationStore(store.path).resume_session(journal.reference)
    record = restored.recover().records[0]
    assert record.state == ("completed" if operation == "finish" else "outcome_unknown")


def test_verified_user_result_is_distinct_from_original_tool_completion(tmp_path: Path) -> None:
    store, journal = prepared(tmp_path / "ops.db")
    journal.start("op")
    unknown = journal.cancel("op")
    result = OperationResult("User inspected marker on disk", True)
    journal.resolve("op", expected_revision=unknown.revision, decision="completed", note="Manual inspection", result=result)
    restored = OperationStore(store.path).resume_session(journal.reference)
    record = restored.report().records[0]
    assert record.state == "completed" and record.resolution == "verified"
    assert record.result == result and record.resolution_note == "Manual inspection"
    assert restored.start("op") is None


@pytest.mark.parametrize("damage", ["payload", "version", "identity"])
def test_corruption_and_newer_schema_fail_closed(tmp_path: Path, damage: str) -> None:
    store, journal = prepared(tmp_path / "ops.db")
    with closing(sqlite3.connect(store.path)) as connection, connection:
        if damage == "payload":
            connection.execute("UPDATE operation_sessions SET state_json='{}'")
        elif damage == "version":
            connection.execute("UPDATE schema_versions SET version=999 WHERE namespace='operation_recovery'")
        else:
            connection.execute("UPDATE operation_store SET store_id='changed'")
    with pytest.raises(OperationRecoveryError):
        journal.start("op")


def test_durable_evidence_is_projected_and_does_not_store_dispatch_capability(tmp_path: Path) -> None:
    policy = EvidenceRedactor(["private-credential"])
    store = OperationStore(tmp_path / "ops.db", redactor=policy)
    journal = store.open_session("project", "session", create=True)
    journal.queue(CONTEXT, tool_name="shell", effect="effectful", input_digest=DIGEST,
                  description="private-credential", operation_id="op")
    permit = journal.start("op")
    assert permit is not None
    journal.finish(permit, OperationResult("private-credential", False, "private-credential"))
    with closing(sqlite3.connect(store.path)) as connection:
        payload = connection.execute("SELECT state_json FROM operation_sessions").fetchone()[0]
    assert "private-credential" not in payload and permit.token not in payload
    assert "[REDACTED]" in payload
    assert json.loads(payload)["operations"][0]["record"]["context"]["tool_call_id"] == "call"
