"""Native content checkpoints preserve unrelated work and fail closed on conflicts."""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from henchman.advanced.checkpoints import CheckpointConflict, CheckpointService
from henchman.advanced.tungsten import TungstenSnapshotRecord
from henchman.utils.evidence_redaction import EvidenceRedactor

pytestmark = pytest.mark.skipif(os.name != "posix", reason="Descriptor-mediated restore backend is POSIX-only")


def test_edit_create_delete_rename_round_trip_keeps_dirty_files_and_git_index(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    for name in ("edit.txt", "delete.txt", "old.txt", "dirty.txt"):
        (tmp_path / name).write_bytes((name + " original\r\n").encode())
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
    index = (tmp_path / ".git/index").read_bytes()
    (tmp_path / "dirty.txt").write_bytes(b"unrelated dirty work")
    service = CheckpointService(tmp_path)
    checkpoint = service.begin(["edit.txt", "create.txt", "delete.txt", "old.txt", "new.txt"], actor="engineer")
    (tmp_path / "edit.txt").write_bytes(b"agent change\n")
    (tmp_path / "create.txt").write_bytes(b"created")
    (tmp_path / "delete.txt").unlink()
    (tmp_path / "old.txt").rename(tmp_path / "new.txt")
    service.complete(checkpoint.checkpoint_id)
    plan = service.preview(checkpoint.checkpoint_id, decision="reject")
    result = service.apply(plan.plan_id)
    assert result.changed_paths == ("create.txt", "delete.txt", "edit.txt", "new.txt", "old.txt")
    for name in ("edit.txt", "delete.txt", "old.txt"):
        assert (tmp_path / name).read_bytes() == (name + " original\r\n").encode()
    assert not (tmp_path / "create.txt").exists() and not (tmp_path / "new.txt").exists()
    assert (tmp_path / "dirty.txt").read_bytes() == b"unrelated dirty work"
    assert (tmp_path / ".git/index").read_bytes() == index


def test_user_change_conflicts_before_any_selected_file_is_mutated(tmp_path):
    for name in ("a", "b"):
        (tmp_path / name).write_text("before")
    service = CheckpointService(tmp_path)
    checkpoint = service.begin(["a", "b"], actor="engineer")
    for name in ("a", "b"):
        (tmp_path / name).write_text("agent")
    service.complete(checkpoint.checkpoint_id)
    plan = service.preview(checkpoint.checkpoint_id, decision="reject")
    (tmp_path / "b").write_text("user")
    with pytest.raises(CheckpointConflict):
        service.apply(plan.plan_id)
    assert (tmp_path / "a").read_text() == "agent"
    assert (tmp_path / "b").read_text() == "user"


def test_reject_one_hunk_preserves_the_other_and_invalidates_stale_preview(tmp_path):
    path = tmp_path / "code.txt"
    path.write_text("one\nkeep\nthree\n")
    service = CheckpointService(tmp_path)
    checkpoint = service.begin(["code.txt"], actor="engineer")
    path.write_text("ONE\nkeep\nTHREE\n")
    service.complete(checkpoint.checkpoint_id)
    review = service.review(checkpoint.checkpoint_id)
    assert len(review.files[0].hunks) == 2
    stale = service.preview(checkpoint.checkpoint_id, decision="reject")
    plan = service.preview(checkpoint.checkpoint_id, decision="reject", hunks={"code.txt": [0]})
    result = service.apply(plan.plan_id)
    assert result.changed_paths == ("code.txt",)
    assert result.invalidate_checks is True
    assert path.read_text() == "one\nkeep\nTHREE\n"
    with pytest.raises(CheckpointConflict):
        service.apply(stale.plan_id)


def test_secret_binary_oversize_and_excluded_bytes_never_become_restore_payloads(tmp_path):
    policy = EvidenceRedactor(["checkpoint-private-canary"])
    samples = {"secret.txt": b"checkpoint-private-canary", "binary": b"a\x00b", "large": b"x" * 101,
               ".env": b"never-persist", "ignored.txt": b"ignored-private"}
    (tmp_path / ".gitignore").write_text("ignored.txt\n")
    for name, data in samples.items():
        (tmp_path / name).write_bytes(data)
    service = CheckpointService(tmp_path, redactor=policy, max_file_bytes=100)
    checkpoint = service.begin(list(samples), actor="engineer")
    service.complete(checkpoint.checkpoint_id)
    statuses = {item.path: item.before.status for item in service.review(checkpoint.checkpoint_id).files}
    assert statuses == {"secret.txt": "secret", "binary": "binary", "large": "oversized",
                        ".env": "excluded", "ignored.txt": "excluded"}
    payload = b"".join(p.read_bytes() for p in (tmp_path / ".henchman/tungsten/checkpoints").rglob("*") if p.is_file())
    for canary in (b"checkpoint-private-canary", b"never-persist", b"ignored-private"):
        assert canary not in payload
    with pytest.raises(ValueError, match="restorable"):
        service.preview(checkpoint.checkpoint_id, decision="reject")


def test_legacy_hash_record_is_explicitly_non_restorable():
    record = TungstenSnapshotRecord.from_dict({"snapshot_id": "old", "name": "legacy", "created_at": "old", "files": []})
    assert record.restorable is False
    assert record.to_dict()["restorable"] is False


@pytest.mark.parametrize("stage", ["prepared", "displaced", "stage_linked", "staged", "linked", "published", "recorded", "done"])
def test_process_death_during_restore_has_durable_recovery(tmp_path, stage):
    path = tmp_path / "file.txt"
    path.write_text("before")
    service = CheckpointService(tmp_path)
    checkpoint = service.begin(["file.txt"], actor="engineer")
    path.write_text("after")
    service.complete(checkpoint.checkpoint_id)
    plan = service.preview(checkpoint.checkpoint_id, decision="reject")
    code = """import os, sys
from pathlib import Path
from henchman.advanced.checkpoints import CheckpointService
service = CheckpointService(Path(sys.argv[1]), fault=lambda stage: os._exit(73) if stage == sys.argv[3] else None)
service.apply(sys.argv[2])
"""
    environment = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[2] / "src"))
    completed = subprocess.run([sys.executable, "-c", code, str(tmp_path), plan.plan_id, stage], env=environment, timeout=10)
    assert completed.returncode == 73
    recovered = CheckpointService(tmp_path).recover(plan.plan_id)
    assert recovered.changed_paths == ("file.txt",)
    assert path.read_text() == "before"
    assert not CheckpointService(tmp_path).pending_restores()
    originals = CheckpointService(tmp_path).retained_originals(plan.plan_id)
    assert len(originals) == 1
    assert (tmp_path / originals[0]).read_text() == "after"


