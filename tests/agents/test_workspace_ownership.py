"""Explicit file ownership is transferred, never inferred from actor labels."""

from __future__ import annotations

import asyncio
import copy
import os
import pickle
from pathlib import Path

import pytest

from henchman.agents.workspace_ownership import (
    WorkspaceBinding,
    WorkspaceOwnership,
    WorkspaceOwnershipError,
)


def controller(tmp_path: Path, **kwargs):
    session = object()
    binding = [session, 0, tmp_path]
    ownership = WorkspaceOwnership(
        tmp_path, session=session, generation=0,
        current_binding=lambda: WorkspaceBinding(binding[2], binding[0], binding[1]), **kwargs,
    )
    return ownership, binding


async def test_missing_scope_and_actor_labels_never_grant_workspace_access(tmp_path):
    ownership, _ = controller(tmp_path)
    actor = object()
    root = ownership.open_root(actor)
    ownership.require_current(root, actor)
    with pytest.raises(WorkspaceOwnershipError, match="outside_scope"):
        ownership.require_write(root, actor, ["new.txt"])
    with pytest.raises(WorkspaceOwnershipError, match="opaque_mutation"):
        ownership.require_opaque_mutation(root, actor)
    with pytest.raises(WorkspaceOwnershipError, match="invalid_actor"):
        ownership.reserve(root, actor, "child", paths=[])
    child_actor = object()
    child = ownership.reserve(root, actor, child_actor)
    assert ownership.snapshot(child).paths == ()
    ownership.abort_reservation(root, actor, child)
    await ownership.close()


async def test_sibling_transfer_remains_held_after_worker_completion_until_review(tmp_path):
    ownership, _ = controller(tmp_path)
    actor, child_actor = object(), object()
    root = ownership.open_root(actor, paths=["a.txt", "b.txt"])
    child = ownership.reserve(root, actor, child_actor, paths=["a.txt"])
    with pytest.raises(WorkspaceOwnershipError, match="transferred"):
        ownership.require_write(root, actor, ["a.txt"])
    ownership.require_write(root, actor, ["b.txt"])
    with pytest.raises(WorkspaceOwnershipError, match="overlap"):
        ownership.reserve(root, actor, object(), paths=["a.txt"])

    async def run():
        ownership.require_write(child, child_actor, ["a.txt"])

    worker = asyncio.create_task(run())
    ownership.bind_worker(root, actor, child, worker)
    await worker
    assert ownership.snapshot(child).state == "settled"
    assert ownership.snapshot(child).outcome == "completed"
    with pytest.raises(WorkspaceOwnershipError, match="transferred"):
        ownership.require_write(root, actor, ["a.txt"])
    ownership.resolve(root, actor, child, disposition="reviewed")
    ownership.resolve(root, actor, child, disposition="reviewed")
    ownership.require_write(root, actor, ["a.txt"])
    with pytest.raises(WorkspaceOwnershipError, match="disposition"):
        ownership.resolve(root, actor, child, disposition="discarded")
    await ownership.close()


