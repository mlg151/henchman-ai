"""Independent durable input authority, without provider or process replay."""

import json
import sqlite3
import subprocess
import sys
from contextlib import closing

import pytest

from henchman.core.workflow_state import WorkflowError
from henchman.ops.workflow_store import WorkflowStore
from henchman.utils.evidence_redaction import EvidenceRedactor


def queued(tmp_path):
    store = WorkflowStore(tmp_path / "ops.db")
    workflow = store.open_session("project", "session", create=True)
    record = workflow.enqueue("Review the change", input_id="input")
    return store, workflow, record


def test_restore_is_read_only_and_cannot_claim_another_runtime_queue(tmp_path):
    store, workflow, record = queued(tmp_path)
    before = store.path.read_bytes()
    restored = WorkflowStore.inspect(store.path, "project", "session", reference=workflow.reference)
    assert restored.inputs[0].state == "queued"
    assert store.path.read_bytes() == before
    other = WorkflowStore(store.path, expected_store_id=store.store_id).open_session("project", "session")
    with pytest.raises(WorkflowError, match="input_owner_changed"):
        other.claim(record.id, record.revision)
    armed = other.transfer_queued(record.id, record.revision)
    assert other.claim(armed.id, armed.revision) is not None
    assert workflow.snapshot().inputs[0].state == "started"


def test_unknown_started_work_cannot_be_sent_again_and_late_owner_can_finish(tmp_path):
    store, workflow, record = queued(tmp_path)
    permit = workflow.claim(record.id, record.revision)
    other = WorkflowStore(store.path).open_session("project", "session")
    assert other.report().inputs[0].state == "outcome_unknown"
    assert workflow.report().inputs[0].state == "started"
    with pytest.raises(WorkflowError, match="input_not_queued"):
        other.transfer_queued(record.id, other.snapshot().inputs[0].revision)
    workflow.finish(permit, outcome="success")
    workflow.finish(permit, outcome="success")
    assert other.report().inputs[0].state == "completed"


def test_known_authority_missing_or_replaced_does_not_create_empty_state(tmp_path):
    store, workflow, _ = queued(tmp_path)
    reference = workflow.reference
    store.path.unlink()
    with pytest.raises(WorkflowError):
        WorkflowStore.inspect(store.path, "project", "session", reference=reference)
    assert not store.path.exists()
    with pytest.raises(WorkflowError):
        workflow.enqueue("must not run")
    assert not store.path.exists()
    replacement = WorkflowStore(store.path)
    replacement.open_session("project", "session", create=True)
    with pytest.raises(WorkflowError, match="store_identity_mismatch"):
        WorkflowStore.inspect(store.path, "project", "session", reference=reference)


def test_redaction_removes_replayable_text_and_revisions_reject_stale_edits(tmp_path):
    policy = EvidenceRedactor()
    policy.register_secret("private-queue-canary")
    store = WorkflowStore(tmp_path / "ops.db", redactor=policy)
    workflow = store.open_session("project", "session", create=True)
    record = workflow.enqueue("use private-queue-canary")
    assert record.text is None and record.availability == "redacted"
    assert "private-queue-canary" not in store.path.read_bytes().decode("latin1")
    with pytest.raises(WorkflowError, match="input_payload_unavailable"):
        workflow.claim(record.id, record.revision)
    edited = workflow.edit(record.id, record.revision, "inspect current code")
    with pytest.raises(WorkflowError, match="revision_conflict"):
        workflow.edit(record.id, record.revision, "stale edit")
    assert workflow.snapshot().inputs[0].text == edited.text


def test_inspection_creates_nothing_and_rejects_corruption(tmp_path):
    path = tmp_path / "missing" / "ops.db"
    assert WorkflowStore.inspect(path, "project", "session") is None
    assert not path.parent.exists()
    store, workflow, _ = queued(tmp_path)
    with closing(sqlite3.connect(store.path)) as connection:
        connection.execute("UPDATE workflow_sessions SET state_json=?", (json.dumps({}),))
        connection.commit()
    with pytest.raises(WorkflowError, match="invalid_state"):
        WorkflowStore.inspect(store.path, "project", "session", reference=workflow.reference)


