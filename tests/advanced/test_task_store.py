"""Task evidence updates are conditional, bounded, and safe across processes."""

import json
import multiprocessing
from pathlib import Path

import pytest

from henchman.advanced.task_store import TaskStore, TaskStoreError


def record(identity="task-012345abcdef", *, owner="owner-a"):
    return {"task_id": identity, "title": "original", "argv": ["display only"],
            "cwd": "/project", "status": "queued", "created_at": "2026-01-01T00:00:00+00:00",
            "started_at": None, "finished_at": None, "output_path": f"{identity}.log",
            "pid": None, "return_code": None, "metadata": {}, "revision": 0,
            "owner_id": owner, "operation_context": None}


def _writer(path, identity, ready, release):
    store = TaskStore(Path(path))
    current = next(item for item in store.read() if item["task_id"] == identity)
    ready.set()
    assert release.wait(15)
    store.replace(dict(current, title=identity), expected_revision=current["revision"])


def test_unrelated_process_writes_preserve_both_updates(tmp_path):
    path = tmp_path / "index.json"
    store = TaskStore(path)
    ids = ["task-000000000001", "task-000000000002"]
    for identity in ids:
        store.create(record(identity))
    context = multiprocessing.get_context("spawn")
    ready = [context.Event(), context.Event()]
    release = [context.Event(), context.Event()]
    workers = [context.Process(target=_writer, args=(str(path), identity, ready[i], release[i]))
               for i, identity in enumerate(ids)]
    try:
        for worker in workers:
            worker.start()
        assert all(event.wait(15) for event in ready)
        for i, worker in enumerate(workers):
            release[i].set()
            worker.join(15)
            assert worker.exitcode == 0
        assert {item["title"] for item in store.read()} == set(ids)
    finally:
        for worker in workers:
            if worker.is_alive():
                worker.terminate()
            worker.join()


def test_same_task_stale_revision_is_an_explicit_conflict(tmp_path):
    first = TaskStore(tmp_path / "index.json")
    original = first.create(record())
    second = TaskStore(first.path)
    stale = second.read()[0]
    changed = first.replace(dict(original, title="first"), expected_revision=original["revision"])
    with pytest.raises(TaskStoreError, match="revision"):
        second.replace(dict(stale, title="second"), expected_revision=stale["revision"])
    assert first.read() == (changed,)


def test_lifecycle_requires_exact_runtime_owner_and_terminal_is_immutable(tmp_path):
    store = TaskStore(tmp_path / "index.json")
    queued = store.create(record())
    started = dict(queued, status="started", started_at=queued["created_at"])
    with pytest.raises(TaskStoreError, match="ownership"):
        store.replace(started, expected_revision=queued["revision"], owner_id="different")
    started = store.replace(started, expected_revision=queued["revision"], owner_id="owner-a")
    done = store.replace(dict(started, status="failed", finished_at=started["created_at"]),
                         expected_revision=started["revision"], owner_id="owner-a")
    with pytest.raises(TaskStoreError, match="transition"):
        store.replace(dict(done, status="running", finished_at=None), expected_revision=done["revision"], owner_id="owner-a")


def test_read_is_detached_and_does_not_modify_legacy_bytes(tmp_path):
    path = tmp_path / "index.json"
    payload = record()
    payload.update(status="running", started_at=payload["created_at"])
    for key in ("revision", "owner_id", "operation_context"):
        payload.pop(key)
    raw = json.dumps([payload]).encode()
    path.write_bytes(raw)
    store = TaskStore(path)
    loaded = store.read()[0]
    assert loaded["status"] == "running" and loaded["owner_id"] is None
    loaded["metadata"]["changed"] = "not persisted"
    assert store.read()[0]["metadata"] == {}
    assert path.read_bytes() == raw


@pytest.mark.parametrize("fault", ["missing", "corrupt", "identity", "newer"])
def test_known_authority_cannot_be_silently_replaced(tmp_path, fault):
    path = tmp_path / "index.json"
    store = TaskStore(path)
    store.create(record())
    if fault == "missing":
        path.unlink()
    elif fault == "corrupt":
        path.write_text('{"secret": broken')
    elif fault == "identity":
        other = TaskStore(tmp_path / "other.json")
        other.create(record("task-000000000002"))
        path.write_bytes(other.path.read_bytes())
    else:
        payload = json.loads(path.read_text())
        payload["version"] = 999
        path.write_text(json.dumps(payload))
    before = path.read_bytes() if path.exists() else None
    with pytest.raises(TaskStoreError):
        store.create(record("task-000000000003"))
    assert (path.read_bytes() if path.exists() else None) == before


def test_versioned_integrity_and_limits_are_validated_before_replace(tmp_path):
    store = TaskStore(tmp_path / "index.json")
    saved = store.create(record())
    before = store.path.read_bytes()
    with pytest.raises(TaskStoreError):
        store.replace(dict(saved, title="x" * (8 * 1024 * 1024)), expected_revision=saved["revision"])
    assert store.path.read_bytes() == before
    payload = json.loads(before)
    payload["records"][0]["title"] = "modified without digest"
    store.path.write_text(json.dumps(payload))
    with pytest.raises(TaskStoreError, match="integrity"):
        store.read()


def test_new_process_handle_cannot_initialize_over_a_missing_known_index(tmp_path):
    store = TaskStore(tmp_path / "index.json")
    store.create(record())
    store.path.unlink()
    with pytest.raises(TaskStoreError, match="missing"):
        TaskStore(store.path).initialize()
    assert not store.path.exists()


@pytest.mark.parametrize("changes", [{"pid": 123}, {"started_at": "2026-01-01T00:00:00+00:00"},
                                     {"finished_at": "2026-01-01T00:00:00+00:00"}, {"return_code": 0}])
def test_queued_intent_cannot_claim_process_observations(tmp_path, changes):
    store = TaskStore(tmp_path / "index.json")
    with pytest.raises(TaskStoreError):
        store.create(dict(record(), **changes))
    assert not store.path.exists()