async def test_nested_subset_transfer_and_parent_join_do_not_release_unresolved_child(tmp_path):
    ownership, _ = controller(tmp_path)
    actor, child_actor, grand_actor = object(), object(), object()
    root = ownership.open_root(actor, paths=["a", "b", "c"])
    child = ownership.reserve(root, actor, child_actor, paths=["a", "b"])
    ready, release = asyncio.Event(), asyncio.Event()
    values = {}

    async def parent_work():
        with pytest.raises(WorkspaceOwnershipError, match="outside_scope"):
            ownership.reserve(child, child_actor, grand_actor, paths=["c"])
        grand = ownership.reserve(child, child_actor, grand_actor, paths=["a"])
        values["grand"] = grand

        async def nested():
            ownership.require_write(grand, grand_actor, ["a"])
            ready.set()
            await release.wait()

        task = asyncio.create_task(nested())
        ownership.bind_worker(child, child_actor, grand, task)
        with pytest.raises(WorkspaceOwnershipError, match="transferred"):
            ownership.require_write(child, child_actor, ["a"])
        ownership.require_write(child, child_actor, ["b"])
        await task
        # Deliberately omit disposition; the ancestor must not receive the path.

    task = asyncio.create_task(parent_work())
    ownership.bind_worker(root, actor, child, task)
    await ready.wait()
    release.set()
    await task
    with pytest.raises(WorkspaceOwnershipError, match="unresolved_descendants"):
        ownership.resolve(root, actor, child, disposition="reviewed")
    # Discard is recursive only after every descendant worker has joined.
    ownership.resolve(root, actor, child, disposition="discarded")
    assert ownership.snapshot(values["grand"]).disposition == "discarded"
    ownership.require_write(root, actor, ["a", "b"])
    await ownership.close()


async def test_binding_requires_exact_actor_worker_and_single_use_handle(tmp_path):
    ownership, _ = controller(tmp_path)
    actor, child_actor = object(), object()
    root = ownership.open_root(actor, paths=["a"])
    child = ownership.reserve(root, actor, child_actor, paths=["a"])
    with pytest.raises(WorkspaceOwnershipError, match="unbound"):
        ownership.require_write(child, child_actor, ["a"])

    async def run():
        with pytest.raises(WorkspaceOwnershipError, match="wrong_actor"):
            ownership.require_write(child, object(), ["a"])
        ownership.require_write(child, child_actor, ["a"])

        async def inherited():
            with pytest.raises(WorkspaceOwnershipError, match="wrong_worker"):
                ownership.require_write(child, child_actor, ["a"])
        await asyncio.create_task(inherited())

    worker = asyncio.create_task(run())
    ownership.bind_worker(root, actor, child, worker)
    with pytest.raises(WorkspaceOwnershipError, match="already_bound"):
        ownership.bind_worker(root, actor, child, worker)
    with pytest.raises(WorkspaceOwnershipError, match="wrong_worker"):
        ownership.require_write(child, child_actor, ["a"])
    await worker
    ownership.resolve(root, actor, child, disposition="discarded")
    with pytest.raises(WorkspaceOwnershipError, match="released"):
        ownership.require_write(child, child_actor, ["a"])
    followup = ownership.reserve(root, actor, child_actor, paths=["a"])
    assert followup is not child
    ownership.abort_reservation(root, actor, followup)
    await ownership.close()


async def test_opaque_handles_cannot_be_copied_reconstructed_or_cross_controller(tmp_path):
    ownership, _ = controller(tmp_path)
    actor = object()
    root = ownership.open_root(actor, paths=["a"])
    for attempt in (copy.copy, copy.deepcopy, pickle.dumps):
        with pytest.raises(TypeError):
            attempt(root)
    fake = object.__new__(type(root))
    other, _ = controller(tmp_path)
    for candidate, owner in [(fake, ownership), (root, other), ({"paths": ["a"]}, ownership)]:
        with pytest.raises(WorkspaceOwnershipError, match="unknown_handle"):
            owner.require_write(candidate, actor, ["a"])
    await ownership.close()
    await other.close()


async def test_unbound_creation_failure_abort_is_exact_and_idempotent(tmp_path):
    ownership, _ = controller(tmp_path)
    actor = object()
    root = ownership.open_root(actor, paths=["a"])
    child = ownership.reserve(root, actor, object(), paths=["a"])
    ownership.abort_reservation(root, actor, child)
    ownership.abort_reservation(root, actor, child)
    ownership.require_write(root, actor, ["a"])
    other = ownership.reserve(root, actor, object(), paths=["a"])
    worker = asyncio.create_task(asyncio.Event().wait())
    ownership.bind_worker(root, actor, other, worker)
    with pytest.raises(WorkspaceOwnershipError, match="already_bound"):
        ownership.abort_reservation(root, actor, other)
    worker.cancel()
    with pytest.raises(asyncio.CancelledError):
        await worker
    ownership.resolve(root, actor, other, disposition="discarded")
    await ownership.close()