def test_retention_and_private_storage_do_not_remove_active_capture(tmp_path):
    path = tmp_path / "file"
    path.write_text("text")
    service = CheckpointService(tmp_path, max_checkpoints=2)
    first = service.begin(["file"], actor="engineer")
    second = service.begin(["file"], actor="engineer")
    service.complete(second.checkpoint_id)
    third = service.begin(["file"], actor="engineer")
    ids = {item.checkpoint_id for item in service.list_checkpoints()}
    assert ids == {first.checkpoint_id, third.checkpoint_id}
    for path in (tmp_path / ".henchman/tungsten/checkpoints").rglob("*"):
        assert path.stat().st_mode & 0o077 == 0
    assert json.loads((tmp_path / ".henchman/tungsten/checkpoints" / f"{first.checkpoint_id}.json").read_text())["version"] == 1


@pytest.mark.parametrize("stage", ["before_displace", "before_publish"])
def test_intervening_process_style_write_at_restore_boundary_is_not_overwritten(tmp_path, stage):
    path = tmp_path / "file"
    path.write_text("before")
    service = CheckpointService(tmp_path)
    record = service.begin(["file"], actor="engineer")
    path.write_text("agent")
    service.complete(record.checkpoint_id)
    plan = service.preview(record.checkpoint_id, decision="reject")

    def fault(boundary):
        if boundary == stage:
            path.write_text("intervening user bytes")

    racing = CheckpointService(tmp_path, fault=fault)
    with pytest.raises(CheckpointConflict):
        racing.apply(plan.plan_id)
    assert path.read_text() == "intervening user bytes"


def test_interrupted_restore_prevents_a_second_decision_from_changing_revision(tmp_path):
    for name in ("a", "b"):
        (tmp_path / name).write_text("before")
    service = CheckpointService(tmp_path)
    record = service.begin(["a", "b"], actor="engineer")
    for name in ("a", "b"):
        (tmp_path / name).write_text("agent")
    service.complete(record.checkpoint_id)
    first = service.preview(record.checkpoint_id, decision="reject", paths=["a"])
    second = service.preview(record.checkpoint_id, decision="reject", paths=["b"])

    def interrupt(stage):
        if stage == "prepared":
            raise OSError("injected interruption")

    with pytest.raises(OSError):
        CheckpointService(tmp_path, fault=interrupt).apply(first.plan_id)
    with pytest.raises(CheckpointConflict):
        service.apply(second.plan_id)
    assert (tmp_path / "b").read_text() == "agent"
    service.recover(first.plan_id)


