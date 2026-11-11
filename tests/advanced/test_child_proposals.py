"""Staged child proposals require explicit, conflict-checked publication."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from henchman.advanced.checkpoint_models import CheckpointConflict
from henchman.advanced.child_proposals import ChildProposalService
from henchman.utils.evidence_redaction import EvidenceRedactor

pytestmark = pytest.mark.skipif(os.name != "posix", reason="POSIX publication backend")


def test_staged_files_are_private_until_review_and_explicit_publication(tmp_path: Path) -> None:
    (tmp_path / "edit.txt").write_text("original\n")
    (tmp_path / "remove.txt").write_text("remove\n")
    (tmp_path / "unrelated.txt").write_text("user work\n")
    service = ChildProposalService(tmp_path)
    proposal = service.begin(["edit.txt", "remove.txt", "new.txt"])
    service.stage(proposal, "edit.txt", "revised\n")
    service.stage(proposal, "remove.txt", None)
    service.stage(proposal, "new.txt", "new\n")
    assert service.read_staged(proposal, "edit.txt") == "revised\n"
    assert service.read_staged(proposal, "remove.txt") is None
    with pytest.raises(ValueError, match="scope"):
        service.read_staged(proposal, "unrelated.txt")

    assert (tmp_path / "edit.txt").read_text() == "original\n"
    assert (tmp_path / "remove.txt").exists()
    assert not (tmp_path / "new.txt").exists()
    service.seal(proposal)
    review = service.review(proposal)
    assert {item.path for item in review.files} == {"edit.txt", "remove.txt", "new.txt"}
    with pytest.raises(ValueError, match="sealed"):
        service.stage(proposal, "edit.txt", "late\n")
    plan = service.prepare(proposal, revision=review.revision)
    result = service.apply(plan)
    assert result.changed_paths == ("edit.txt", "new.txt", "remove.txt")
    assert (tmp_path / "edit.txt").read_text() == "revised\n"
    assert (tmp_path / "new.txt").read_text() == "new\n"
    assert (tmp_path / "new.txt").stat().st_mode & 0o777 == 0o600
    assert not (tmp_path / "remove.txt").exists()
    assert (tmp_path / "unrelated.txt").read_text() == "user work\n"


def test_changed_user_file_prevents_all_publication(tmp_path: Path) -> None:
    for name in ("a", "b"):
        (tmp_path / name).write_text("before")
    service = ChildProposalService(tmp_path)
    proposal = service.begin(["a", "b"])
    service.stage(proposal, "a", "agent-a")
    service.stage(proposal, "b", "agent-b")
    service.seal(proposal)
    plan = service.prepare(proposal, revision=service.review(proposal).revision)
    (tmp_path / "b").write_text("user-b")
    with pytest.raises(CheckpointConflict):
        service.apply(plan)
    assert (tmp_path / "a").read_text() == "before"
    assert (tmp_path / "b").read_text() == "user-b"


def test_interrupted_publication_can_be_recovered_without_losing_original(tmp_path: Path) -> None:
    (tmp_path / "file").write_text("before")

    def fail(stage: str) -> None:
        if stage == "published":
            raise RuntimeError("simulated interruption")

    service = ChildProposalService(tmp_path, fault=fail)
    proposal = service.begin(["file"])
    service.stage(proposal, "file", "after")
    service.seal(proposal)
    plan = service.prepare(proposal, revision=service.review(proposal).revision)
    with pytest.raises(RuntimeError, match="simulated interruption"):
        service.apply(plan)
    resumed = ChildProposalService(tmp_path)
    assert resumed.pending() == (plan,)
    assert resumed.recover(plan).changed_paths == ("file",)
    assert (tmp_path / "file").read_text() == "after"
    originals = resumed.retained_originals(plan)
    assert len(originals) == 1
    assert (tmp_path / originals[0]).read_text() == "before"


def test_scope_and_secrets_are_rejected_before_private_storage(tmp_path: Path) -> None:
    secret = "proposal-credential-canary"
    (tmp_path / "file").write_text("safe")
    service = ChildProposalService(tmp_path, redactor=EvidenceRedactor([secret]))
    with pytest.raises(ValueError):
        service.begin([".env"])
    proposal = service.begin(["file"])
    with pytest.raises(ValueError):
        service.stage(proposal, "other", "outside")
    with pytest.raises(ValueError):
        service.stage(proposal, "file", secret)
    store = tmp_path / ".henchman/tungsten/proposals"
    assert secret.encode() not in b"".join(path.read_bytes() for path in store.rglob("*") if path.is_file())
    assert (tmp_path / "file").read_text() == "safe"


def test_stale_review_and_forged_plan_do_not_publish(tmp_path: Path) -> None:
    (tmp_path / "file").write_text("before")
    service = ChildProposalService(tmp_path)
    proposal = service.begin(["file"])
    service.stage(proposal, "file", "proposed")
    service.seal(proposal)
    revision = service.review(proposal).revision
    with pytest.raises(CheckpointConflict):
        service.prepare(proposal, revision=revision - 1)
    plan = service.prepare(proposal, revision=revision)
    plan_path = tmp_path / ".henchman/tungsten/proposals/plans" / f"{plan}.json"
    payload = json.loads(plan_path.read_text())
    from henchman.advanced.checkpoint_models import FileState

    original = FileState.from_dict(payload["proposed"]["file"])
    payload["proposed"]["file"] = FileState("text", b"forged", original.mode, original.parents).to_dict()
    plan_path.write_text(json.dumps(payload))
    with pytest.raises(CheckpointConflict):
        service.apply(plan)
    assert (tmp_path / "file").read_text() == "before"


def test_forged_new_file_permissions_are_rejected(tmp_path: Path) -> None:
    service = ChildProposalService(tmp_path)
    proposal = service.begin(["new"])
    service.stage(proposal, "new", "content")
    service.seal(proposal)
    record = tmp_path / ".henchman/tungsten/proposals" / f"{proposal}.json"
    payload = json.loads(record.read_text())
    payload["proposed"]["new"]["mode"] = 0o777
    record.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="proposal"):
        service.review(proposal)
    assert not (tmp_path / "new").exists()


def test_review_content_not_just_revision_is_checked_before_publication(tmp_path: Path) -> None:
    from henchman.advanced.checkpoint_models import FileState

    (tmp_path / "file").write_text("before")
    service = ChildProposalService(tmp_path)
    proposal = service.begin(["file"])
    service.stage(proposal, "file", "reviewed")
    service.seal(proposal)
    review = service.review(proposal)
    record = tmp_path / ".henchman/tungsten/proposals" / f"{proposal}.json"
    payload = json.loads(record.read_text())
    prior = FileState.from_dict(payload["proposed"]["file"])
    payload["proposed"]["file"] = FileState("text", b"different", prior.mode, prior.parents).to_dict()
    record.write_text(json.dumps(payload))
    with pytest.raises(CheckpointConflict, match="after review"):
        service.prepare(proposal, revision=review.revision, expected_review=review)
    assert (tmp_path / "file").read_text() == "before"


def test_matching_forged_record_and_plan_cannot_replace_reviewed_content(tmp_path: Path) -> None:
    from henchman.advanced.checkpoint_models import FileState

    (tmp_path / "file").write_text("before")
    service = ChildProposalService(tmp_path)
    proposal = service.begin(["file"])
    service.stage(proposal, "file", "reviewed")
    service.seal(proposal)
    review = service.review(proposal)
    plan = service.prepare(proposal, revision=review.revision, expected_review=review)
    store = tmp_path / ".henchman/tungsten/proposals"
    for path in (store / f"{proposal}.json", store / "plans" / f"{plan}.json"):
        payload = json.loads(path.read_text())
        prior = FileState.from_dict(payload["proposed"]["file"])
        payload["proposed"]["file"] = FileState("text", b"different", prior.mode, prior.parents).to_dict()
        path.write_text(json.dumps(payload))
    with pytest.raises(CheckpointConflict, match="after review"):
        service.apply(plan, expected_review=review)
    assert (tmp_path / "file").read_text() == "before"


def test_concurrent_write_at_displacement_is_preserved(tmp_path: Path) -> None:
    path = tmp_path / "file"
    path.write_text("before")

    def user_write(stage: str) -> None:
        if stage == "before_displace":
            path.write_text("user edit")

    service = ChildProposalService(tmp_path, fault=user_write)
    proposal = service.begin(["file"])
    service.stage(proposal, "file", "agent edit")
    service.seal(proposal)
    plan = service.prepare(proposal, revision=service.review(proposal).revision)
    with pytest.raises(CheckpointConflict):
        service.apply(plan)
    assert path.read_text() == "user edit"
    assert service.pending() == (plan,)


def test_competing_proposal_cannot_overwrite_the_first_and_can_be_discarded(tmp_path: Path) -> None:
    path = tmp_path / "file"
    path.write_text("before")
    service = ChildProposalService(tmp_path)
    first, second = service.begin(["file"]), service.begin(["file"])
    plans = []
    for proposal, text in ((first, "first"), (second, "second")):
        service.stage(proposal, "file", text)
        service.seal(proposal)
        plans.append(service.prepare(proposal, revision=service.review(proposal).revision))
    service.apply(plans[0])
    with pytest.raises(CheckpointConflict):
        service.apply(plans[1])
    assert path.read_text() == "first"
    service.discard(second)
    assert path.read_text() == "first"
    with pytest.raises(FileNotFoundError):
        service.review(second)


def test_interrupted_publication_cannot_discard_its_original(tmp_path: Path) -> None:
    path = tmp_path / "file"
    path.write_text("before")

    def fault(stage: str) -> None:
        if stage == "published":
            raise RuntimeError("interrupted")

    service = ChildProposalService(tmp_path, fault=fault)
    proposal = service.begin(["file"])
    service.stage(proposal, "file", "after")
    service.seal(proposal)
    plan = service.prepare(proposal, revision=service.review(proposal).revision)
    with pytest.raises(RuntimeError):
        service.apply(plan)
    with pytest.raises(CheckpointConflict):
        service.discard(proposal)
    assert (tmp_path / service.retained_originals(plan)[0]).read_text() == "before"


def test_invalidation_failure_does_not_hide_publication_failure(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "file").write_text("before")

    def fault(stage: str) -> None:
        if stage == "published":
            raise RuntimeError("publication failure")

    service = ChildProposalService(tmp_path, fault=fault)
    proposal = service.begin(["file"])
    service.stage(proposal, "file", "after")
    service.seal(proposal)
    plan = service.prepare(proposal, revision=service.review(proposal).revision)
    original = service._invalidate
    calls = 0

    def invalidate(value):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise ValueError("verification index failure")
        original(value)

    monkeypatch.setattr(service, "_invalidate", invalidate)
    with pytest.raises(RuntimeError, match="publication failure") as caught:
        service.apply(plan)
    assert any("invalidation" in note for note in caught.value.__notes__)
    assert service.pending() == (plan,)


def test_revoked_authority_at_publication_retains_original_for_recovery(tmp_path: Path) -> None:
    path = tmp_path / "file"
    path.write_text("before")
    permitted = True

    def guard() -> None:
        if not permitted:
            raise PermissionError("authority revoked")

    def revoke(stage: str) -> None:
        nonlocal permitted
        if stage == "before_publish":
            permitted = False

    service = ChildProposalService(tmp_path, guard=guard, fault=revoke)
    proposal = service.begin(["file"])
    service.stage(proposal, "file", "after")
    service.seal(proposal)
    plan = service.prepare(proposal, revision=service.review(proposal).revision)
    with pytest.raises(PermissionError, match="authority revoked"):
        service.apply(plan)
    assert not path.exists()
    recovery = ChildProposalService(tmp_path)
    assert recovery.pending() == (plan,)
    assert (tmp_path / recovery.retained_originals(plan)[0]).read_text() == "before"
    recovery.recover(plan)
    assert path.read_text() == "after"


def test_revoked_authority_cannot_create_proposal_storage(tmp_path: Path) -> None:
    def guard() -> None:
        raise PermissionError("authority revoked")

    with pytest.raises(PermissionError, match="authority revoked"):
        ChildProposalService(tmp_path, guard=guard)
    assert not (tmp_path / ".henchman").exists()


@pytest.mark.parametrize("stage", ["prepared", "displaced", "stage_linked", "staged", "linked", "published", "recorded", "done"])
def test_process_death_recovery_uses_durable_publication_journal(tmp_path: Path, stage: str) -> None:
    (tmp_path / "file").write_text("before")
    service = ChildProposalService(tmp_path)
    proposal = service.begin(["file"])
    service.stage(proposal, "file", "after")
    service.seal(proposal)
    plan = service.prepare(proposal, revision=service.review(proposal).revision)
    code = """import os, sys
