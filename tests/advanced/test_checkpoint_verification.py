"""Restores supersede verification observations, including concurrent checks."""

import asyncio
import os

import pytest

from henchman.advanced.checkpoints import CheckpointService
from henchman.advanced.plans import PlanExecutionService

pytestmark = pytest.mark.skipif(os.name != "posix", reason="POSIX checkpoint backend")


async def setup(tmp_path):
    path = tmp_path / "file.txt"
    path.write_text("before")
    checkpoints = CheckpointService(tmp_path)
    capture = checkpoints.begin(["file.txt"], actor="engineer")
    path.write_text("after")
    checkpoints.complete(capture.checkpoint_id)
    checks = PlanExecutionService(tmp_path)
    plan = checks.create_plan(steps=["Edit file"], checks=[{"kind": "file_contains", "path": "file.txt", "text": "after"}])
    assert (await checks.verify_plan(plan.plan_id))["checks_passed"]
    return checkpoints, capture.checkpoint_id, checks, plan.plan_id


async def test_rejected_content_invalidates_checks_and_preserves_prior_observations(tmp_path):
    checkpoints, identity, checks, plan_id = await setup(tmp_path)
    decision = checkpoints.preview(identity, decision="reject")
    checkpoints.apply(decision.plan_id)
    report = checks.get_plan(plan_id).last_verification
    assert report["status"] == "stale" and report["checks_passed"] is False
    assert report["results"][0]["passed"] is True
    assert report["invalidation_reason"] == "checkpoint_restore"
    assert (await checks.verify_plan(plan_id))["checks_passed"] is False


async def test_accept_without_content_change_keeps_historical_observation(tmp_path):
    checkpoints, identity, checks, plan_id = await setup(tmp_path)
    before = checks.get_plan(plan_id).last_verification
    decision = checkpoints.preview(identity, decision="accept")
    assert checkpoints.apply(decision.plan_id).changed_paths == ()
    assert checks.get_plan(plan_id).last_verification == before


async def test_restore_supersedes_an_inflight_successful_check(tmp_path, monkeypatch):
    from henchman.advanced import plans

    checkpoints, identity, checks, plan_id = await setup(tmp_path)
    started, release = asyncio.Event(), asyncio.Event()

    async def observe(*_args):
        started.set()
        await release.wait()
        return {"checks_passed": True, "results": [{"passed": True}]}

    monkeypatch.setattr(plans, "run_checks", observe)
    checking = asyncio.create_task(checks.verify_plan(plan_id))
    await started.wait()
    decision = checkpoints.preview(identity, decision="reject")
    checkpoints.apply(decision.plan_id)
    release.set()
    with pytest.raises(ValueError, match="superseded"):
        await checking
    assert checks.get_plan(plan_id).last_verification["checks_passed"] is False


async def test_interrupted_restore_blocks_reverification_until_recovered(tmp_path):
    checkpoints, identity, checks, plan_id = await setup(tmp_path)
    decision = checkpoints.preview(identity, decision="reject")

    def crash(stage):
        if stage == "published":
            raise RuntimeError("crash")

    checkpoints._fault = crash
    with pytest.raises(RuntimeError, match="crash"):
        checkpoints.apply(decision.plan_id)
    with pytest.raises(ValueError, match="restore"):
        await checks.verify_plan(plan_id)
    assert checks.get_plan(plan_id).last_verification["checks_passed"] is False
    checkpoints._fault = lambda _stage: None
    checkpoints.recover(decision.plan_id)
    assert not (await checks.verify_plan(plan_id))["checks_passed"]


async def test_corrupt_verification_index_blocks_restore_before_displacement(tmp_path):
    checkpoints, identity, _, _ = await setup(tmp_path)
    decision = checkpoints.preview(identity, decision="reject")
    index = tmp_path / ".henchman/plans/verification.json"
    index.write_text("corrupt retained evidence")
    with pytest.raises(ValueError):
        checkpoints.apply(decision.plan_id)
    assert (tmp_path / "file.txt").read_text() == "after"
    assert index.read_text() == "corrupt retained evidence"