def test_denied_symlink_hardlink_fifo_and_traversal_are_not_captured(tmp_path):
    outside = tmp_path.parent / "outside-checkpoint.txt"
    outside.write_text("outside original")
    (tmp_path / "sym").symlink_to(outside)
    os.link(outside, tmp_path / "hard")
    os.mkfifo(tmp_path / "fifo")
    service = CheckpointService(tmp_path)
    record = service.begin(["sym", "hard", "fifo"], actor="engineer")
    service.complete(record.checkpoint_id)
    assert all(file.before.status == "unsupported" for file in service.review(record.checkpoint_id).files)
    with pytest.raises(ValueError):
        service.begin(["../outside-checkpoint.txt"], actor="engineer")
    assert outside.read_text() == "outside original"


def test_storage_limits_and_aged_retention_are_enforced(tmp_path, monkeypatch):
    path = tmp_path / "file"
    path.write_text("before")
    service = CheckpointService(tmp_path, max_storage_bytes=2000, max_age_seconds=10)
    first = service.begin(["file"], actor="engineer")
    service.complete(first.checkpoint_id)
    with pytest.raises(ValueError, match="storage limit"):
        service.begin(["file"], actor="x" * 3000)
    monkeypatch.setattr("henchman.advanced.checkpoints.time.time", lambda: first.created_at + 11)
    service.prune()
    assert service.list_checkpoints() == ()


def test_accept_is_metadata_only_and_reject_restores_exact_mode(tmp_path):
    path = tmp_path / "file"
    path.write_bytes(b"before\r\n")
    path.chmod(0o640)
    service = CheckpointService(tmp_path)
    record = service.begin(["file"], actor="engineer")
    path.write_bytes(b"after\n")
    path.chmod(0o600)
    service.complete(record.checkpoint_id)
    accepted = service.apply(service.preview(record.checkpoint_id, decision="accept").plan_id)
    assert accepted.changed_paths == () and not accepted.invalidate_checks
    assert path.read_bytes() == b"after\n"
    service.apply(service.preview(record.checkpoint_id, decision="reject").plan_id)
    assert path.read_bytes() == b"before\r\n" and path.stat().st_mode & 0o777 == 0o640


@pytest.mark.parametrize("field,value", [("id", "0" * 32), ("revision", True), ("state", "invented"),
                                         ("created", float("nan")), ("project", [True, 1]), ("after", {})])
def test_corrupt_checkpoint_authority_never_changes_workspace(tmp_path, field, value):
    path = tmp_path / "file"
    path.write_text("before")
    service = CheckpointService(tmp_path)
    record = service.begin(["file"], actor="engineer")
    path.write_text("agent")
    service.complete(record.checkpoint_id)
    plan = service.preview(record.checkpoint_id, decision="reject")
    stored = tmp_path / f".henchman/tungsten/checkpoints/{record.checkpoint_id}.json"
    payload = json.loads(stored.read_text())
    payload[field] = value
    stored.write_text(json.dumps(payload))
    with pytest.raises(ValueError):
        service.apply(plan.plan_id)
    assert path.read_text() == "agent"


def test_forged_desired_content_with_a_valid_hash_is_not_restore_authority(tmp_path):
    import base64

    path = tmp_path / "file"
    path.write_text("before")
    service = CheckpointService(tmp_path)
    record = service.begin(["file"], actor="engineer")
    path.write_text("agent")
    service.complete(record.checkpoint_id)
    plan = service.preview(record.checkpoint_id, decision="reject")
    stored = tmp_path / f".henchman/tungsten/checkpoints/plans/{plan.plan_id}.json"
    payload = json.loads(stored.read_text())
    payload["changes"]["file"]["desired"]["content"] = base64.b64encode(b"injected").decode()
    payload["changes"]["file"]["desired"]["sha256"] = hashlib.sha256(b"injected").hexdigest()
    stored.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="decision"):
        service.apply(plan.plan_id)
    assert path.read_text() == "agent"


def test_corrupted_staging_file_is_not_published_by_recovery(tmp_path):
    path = tmp_path / "file"
    path.write_text("before")
    service = CheckpointService(tmp_path)
    record = service.begin(["file"], actor="engineer")
    path.write_text("agent")
    service.complete(record.checkpoint_id)
    plan = service.preview(record.checkpoint_id, decision="reject")

    def interrupt(stage):
        if stage == "staged":
            raise OSError("injected interruption")

    with pytest.raises(OSError):
        CheckpointService(tmp_path, fault=interrupt).apply(plan.plan_id)
    directory = tmp_path / f".henchman/tungsten/checkpoints/plans/{plan.plan_id}"
    (directory / "0.new").write_text("corrupt stage")
    with pytest.raises(ValueError, match="Staged restore"):
        service.recover(plan.plan_id)
    assert not path.exists()
    assert (directory / "0.old").read_text() == "agent"