async def test_failed_worker_retains_scope_and_review_cannot_certify_failed_work(tmp_path):
    ownership, _ = controller(tmp_path)
    actor = object()
    root = ownership.open_root(actor, paths=["a"])
    child = ownership.reserve(root, actor, object(), paths=["a"])
    failure = RuntimeError("worker failed")

    async def fail():
        raise failure

    worker = asyncio.create_task(fail())
    ownership.bind_worker(root, actor, child, worker)
    with pytest.raises(RuntimeError) as caught:
        await worker
    assert caught.value is failure
    assert ownership.snapshot(child).outcome == "failed"
    with pytest.raises(WorkspaceOwnershipError, match="unsuccessful"):
        ownership.resolve(root, actor, child, disposition="reviewed")
    ownership.resolve(root, actor, child, disposition="discarded")
    ownership.require_write(root, actor, ["a"])
    await ownership.close()


@pytest.mark.parametrize("action", ["cancel", "close"])
async def test_repeated_parent_cancellation_joins_then_retains_pending_disposition(tmp_path, action):
    started, cleaning, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
    values = {}

    async def parent():
        ownership, _ = controller(tmp_path)
        actor, child_actor = object(), object()
        root = ownership.open_root(actor, paths=["a"])
        child = ownership.reserve(root, actor, child_actor, paths=["a"])
        values.update(ownership=ownership, child=child)

        async def work():
            try:
                started.set()
                await asyncio.Event().wait()
            finally:
                cleaning.set()
                await release.wait()

        worker = asyncio.create_task(work())
        ownership.bind_worker(root, actor, child, worker)
        values["worker"] = worker
        await started.wait()
        if action == "cancel":
            await ownership.cancel(root, actor, child)
        else:
            await ownership.close()

    task = asyncio.create_task(parent())
    await cleaning.wait()
    task.cancel("first")
    await asyncio.sleep(0)
    task.cancel("second")
    await asyncio.sleep(0)
    assert not task.done()
    assert values["ownership"].snapshot(values["child"]).state == "running"
    release.set()
    with pytest.raises(asyncio.CancelledError) as caught:
        await task
    assert caught.value.args == ("first",)
    assert values["worker"].done()
    assert values["ownership"].snapshot(values["child"]).disposition is None
    await values["ownership"].close()


async def test_parent_failure_revokes_nested_workers_before_their_next_effect(tmp_path):
    ready, cleanup = asyncio.Event(), asyncio.Event()
    values = {}

    async def parent():
        ownership, _ = controller(tmp_path)
        actor, child_actor = object(), object()
        root = ownership.open_root(actor, paths=["a"])
        child = ownership.reserve(root, actor, child_actor, paths=["a"])
        values.update(ownership=ownership, child=child)

        async def work():
            try:
                ready.set()
                await asyncio.Event().wait()
            finally:
                with pytest.raises(WorkspaceOwnershipError, match="revoked|retired"):
                    ownership.require_write(child, child_actor, ["a"])
                cleanup.set()

        worker = asyncio.create_task(work())
        ownership.bind_worker(root, actor, child, worker)
        values["worker"] = worker
        await ready.wait()
        raise RuntimeError("parent failed")

    with pytest.raises(RuntimeError, match="parent failed"):
        await asyncio.create_task(parent())
    await asyncio.wait_for(cleanup.wait(), 1)
    await values["ownership"].close()
    assert values["worker"].done()


