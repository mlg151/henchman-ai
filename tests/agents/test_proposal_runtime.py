"""Staged child work requires exact worker identity and explicit parent review."""

from __future__ import annotations

import asyncio
import copy
import json
from pathlib import Path

import pytest

from henchman.advanced.checkpoint_models import CheckpointConflict
from henchman.agents.proposal_runtime import ProposalCoordinator
from henchman.agents.workspace_ownership import WorkspaceBinding, WorkspaceOwnershipError


def coordinator(tmp_path: Path, paths: list[str]):
    session, parent = object(), object()
    binding = [session, 0, tmp_path]
    runtime = ProposalCoordinator(
        tmp_path, session=session, generation=0, parent=parent, paths=paths,
        current_binding=lambda: WorkspaceBinding(binding[2], binding[0], binding[1]),
    )
    return runtime, binding


async def test_child_stages_then_parent_reviews_exact_work_before_publication(tmp_path: Path) -> None:
    path = tmp_path / "file"
    path.write_text("before")
    runtime, _ = coordinator(tmp_path, ["file"])
    child = object()
    handle = runtime.reserve(child, paths=["file"], completed=lambda: True)
    gate = asyncio.Event()

    async def run():
        await gate.wait()
        workspace = runtime.workspace(handle, child)
        assert workspace.read("file") == "before"
        workspace.stage("file", "after")
        assert workspace.read("file") == "after"
        with pytest.raises(WorkspaceOwnershipError, match="outside_scope"):
            workspace.stage("other", "outside")

        async def inherited():
            with pytest.raises(WorkspaceOwnershipError, match="wrong_worker"):
                workspace.stage("file", "inherited")

        await asyncio.create_task(inherited())

    worker = asyncio.create_task(run())
    runtime.bind(handle, worker)
    with pytest.raises(WorkspaceOwnershipError, match="not_settled"):
        runtime.review(handle)
    gate.set()
    await worker
    assert path.read_text() == "before"
    review = runtime.review(handle)
    assert review.files[0].after.content == b"after"
    with pytest.raises(ValueError, match="review"):
        runtime.publish(handle, copy.copy(review))
    assert runtime.publish(handle, review).changed_paths == ("file",)
    assert path.read_text() == "after"
    await runtime.close()


async def test_changed_user_work_conflicts_and_child_can_be_discarded(tmp_path: Path) -> None:
    path = tmp_path / "file"
    path.write_text("before")
    runtime, _ = coordinator(tmp_path, ["file"])
    child = object()
    handle = runtime.reserve(child, paths=["file"], completed=lambda: True)

    async def run():
        runtime.workspace(handle, child).stage("file", "agent")

    worker = asyncio.create_task(run())
    runtime.bind(handle, worker)
    await worker
    review = runtime.review(handle)
    path.write_text("user")
    with pytest.raises(CheckpointConflict):
        runtime.publish(handle, review)
    assert path.read_text() == "user"
    runtime.discard(handle)
    await runtime.close()


async def test_parent_review_is_bound_to_exact_proposed_content(tmp_path: Path) -> None:
    from henchman.advanced.checkpoint_models import FileState

    path = tmp_path / "file"
    path.write_text("before")
    runtime, _ = coordinator(tmp_path, ["file"])
    child = object()
    handle = runtime.reserve(child, paths=["file"], completed=lambda: True)

    async def run():
        runtime.workspace(handle, child).stage("file", "reviewed")

    worker = asyncio.create_task(run())
    runtime.bind(handle, worker)
    await worker
    review = runtime.review(handle)
    proposal_file = tmp_path / ".henchman/tungsten/proposals" / f"{review.proposal_id}.json"
    payload = json.loads(proposal_file.read_text())
    old = FileState.from_dict(payload["proposed"]["file"])
    payload["proposed"]["file"] = FileState("text", b"altered", old.mode, old.parents).to_dict()
    proposal_file.write_text(json.dumps(payload))
    with pytest.raises(CheckpointConflict, match="after review"):
        runtime.publish(handle, review)
    assert path.read_text() == "before"
    runtime.discard(handle)
    await runtime.close()