def test_independent_processes_cannot_both_claim_one_input(tmp_path):
    store, workflow, record = queued(tmp_path)
    script = '''
import sys
from pathlib import Path
from henchman.ops.workflow_store import WorkflowStore
from henchman.core.workflow_state import WorkflowError
workflow=WorkflowStore(Path(sys.argv[1])).open_session('project','session')
try:
    item=workflow.transfer_queued('input',1)
    permit=workflow.claim(item.id,item.revision)
except WorkflowError:
    print('denied')
else:
    print('claimed')
'''
    children = [subprocess.Popen([sys.executable, "-c", script, str(store.path)], stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, text=True) for _ in range(2)]
    outputs = [child.communicate(timeout=20) for child in children]
    assert all(child.returncode == 0 for child in children), outputs
    assert sorted(output.strip() for output, _ in outputs) == ["claimed", "denied"]
    assert workflow.snapshot().inputs[0].state == "started"


def test_distinct_entries_cannot_start_concurrently_in_one_session(tmp_path):
    store, workflow, first = queued(tmp_path)
    second = workflow.enqueue("second")
    other = WorkflowStore(store.path).open_session("project", "session")
    transferred = other.transfer_queued(second.id, second.revision)
    workflow.claim(first.id, first.revision)
    with pytest.raises(WorkflowError, match="workflow_dispatch_active"):
        other.claim(transferred.id, transferred.revision)


def test_rotated_credentials_project_read_only_report_without_rewriting_authority(tmp_path):
    from henchman.core.workflow_state import WorkflowGoal

    store, workflow, _ = queued(tmp_path)
    workflow.enqueue("newly-known-workflow-canary")
    workflow.set_goal(WorkflowGoal(id="goal", objective="Inspect newly-known-workflow-canary"),
                      expected_revision=workflow.snapshot().revision)
    before = store.path.read_bytes()
    store.redactor.register_secret("newly-known-workflow-canary")
    report = workflow.report()
    assert report.inputs[1].text is None
    assert report.goal.availability == "redacted"
    assert "newly-known-workflow-canary" not in report.model_dump_json()
    assert store.path.read_bytes() == before


@pytest.mark.parametrize("stage", ["claim:before_commit", "claim:after_commit", "effect", "finish:before_commit", "finish:after_commit"])
def test_crash_boundaries_do_not_replay_started_input(tmp_path, stage):
    store, workflow, _ = queued(tmp_path)
    marker = tmp_path / "effect"
    script = '''
import os,sys
from pathlib import Path
from henchman.ops.workflow_store import WorkflowStore
def fault(stage):
    if stage==sys.argv[2]: os._exit(73)
workflow=WorkflowStore(Path(sys.argv[1]),checkpoint=fault).open_session('project','session')
item=workflow.transfer_queued('input',1)
permit=workflow.claim(item.id,item.revision)
with open(sys.argv[3],'a') as stream:
    stream.write('effect\\n');stream.flush();os.fsync(stream.fileno())
if sys.argv[2]=='effect':os._exit(73)
workflow.finish(permit,outcome='success')
'''
    child = subprocess.run([sys.executable, "-c", script, str(store.path), stage, str(marker)], capture_output=True, text=True, timeout=20)
    assert child.returncode == 73, child.stderr
    restored = WorkflowStore(store.path).open_session("project", "session")
    state = restored.report().inputs[0].state
    assert state == ("queued" if stage == "claim:before_commit" else "completed" if stage == "finish:after_commit" else "outcome_unknown")
    if state != "queued":
        with pytest.raises(WorkflowError, match="input_not_queued"):
            restored.transfer_queued("input", restored.snapshot().inputs[0].revision)
    assert not marker.exists() or marker.read_text() == "effect\n"