@pytest.mark.parametrize("change", ["session", "generation", "selection", "root", "parent"])
async def test_live_binding_or_physical_replacement_fails_closed(tmp_path, change):
    project = tmp_path / "project"
    project.mkdir()
    (project / "nested").mkdir()
    ownership, binding = controller(project)
    actor = object()
    root = ownership.open_root(actor, paths=["nested/file"])
    if change == "session":
        binding[0] = object()
    elif change == "generation":
        binding[1] += 1
    elif change == "selection":
        binding[2] = tmp_path / "different-project"
    elif change == "root":
        project.rename(tmp_path / "old")
        project.mkdir()
    else:
        (project / "nested").rename(project / "old-nested")
        (project / "nested").mkdir()
    with pytest.raises(WorkspaceOwnershipError):
        ownership.require_write(root, actor, ["nested/file"])
    await ownership.close()


@pytest.mark.parametrize("path", ["", ".", "../outside", "/absolute", "a/../b", "a//b", "./a", "a/", "a\\b", "C:target", "a\x00b", "a\nb", "e\u0301", "a.", "a ", "NUL", "con.txt", "a/" * 33 + "b"])
async def test_noncanonical_paths_rejected_before_any_transfer(tmp_path, path):
    ownership, _ = controller(tmp_path)
    with pytest.raises(WorkspaceOwnershipError, match="invalid_path"):
        ownership.open_root(object(), paths=[path])
    await ownership.close()


@pytest.mark.parametrize("kind", ["symlink", "hardlink", "directory", "fifo", "missing_parent"])
async def test_scope_is_regular_files_or_absence_under_existing_physical_parent(tmp_path, kind):
    if kind == "symlink":
        (tmp_path / "original").write_text("original")
        try:
            (tmp_path / "target").symlink_to(tmp_path / "original")
        except OSError:
            pytest.skip("Native symlink creation unavailable")
    elif kind == "hardlink":
        (tmp_path / "original").write_text("original")
        os.link(tmp_path / "original", tmp_path / "target")
    elif kind == "directory":
        (tmp_path / "target").mkdir()
    elif kind == "fifo":
        if not hasattr(os, "mkfifo"):
            pytest.skip("Native FIFO creation unavailable")
        os.mkfifo(tmp_path / "target")
    ownership, _ = controller(tmp_path)
    with pytest.raises(WorkspaceOwnershipError):
        ownership.open_root(object(), paths=["absent/target" if kind == "missing_parent" else "target"])
    await ownership.close()


async def test_aliases_bounds_and_failed_transfer_do_not_change_parent_scope(tmp_path):
    ownership, _ = controller(tmp_path, max_paths=2, max_nodes=3)
    actor = object()
    with pytest.raises(WorkspaceOwnershipError, match="alias"):
        ownership.open_root(actor, paths=["A", "a"])
    with pytest.raises(WorkspaceOwnershipError, match="scope_limit"):
        ownership.open_root(actor, paths=["a", "b", "c"])
    root = ownership.open_root(actor, paths=["a", "b"])
    with pytest.raises(WorkspaceOwnershipError, match="outside_scope"):
        ownership.reserve(root, actor, object(), paths=["a", "c"])
    ownership.require_write(root, actor, ["a", "b"])
    child = ownership.reserve(root, actor, object(), paths=["a"])
    ownership.abort_reservation(root, actor, child)
    following = ownership.reserve(root, actor, object(), paths=["a"])
    ownership.abort_reservation(root, actor, following)
    with pytest.raises(WorkspaceOwnershipError, match="node_limit"):
        ownership.reserve(root, actor, object(), paths=[])
    await ownership.close()


async def test_revocation_and_close_do_not_restore_parent_write_authority(tmp_path):
    ownership, _ = controller(tmp_path)
    actor = object()
    root = ownership.open_root(actor, paths=["a"])
    child = ownership.reserve(root, actor, object(), paths=["a"])
    ownership.retire()
    with pytest.raises(WorkspaceOwnershipError, match="retired"):
        ownership.require_write(root, actor, ["a"])
    await ownership.close()
    await ownership.close()
    assert ownership.snapshot(child).revoked
    assert ownership.snapshot(child).disposition is None
    with pytest.raises(WorkspaceOwnershipError, match="retired"):
        ownership.open_root(actor, paths=["a"])


