"""Strict bounded workflow codecs and revision transitions."""

import json

import pytest

from henchman.core.workflow_state import WorkflowError, WorkflowJournal, decode_state, encode_state


def test_state_roundtrip_preserves_stable_input_identity_and_explicit_failure():
    journal = WorkflowJournal("project", "session")
    record = journal.enqueue("inspect", kind="direct", role="engineer")
    permit = journal.claim(record.id, record.revision)
    journal.finish(permit, outcome="failure")
    restored = decode_state(encode_state(journal.snapshot()))
    assert restored == journal.snapshot()
    assert restored.inputs[0].state == "completed" and restored.inputs[0].outcome == "failure"


@pytest.mark.parametrize("field,value", [("version", True), ("version", 2), ("revision", True), ("revision", -1)])
def test_codec_rejects_invalid_version_or_revision(field, value):
    payload = WorkflowJournal("project", "session").snapshot().model_dump(mode="json")
    payload[field] = value
    with pytest.raises(WorkflowError, match="invalid_state"):
        decode_state(json.dumps(payload))


@pytest.mark.parametrize("revision", [True, 1.0, "1"])
def test_compare_and_swap_requires_an_integer_revision(revision):
    journal = WorkflowJournal("project", "session")
    record = journal.enqueue("first")
    with pytest.raises(WorkflowError, match="revision_conflict"):
        journal.edit(record.id, revision, "replacement")
    assert journal.snapshot().inputs[0].text == "first"


def test_forked_process_cannot_reuse_in_memory_dispatch_authority(monkeypatch):
    from henchman.core import workflow_state

    journal = WorkflowJournal("project", "session")
    record = journal.enqueue("parent only")
    original = workflow_state.os.getpid()
    monkeypatch.setattr(workflow_state.os, "getpid", lambda: original + 1)
    with pytest.raises(WorkflowError, match="process_authority_changed"):
        journal.claim(record.id, record.revision)


def test_extra_fields_and_duplicate_identities_are_not_silently_dropped():
    journal = WorkflowJournal("project", "session")
    journal.enqueue("first")
    payload = journal.snapshot().model_dump(mode="json")
    payload["inputs"].append(payload["inputs"][0])
    with pytest.raises(WorkflowError, match="invalid_state"):
        decode_state(json.dumps(payload))
    payload = journal.snapshot().model_dump(mode="json")
    payload["automatic_replay_authorized"] = True
    with pytest.raises(WorkflowError, match="invalid_state"):
        decode_state(json.dumps(payload))


def test_correlation_limit_is_explicit_and_duplicate_ids_do_not_consume_capacity():
    journal = WorkflowJournal("project", "session")
    item = journal.enqueue("request")
    permit = journal.claim(item.id, item.revision)
    for number in range(256):
        journal.correlate(permit, budget_run_id=f"run-{number}")
    before = journal.snapshot()
    journal.correlate(permit, budget_run_id="run-0")
    assert journal.snapshot() == before
    with pytest.raises(WorkflowError, match="input_correlation_limit"):
        journal.correlate(permit, budget_run_id="overflow")
    assert journal.snapshot() == before
