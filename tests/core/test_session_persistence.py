"""Disk faults, migration and concurrent-writer session persistence contracts."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

from henchman.core.session import SessionManager, SessionMessage


def test_legacy_migrates_without_changing_transcript(tmp_path: Path) -> None:
    manager = SessionManager(tmp_path)
    session = manager.create_session("project", tag="legacy")
    session.messages.append(SessionMessage(role="user", content="keep this"))
    path = tmp_path / f"{session.id}.json"
    legacy = session.to_json()
    path.write_text(legacy, encoding="utf-8")
    loaded = manager.load(session.id)
    manager.save(loaded)
    assert json.loads(path.read_text())["_storage"]["version"] == 1
    assert path.with_suffix(".json.bak").read_text() == legacy
    assert manager.load(session.id).messages == session.messages
    assert "_storage" not in loaded.to_dict()  # Export is portable, not a write grant.


@pytest.mark.parametrize("damage", ["truncated", "checksum", "shape"])
def test_corruption_recovers_prior_with_explicit_notice(tmp_path: Path, damage: str) -> None:
    manager = SessionManager(tmp_path)
    session = manager.create_session("project", tag="prior")
    path = manager.save(session)
    session.tag = "latest"
    manager.save(session)
    if damage == "truncated":
        path.write_text('{"id":', encoding="utf-8")
    elif damage == "shape":
        path.write_text("[]", encoding="utf-8")
    else:
        payload = json.loads(path.read_text())
        payload["tag"] = "tampered"
        path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.warns(UserWarning, match="Recovered prior session"):
        recovered = manager.load(session.id)
    assert recovered.tag == "prior"
    assert recovered.recovery_notice
    manager.save(recovered)
    assert manager.load(session.id).tag == "prior"
    # Never rotate corrupt bytes over the only known-good prior copy.
    assert json.loads(path.with_suffix(".json.bak").read_text())["tag"] == "prior"


def test_unrecoverable_and_future_format_fail_explicitly(tmp_path: Path) -> None:
    manager = SessionManager(tmp_path)
    session = manager.create_session("project")
    path = manager.save(session)
    path.write_text("{broken", encoding="utf-8")
    with pytest.raises(ValueError, match="No valid session copy"):
        manager.load(session.id)
    path.write_text(session.to_json(), encoding="utf-8")
    loaded = manager.load(session.id)
    manager.save(loaded)
    payload = json.loads(path.read_text())
    payload["_storage"]["version"] = 999
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="Unsupported session storage version"):
        manager.load(session.id)  # Never silently downgrade to an older backup.


def test_stale_writer_cannot_overwrite_or_resurrect_session(tmp_path: Path) -> None:
    first, second = SessionManager(tmp_path), SessionManager(tmp_path)
    session = first.create_session("project")
    first.save(session)
    stale = second.load(session.id)
    session.tag = "newer"
    first.save(session)
    stale.tag = "lost update"
    with pytest.raises(ValueError, match="changed on disk"):
        second.save(stale)
    assert first.load(session.id).tag == "newer"
    stale = second.load(session.id)
    first.delete(session.id)
    with pytest.raises(ValueError, match="changed on disk"):
        second.save(stale)
    assert not list(tmp_path.glob("*.json*"))


def test_recovered_writer_cannot_resurrect_deleted_prior_copy(tmp_path: Path) -> None:
    manager = SessionManager(tmp_path)
    session = manager.create_session("project")
    path = manager.save(session)
    manager.save(session)
    path.unlink()
    with pytest.warns(UserWarning, match="Recovered prior session"):
        recovered = manager.load(session.id)
    manager.delete(session.id)
    with pytest.raises(ValueError, match="changed on disk"):
        manager.save(recovered)


@pytest.mark.parametrize("boundary", ["backup", "current", "fsync"])
def test_save_fault_preserves_readable_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, boundary: str
) -> None:
    import henchman.core.session_persistence as persistence

    manager = SessionManager(tmp_path)
    session = manager.create_session("project", tag="committed")
    path = manager.save(session)
    session.tag = "pending"
    old_updated = session.last_updated
    replace = persistence.os.replace

    def fail_replace(source: str, target: Path) -> None:
        if target == (path if boundary == "current" else path.with_suffix(".json.bak")):
            raise OSError("injected replacement failure")
        replace(source, target)

    def fail_fsync(_fd: int) -> None:
        raise OSError("injected flush failure")

    monkeypatch.setattr(persistence.os, "replace", fail_replace)
    if boundary == "fsync":
        monkeypatch.setattr(persistence.os, "fsync", fail_fsync)
    with pytest.raises(OSError, match="injected"):
        manager.save(session)
    assert session.last_updated == old_updated
    assert manager.load(session.id).tag == "committed"
    assert not list(tmp_path.glob("*.tmp"))


def test_missing_current_recovery_is_listed_and_delete_removes_backup(tmp_path: Path) -> None:
    manager = SessionManager(tmp_path)
    session = manager.create_session("project", tag="prior")
    path = manager.save(session)
    manager.save(session)
    path.unlink()
    with pytest.warns(UserWarning, match="Recovered prior session"):
        assert manager.list_sessions("project")[0].id == session.id
    with pytest.warns(UserWarning, match="Recovered prior session"):
        assert manager.load(session.id[:8]).tag == "prior"
    manager.delete(session.id)
    assert manager.list_sessions() == []


@pytest.mark.parametrize("session_id", ["../escape", "/absolute", "bad*", "x\\y"])
def test_session_paths_reject_nonidentifiers(tmp_path: Path, session_id: str) -> None:
    manager = SessionManager(tmp_path)
    session = manager.create_session("project")
    session.id = session_id
    for action in (
        lambda: manager.save(session),
        lambda: manager.load(session_id),
        lambda: manager.delete(session_id),
    ):
        with pytest.raises(ValueError, match="Invalid session ID"):
            action()


def _wait_for_files(paths: list[Path], processes: list[subprocess.Popen[str]]) -> None:
    deadline = time.monotonic() + 30
    while not all(path.exists() for path in paths):
        assert all(
            process.poll() is None for process in processes
        ), "Child exited before checkpoint"
        assert time.monotonic() < deadline, "Child never reached checkpoint"
        time.sleep(0.01)


@pytest.mark.parametrize("after_replace", [False, True])
def test_process_termination_during_commit_keeps_readable_state(
    tmp_path: Path, after_replace: bool
) -> None:
    manager = SessionManager(tmp_path)
    session = manager.create_session("project", tag="before")
    path = manager.save(session)
    ready = tmp_path / "ready"
    script = f"""