async def test_runtime_result_and_session_identity_remain_authoritative(tmp_path: Path) -> None:
    path = tmp_path / "file"
    path.write_text("before")
    runtime, binding = coordinator(tmp_path, ["file"])
    child = object()
    completed = [False]
    handle = runtime.reserve(child, paths=["file"], completed=lambda: completed[0])

    async def run():
        runtime.workspace(handle, child).stage("file", "agent")

    worker = asyncio.create_task(run())
    runtime.bind(handle, worker)
    await worker
    with pytest.raises(WorkspaceOwnershipError, match="unsuccessful"):
        runtime.review(handle)
    completed[0] = True
    review = runtime.review(handle)
    binding[0] = object()
    with pytest.raises(WorkspaceOwnershipError, match="binding_changed"):
        runtime.publish(handle, review)
    assert path.read_text() == "before"


async def test_completion_observation_cannot_change_session_and_grant_review(tmp_path: Path) -> None:
    path = tmp_path / "file"
    path.write_text("before")
    runtime, binding = coordinator(tmp_path, ["file"])
    child = object()

    def switched() -> bool:
        binding[0] = object()
        return True

    handle = runtime.reserve(child, paths=["file"], completed=switched)

    async def run():
        runtime.workspace(handle, child).stage("file", "agent")

    worker = asyncio.create_task(run())
    runtime.bind(handle, worker)
    await worker
    with pytest.raises(WorkspaceOwnershipError, match="binding_changed"):
        runtime.review(handle)
    assert path.read_text() == "before"


async def test_cancellation_joins_the_exact_child_before_discarding(tmp_path: Path) -> None:
    path = tmp_path / "file"
    path.write_text("before")
    runtime, _ = coordinator(tmp_path, ["file"])
    child = object()
    handle = runtime.reserve(child, paths=["file"], completed=lambda: True)
    ready, cleaned = asyncio.Event(), asyncio.Event()

    async def run():
        try:
            runtime.workspace(handle, child).stage("file", "unpublished")
            ready.set()
            await asyncio.Event().wait()
        finally:
            await asyncio.sleep(0)
            cleaned.set()

    worker = asyncio.create_task(run())
    runtime.bind(handle, worker)
    await ready.wait()
    await runtime.cancel_and_discard(handle)
    assert worker.done() and cleaned.is_set()
    assert path.read_text() == "before"
    await runtime.close()


async def test_unbound_reservation_can_be_aborted_without_leaking_scope(tmp_path: Path) -> None:
    (tmp_path / "file").write_text("before")
    runtime, _ = coordinator(tmp_path, ["file"])
    first = runtime.reserve(object(), paths=["file"], completed=lambda: True)
    runtime.abort(first)
    second = runtime.reserve(object(), paths=["file"], completed=lambda: True)
    runtime.abort(second)
    assert (tmp_path / "file").read_text() == "before"
    await runtime.close()


async def test_completion_revoked_during_publication_preserves_original(tmp_path: Path, monkeypatch) -> None:
    from henchman.advanced.child_proposals import ChildProposalService

    path = tmp_path / "file"
    path.write_text("before")
    runtime, _ = coordinator(tmp_path, ["file"])
    child = object()
    completed = [True]
    handle = runtime.reserve(child, paths=["file"], completed=lambda: completed[0])

    async def run():
        runtime.workspace(handle, child).stage("file", "agent")

    worker = asyncio.create_task(run())
    runtime.bind(handle, worker)
    await worker
    review = runtime.review(handle)
    original = ChildProposalService._boundary

    def revoke(service, stage):
        if stage == "before_publish":
            completed[0] = False
        original(service, stage)

    monkeypatch.setattr(ChildProposalService, "_boundary", revoke)
    with pytest.raises(WorkspaceOwnershipError, match="unsuccessful"):
        runtime.publish(handle, review)
    assert not path.exists()
    recovery = ChildProposalService(tmp_path)
    plan, = recovery.pending()
    assert (tmp_path / recovery.retained_originals(plan)[0]).read_text() == "before"
    with pytest.raises(CheckpointConflict):
        runtime.discard(handle)