from pathlib import Path
from henchman.advanced.child_proposals import ChildProposalService
def fault(stage):
    if stage == sys.argv[3]:
        os._exit(73)
ChildProposalService(Path(sys.argv[1]), fault=fault).apply(sys.argv[2])
"""
    result = subprocess.run([sys.executable, "-c", code, str(tmp_path), plan, stage], check=False, timeout=30)
    assert result.returncode == 73
    resumed = ChildProposalService(tmp_path)
    if stage != "done":
        assert resumed.pending() == (plan,)
    assert resumed.recover(plan).changed_paths == ("file",)
    assert (tmp_path / "file").read_text() == "after"
    assert (tmp_path / resumed.retained_originals(plan)[0]).read_text() == "before"


def test_rotated_secret_blocks_review_and_publication(tmp_path: Path) -> None:
    path = tmp_path / "file"
    path.write_text("before")
    policy = EvidenceRedactor()
    service = ChildProposalService(tmp_path, redactor=policy)
    proposal = service.begin(["file"])
    service.stage(proposal, "file", "later-known-credential")
    service.seal(proposal)
    plan = service.prepare(proposal, revision=service.review(proposal).revision)
    policy.register_secret("later-known-credential")
    with pytest.raises(ValueError, match="credential"):
        service.review(proposal)
    with pytest.raises(ValueError, match="credential"):
        service.apply(plan)
    assert path.read_text() == "before"


def test_parent_directory_replaced_by_symlink_cannot_redirect_publication(tmp_path: Path) -> None:
    project = tmp_path / "project"
    outside = tmp_path / "outside"
    (project / "nested").mkdir(parents=True)
    outside.mkdir()
    (project / "nested/file").write_text("before")
    (outside / "file").write_text("outside")
    service = ChildProposalService(project)
    proposal = service.begin(["nested/file"])
    service.stage(proposal, "nested/file", "agent")
    service.seal(proposal)
    plan = service.prepare(proposal, revision=service.review(proposal).revision)
    (project / "nested").rename(project / "original-nested")
    (project / "nested").symlink_to(outside, target_is_directory=True)
    with pytest.raises((CheckpointConflict, ValueError)):
        service.apply(plan)
    assert (outside / "file").read_text() == "outside"
    assert (project / "original-nested/file").read_text() == "before"


async def test_interrupted_proposal_blocks_verification_until_recovered(tmp_path: Path) -> None:
    from henchman.advanced.plans import PlanExecutionService

    path = tmp_path / "file"
    path.write_text("before")
    checks = PlanExecutionService(tmp_path)
    check = checks.create_plan(steps=["edit"], checks=[{"kind": "file_contains", "path": "file", "text": "before"}])
    assert (await checks.verify_plan(check.plan_id))["checks_passed"]

    def fault(stage: str) -> None:
        if stage == "published":
            raise RuntimeError("interrupted")

    service = ChildProposalService(tmp_path, fault=fault)
    proposal = service.begin(["file"])
    service.stage(proposal, "file", "after")
    service.seal(proposal)
    plan = service.prepare(proposal, revision=service.review(proposal).revision)
    with pytest.raises(RuntimeError, match="interrupted"):
        service.apply(plan)
    with pytest.raises(ValueError, match="incomplete"):
        await checks.verify_plan(check.plan_id)
    assert not checks.get_plan(check.plan_id).last_verification["checks_passed"]
    assert checks.get_plan(check.plan_id).last_verification["invalidation_reason"] == "child_proposal_publication"
    ChildProposalService(tmp_path).recover(plan)
    assert not (await checks.verify_plan(check.plan_id))["checks_passed"]


@pytest.mark.parametrize("interrupted", ["proposal", "checkpoint"])
def test_checkpoint_and_proposal_publication_wait_for_each_others_recovery(tmp_path: Path, interrupted: str) -> None:
    from henchman.advanced.checkpoints import CheckpointService

    (tmp_path / "proposal-file").write_text("original")
    (tmp_path / "checkpoint-file").write_text("before")
    checkpoints = CheckpointService(tmp_path)
    checkpoint = checkpoints.begin(["checkpoint-file"], actor="test")
    (tmp_path / "checkpoint-file").write_text("after")
    checkpoints.complete(checkpoint.checkpoint_id)
    restore = checkpoints.preview(checkpoint.checkpoint_id, decision="reject")
    proposals = ChildProposalService(tmp_path)
    proposal = proposals.begin(["proposal-file"])
    proposals.stage(proposal, "proposal-file", "proposed")
    proposals.seal(proposal)
    publication = proposals.prepare(proposal, revision=proposals.review(proposal).revision)

    def fault(stage: str) -> None:
        if stage == "published":
            raise RuntimeError("interrupted")

    if interrupted == "proposal":
        proposals._fault = fault
        with pytest.raises(RuntimeError, match="interrupted"):
            proposals.apply(publication)
        with pytest.raises(CheckpointConflict, match="proposal"):
            checkpoints.apply(restore.plan_id)
        assert (tmp_path / "checkpoint-file").read_text() == "after"
        ChildProposalService(tmp_path).recover(publication)
        checkpoints.apply(restore.plan_id)
    else:
        checkpoints._fault = fault
        with pytest.raises(RuntimeError, match="interrupted"):
            checkpoints.apply(restore.plan_id)
        with pytest.raises(CheckpointConflict, match="restore"):
            proposals.apply(publication)
        assert (tmp_path / "proposal-file").read_text() == "original"
        CheckpointService(tmp_path).recover(restore.plan_id)
        proposals.apply(publication)
    assert (tmp_path / "proposal-file").read_text() == "proposed"
    assert (tmp_path / "checkpoint-file").read_text() == "before"


def test_checkpoint_and_proposal_publications_serialize_across_services(tmp_path: Path) -> None:
    from henchman.advanced.checkpoints import CheckpointService

    (tmp_path / "proposal-file").write_text("original")
    (tmp_path / "checkpoint-file").write_text("before")
    checkpoints = CheckpointService(tmp_path)
    captured = checkpoints.begin(["checkpoint-file"], actor="test")
    (tmp_path / "checkpoint-file").write_text("after")
    checkpoints.complete(captured.checkpoint_id)
    restore = checkpoints.preview(captured.checkpoint_id, decision="reject")
    entered, release, checkpoint_started = threading.Event(), threading.Event(), threading.Event()

    def pause(stage: str) -> None:
        if stage == "before_publish":
            entered.set()
            assert release.wait(5)

    def checkpoint_fault(stage: str) -> None:
        if stage == "before_displace":
            checkpoint_started.set()

    proposals = ChildProposalService(tmp_path, fault=pause)
    checkpoints._fault = checkpoint_fault
    proposal = proposals.begin(["proposal-file"])
    proposals.stage(proposal, "proposal-file", "proposed")
    proposals.seal(proposal)
    publication = proposals.prepare(proposal, revision=proposals.review(proposal).revision)
    failures: list[BaseException] = []

    def run(action) -> None:
        try:
            action()
        except BaseException as error:
            failures.append(error)

    first = threading.Thread(target=run, args=(lambda: proposals.apply(publication),))
    second = threading.Thread(target=run, args=(lambda: checkpoints.apply(restore.plan_id),))
    first.start()
    try:
        assert entered.wait(5)
        second.start()
        assert not checkpoint_started.wait(0.2)
    finally:
        release.set()
        first.join(10)
        if second.ident is not None:
            second.join(10)
    assert not first.is_alive() and not second.is_alive()
    assert not failures
    assert checkpoint_started.is_set()
    assert (tmp_path / "proposal-file").read_text() == "proposed"
    assert (tmp_path / "checkpoint-file").read_text() == "before"