def test_open_handle_writers_remain_recoverable_until_explicit_discard(tmp_path):
    path = tmp_path / "file"
    path.write_text("before")
    service = CheckpointService(tmp_path)
    record = service.begin(["file"], actor="engineer")
    path.write_text("agent")
    service.complete(record.checkpoint_id)
    plan = service.preview(record.checkpoint_id, decision="reject")
    with path.open("r+") as retained_writer:
        service.apply(plan.plan_id)
        retained_writer.seek(0)
        retained_writer.write("late user edit")
        retained_writer.truncate()
        retained_writer.flush()
    originals = service.retained_originals(plan.plan_id)
    assert (tmp_path / originals[0]).read_text() == "late user edit"
    assert path.read_text() == "before"
    service.discard(record.checkpoint_id)
    assert not (tmp_path / originals[0]).exists()


def test_partial_hunk_accepts_remain_explicit_after_another_hunk_is_rejected(tmp_path):
    path = tmp_path / "file"
    path.write_text("one\nkeep\nthree\n")
    service = CheckpointService(tmp_path)
    record = service.begin(["file"], actor="engineer")
    path.write_text("ONE\nkeep\nTHREE\n")
    service.complete(record.checkpoint_id)
    for index in (0, 1):
        service.apply(service.preview(record.checkpoint_id, decision="accept", hunks={"file": [index]}).plan_id)
    assert all(hunk.accepted for hunk in service.review(record.checkpoint_id).files[0].hunks)
    service.apply(service.preview(record.checkpoint_id, decision="reject", hunks={"file": [0]}).plan_id)
    hunks = service.review(record.checkpoint_id).files[0].hunks
    assert len(hunks) == 1 and hunks[0].accepted


def test_incomplete_capture_can_be_discarded_when_completion_exceeds_storage(tmp_path):
    path = tmp_path / "file"
    path.write_text("before")
    service = CheckpointService(tmp_path)
    record = service.begin(["file"], actor="engineer")
    usage = sum(item.stat().st_size for item in (tmp_path / ".henchman/tungsten/checkpoints").rglob("*") if item.is_file())
    bounded = CheckpointService(tmp_path, max_storage_bytes=usage + 10)
    path.write_text("agent" * 100)
    with pytest.raises(ValueError, match="storage limit"):
        bounded.complete(record.checkpoint_id)
    bounded.discard(record.checkpoint_id)
    assert bounded.list_checkpoints() == ()
    assert path.read_text() == "agent" * 100


def test_git_info_and_global_ignores_are_excluded_without_touching_index(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".git/info/exclude").write_text("local-secret\n")
    global_ignore = tmp_path.parent / (tmp_path.name + "-global-ignore")
    global_ignore.write_text("global-secret\n")
    subprocess.run(["git", "-C", str(tmp_path), "config", "core.excludesFile", str(global_ignore)], check=True)
    for name in ("local-secret", "global-secret", "visible"):
        (tmp_path / name).write_text("not for history" if "secret" in name else "public")
    service = CheckpointService(tmp_path)
    record = service.begin(["local-secret", "global-secret", "visible"], actor="engineer")
    service.complete(record.checkpoint_id)
    assert {file.path: file.before.status for file in service.review(record.checkpoint_id).files} == {
        "global-secret": "excluded", "local-secret": "excluded", "visible": "text",
    }
    assert not (tmp_path / ".git/index").exists()


def test_replaced_repository_identity_cannot_reuse_checkpoint_authority(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "file").write_text("original")
    service = CheckpointService(tmp_path)
    record = service.begin(["file"], actor="engineer")
    (tmp_path / "file").write_text("agent")
    service.complete(record.checkpoint_id)
    plan = service.preview(record.checkpoint_id, decision="reject")
    (tmp_path / ".git").rename(tmp_path / "old-repository")
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    with pytest.raises(CheckpointConflict):
        CheckpointService(tmp_path).apply(plan.plan_id)
    assert (tmp_path / "file").read_text() == "agent"