async def test_real_racing_reservations_have_one_winner(tmp_path):
    ownership, _ = controller(tmp_path)
    actor = object()
    root = ownership.open_root(actor, paths=["a"])
    # Synchronous admission is confined to the exact parent worker. Delegating
    # admission to a second task cannot impersonate that parent.
    async def foreign():
        with pytest.raises(WorkspaceOwnershipError, match="wrong_worker"):
            ownership.reserve(root, actor, object(), paths=["a"])
    await asyncio.gather(*(foreign() for _ in range(12)))
    child = ownership.reserve(root, actor, object(), paths=["a"])
    with pytest.raises(WorkspaceOwnershipError, match="overlap"):
        ownership.reserve(root, actor, object(), paths=["a"])
    ownership.abort_reservation(root, actor, child)
    await ownership.close()


async def test_pending_worker_cancellation_refuses_effect_before_next_await(tmp_path):
    ownership, _ = controller(tmp_path)
    actor, child_actor = object(), object()
    root = ownership.open_root(actor, paths=["a"])
    child = ownership.reserve(root, actor, child_actor, paths=["a"])

    async def work():
        asyncio.current_task().cancel("original stop")
        with pytest.raises(WorkspaceOwnershipError, match="worker_cancelling"):
            ownership.require_write(child, child_actor, ["a"])
        with pytest.raises(WorkspaceOwnershipError, match="worker_cancelling"):
            ownership.reserve(child, child_actor, object(), paths=[])
        await asyncio.sleep(0)

    task = asyncio.create_task(work())
    ownership.bind_worker(root, actor, child, task)
    with pytest.raises(asyncio.CancelledError, match="original stop"):
        await task
    ownership.resolve(root, actor, child, disposition="discarded")
    await ownership.close()


async def test_empty_mutation_targets_do_not_turn_readonly_scope_into_a_permit(tmp_path):
    ownership, _ = controller(tmp_path)
    actor = object()
    root = ownership.open_root(actor)
    with pytest.raises(WorkspaceOwnershipError, match="empty_mutation"):
        ownership.require_write(root, actor, [])
    await ownership.close()