import time
from pathlib import Path
from henchman.core.session import SessionManager
import henchman.core.session_persistence as storage
manager = SessionManager(Path({str(tmp_path)!r}))
session = manager.load({session.id!r})
session.tag = 'after'
replace = storage.os.replace
def checkpoint(source, target):
    if target == Path({str(path)!r}):
        if {after_replace!r}:
            replace(source, target)
        Path({str(ready)!r}).touch()
        while True:
            time.sleep(0.05)
    replace(source, target)
storage.os.replace = checkpoint
manager.save(session)
"""
    process = subprocess.Popen([sys.executable, "-c", script], text=True)
    try:
        _wait_for_files([ready], [process])
        process.kill()
        process.wait(timeout=10)
        loaded = manager.load(session.id)
        assert loaded.tag == ("after" if after_replace else "before")
        # Native locks are released by process death, so subsequent saves work.
        manager.save(loaded)
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=10)


def test_simultaneous_process_writers_reject_one_stale_update(tmp_path: Path) -> None:
    manager = SessionManager(tmp_path)
    session = manager.create_session("project")
    manager.save(session)
    script = """
import sys, time
from pathlib import Path
from henchman.core.session import SessionManager
root, session_id, name = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
manager = SessionManager(root)
session = manager.load(session_id)
(root / ('ready-' + name)).touch()
while not (root / 'go').exists():
    time.sleep(0.01)
session.tag = name
try:
    manager.save(session)
    outcome = 'saved'
except ValueError as exc:
    assert 'changed on disk' in str(exc), str(exc)
    outcome = 'conflict'
(root / ('result-' + name)).write_text(outcome, encoding='utf-8')
"""
    processes = [
        subprocess.Popen(
            [sys.executable, "-c", script, str(tmp_path), session.id, str(index)], text=True
        )
        for index in range(2)
    ]
    try:
        _wait_for_files([tmp_path / f"ready-{index}" for index in range(2)], processes)
        (tmp_path / "go").touch()
        for process in processes:
            assert process.wait(timeout=15) == 0
        outcomes = [(tmp_path / f"result-{index}").read_text() for index in range(2)]
        assert sorted(outcomes) == ["conflict", "saved"]
        assert manager.load(session.id).tag == str(outcomes.index("saved"))
    finally:
        for process in processes:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=10)