def test_parent_symlink_replacement_conflicts_without_touching_external_file(tmp_path):
    directory = tmp_path / "source"
    directory.mkdir()
    (directory / "file").write_text("original")
    service = CheckpointService(tmp_path)
    record = service.begin(["source/file"], actor="engineer")
    (directory / "file").write_text("agent")
    service.complete(record.checkpoint_id)
    plan = service.preview(record.checkpoint_id, decision="reject")
    outside = tmp_path.parent / (tmp_path.name + "-outside")
    outside.mkdir()
    (outside / "file").write_text("unrelated")
    directory.rename(tmp_path / "original-source")
    directory.symlink_to(outside, target_is_directory=True)
    with pytest.raises(CheckpointConflict):
        service.apply(plan.plan_id)
    assert (outside / "file").read_text() == "unrelated"


def test_later_credential_registration_blocks_historical_review_bytes_and_restore(tmp_path):
    policy = EvidenceRedactor()
    path = tmp_path / "file"
    path.write_text("later-registered-canary")
    service = CheckpointService(tmp_path, redactor=policy)
    record = service.begin(["file"], actor="later-registered-canary")
    path.write_text("agent text")
    service.complete(record.checkpoint_id)
    plan = service.preview(record.checkpoint_id, decision="reject")
    policy.register_secret("later-registered-canary")
    assert service.review(record.checkpoint_id).files[0].before.content is None
    assert service.list_checkpoints()[0].actor == "[REDACTED]"
    with pytest.raises(ValueError, match="non-restorable"):
        service.apply(plan.plan_id)
    assert path.read_text() == "agent text"
    service.discard(record.checkpoint_id)
    assert not list((tmp_path / ".henchman/tungsten/checkpoints").glob("*.json"))


def test_independent_process_captures_do_not_lose_each_others_records(tmp_path):
    (tmp_path / "file").write_text("original")
    CheckpointService(tmp_path)
    code = """import sys
from pathlib import Path
from henchman.advanced.checkpoints import CheckpointService
service = CheckpointService(Path(sys.argv[1]))
record = service.begin(['file'], actor=sys.argv[2])
service.complete(record.checkpoint_id)
"""
    environment = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[2] / "src"))
    processes = [subprocess.Popen([sys.executable, "-c", code, str(tmp_path), f"process-{index}"], env=environment)
                 for index in range(3)]
    try:
        assert all(process.wait(timeout=15) == 0 for process in processes)
    finally:
        for process in processes:
            if process.poll() is None:
                process.kill()
                process.wait()
    records = CheckpointService(tmp_path).list_checkpoints()
    assert {record.actor for record in records} == {f"process-{index}" for index in range(3)}
    assert all(record.state == "ready" for record in records)


def test_shared_service_threads_keep_capture_lifecycle_serialized(tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    (tmp_path / "file").write_text("original")
    service = CheckpointService(tmp_path)
    with ThreadPoolExecutor(max_workers=3) as executor:
        records = list(executor.map(lambda index: service.begin(["file"], actor=f"thread-{index}"), range(3)))
    assert {record.actor for record in service.list_checkpoints()} == {f"thread-{index}" for index in range(3)}
    assert len({record.checkpoint_id for record in records}) == 3


def test_large_line_count_is_file_restorable_but_explicitly_not_hunk_supported(tmp_path):
    path = tmp_path / "file"
    original = "repeat\n" * 5000
    path.write_text(original)
    service = CheckpointService(tmp_path)
    record = service.begin(["file"], actor="engineer")
    path.write_text(original.replace("repeat", "changed"))
    service.complete(record.checkpoint_id)
    file = service.review(record.checkpoint_id).files[0]
    assert file.restorable and file.hunk_status == "oversized" and file.hunks == ()
    with pytest.raises(ValueError, match="hunk"):
        service.preview(record.checkpoint_id, decision="reject", hunks={"file": [0]})
    service.apply(service.preview(record.checkpoint_id, decision="reject").plan_id)
    assert path.read_text() == original


def test_existing_public_checkpoint_directory_fails_closed(tmp_path):
    storage = tmp_path / ".henchman/tungsten/checkpoints"
    storage.mkdir(parents=True)
    storage.chmod(0o755)
    with pytest.raises(ValueError, match="private"):
        CheckpointService(tmp_path)
    assert not list(storage.iterdir())


def test_git_ignore_query_failure_is_actionable_and_does_not_capture(tmp_path, monkeypatch):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "file").write_text("private by unavailable policy")
    service = CheckpointService(tmp_path)

    def unavailable(*_args, **_kwargs):
        raise OSError("injected missing git")

    monkeypatch.setattr("henchman.advanced.checkpoint_files.subprocess.run", unavailable)
    with pytest.raises(ValueError, match="ignore policy"):
        service.begin(["file"], actor="engineer")
    assert service.list_checkpoints() == ()