async def test_lost_project_retires_prior_authority(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    ownership, _ = controller(project)
    actor = object()
    root = ownership.open_root(actor, paths=["a"])
    project.rename(tmp_path / "old")
    with pytest.raises(WorkspaceOwnershipError):
        ownership.require_write(root, actor, ["a"])
    (tmp_path / "old").rename(project)
    with pytest.raises(WorkspaceOwnershipError, match="retired"):
        ownership.require_write(root, actor, ["a"])
    await ownership.close()


async def test_binding_callback_failure_is_preserved_and_cannot_reactivate_old_scope(tmp_path):
    session, actor = object(), object()
    failure = RuntimeError("binding unavailable")
    failed = False

    def binding():
        if failed:
            raise failure
        return WorkspaceBinding(tmp_path, session, 0)

    ownership = WorkspaceOwnership(tmp_path, session=session, generation=0, current_binding=binding)
    root = ownership.open_root(actor, paths=["a"])
    failed = True
    with pytest.raises(RuntimeError) as caught:
        ownership.require_write(root, actor, ["a"])
    assert caught.value is failure
    failed = False
    with pytest.raises(WorkspaceOwnershipError, match="retired"):
        ownership.require_write(root, actor, ["a"])
    await ownership.close()


async def test_close_joins_all_siblings_even_when_one_cleanup_fails(tmp_path):
    ownership, _ = controller(tmp_path)
    actor = object()
    root = ownership.open_root(actor, paths=["a", "b"])
    a = ownership.reserve(root, actor, object(), paths=["a"])
    b = ownership.reserve(root, actor, object(), paths=["b"])
    entered, cleaning, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
    failure = RuntimeError("owned cleanup failed")

    async def failing():
        try:
            await asyncio.Event().wait()
        finally:
            raise failure

    async def slow():
        try:
            entered.set()
            await asyncio.Event().wait()
        finally:
            cleaning.set()
            await release.wait()

    first, second = asyncio.create_task(failing()), asyncio.create_task(slow())
    ownership.bind_worker(root, actor, a, first)
    ownership.bind_worker(root, actor, b, second)
    await entered.wait()
    closing = asyncio.create_task(ownership.close())
    await cleaning.wait()
    assert not closing.done()
    release.set()
    with pytest.raises(RuntimeError) as caught:
        await closing
    assert caught.value is failure
    assert first.done() and second.done()
    assert ownership.snapshot(a).outcome == "failed"
    assert ownership.snapshot(b).outcome == "cancelled"


async def test_foreign_thread_cannot_reuse_loop_authority(tmp_path):
    ownership, _ = controller(tmp_path)
    actor = object()
    root = ownership.open_root(actor, paths=["a"])

    def other_thread():
        with pytest.raises(WorkspaceOwnershipError, match="wrong_runtime"):
            ownership.require_write(root, actor, ["a"])

    await asyncio.to_thread(other_thread)
    ownership.require_write(root, actor, ["a"])
    await ownership.close()


@pytest.mark.parametrize("cancel_parent", [False, True])
async def test_child_effect_before_parent_done_callback_observes_parent_revocation(tmp_path, cancel_parent):
    go = asyncio.Event()
    values = {}

    async def parent():
        ownership, _ = controller(tmp_path)
        actor, child_actor = object(), object()
        root = ownership.open_root(actor, paths=["a"])
        child = ownership.reserve(root, actor, child_actor, paths=["a"])
        values["ownership"] = ownership

        async def work():
            await go.wait()
            with pytest.raises(WorkspaceOwnershipError, match="ancestor_unavailable|revoked|retired"):
                ownership.require_write(child, child_actor, ["a"])

        worker = asyncio.create_task(work())
        ownership.bind_worker(root, actor, child, worker)
        values["worker"] = worker
        await asyncio.sleep(0)
        if cancel_parent:
            asyncio.current_task().cancel("parent cancellation")
        # This queues the child ahead of the parent's done callbacks.
        go.set()
        if cancel_parent:
            await asyncio.sleep(0)

    task = asyncio.create_task(parent())
    if cancel_parent:
        with pytest.raises(asyncio.CancelledError, match="parent cancellation"):
            await task
    else:
        await task
    await values["worker"]
    await values["ownership"].close()


async def test_root_binding_cannot_move_to_an_inherited_task(tmp_path):
    ownership, _ = controller(tmp_path)

    async def inherited():
        with pytest.raises(WorkspaceOwnershipError, match="wrong_worker"):
            ownership.open_root(object(), paths=["a"])

    await asyncio.create_task(inherited())
    root = ownership.open_root(object(), paths=["a"])
    assert ownership.snapshot(root).state == "running"
    await ownership.close()


async def test_owned_child_cannot_retire_runtime_or_join_itself_through_close(tmp_path):
    ownership, _ = controller(tmp_path)
    actor, child_actor = object(), object()
    root = ownership.open_root(actor, paths=["a"])
    child = ownership.reserve(root, actor, child_actor, paths=["a"])

    async def work():
        with pytest.raises(WorkspaceOwnershipError, match="descendant_lifecycle"):
            ownership.retire()
        with pytest.raises(WorkspaceOwnershipError, match="descendant_lifecycle"):
            await ownership.close()
        ownership.require_write(child, child_actor, ["a"])

    worker = asyncio.create_task(work())
    ownership.bind_worker(root, actor, child, worker)
    await worker
    ownership.resolve(root, actor, child, disposition="reviewed")
    ownership.require_write(root, actor, ["a"])
    await ownership.close()
