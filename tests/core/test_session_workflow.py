"""User-owned workflow eligibility never survives reopening a session."""

from copy import deepcopy
from dataclasses import replace

import pytest

from henchman.config.schema import Settings
from henchman.core.goals import GoalService
from henchman.core.session_data import Session, session_from_json
from henchman.core.session_run_accounting import SessionRunAccounting
from henchman.core.session_workflow import SessionWorkflow
from henchman.core.workflow_state import WorkflowError


def controller(tmp_path, *, durable=True, session=None, save=None):
    session = session or Session("session", "project", "now", "now")
    settings = Settings()
    settings.operations.persistence = "durable" if durable else "process"
    runtime = SessionWorkflow(settings, lambda: session, save or (lambda _session: None), tmp_path / "ops.db")
    runtime.attach(session, restored=False)
    return runtime, session, settings


def test_accepted_queue_survives_restart_without_dispatch_eligibility(tmp_path):
    runtime, session, _ = controller(tmp_path)
    item = runtime.submit("first")
    saved = session_from_json(session.to_json())
    restarted, _, _ = controller(tmp_path, session=saved)
    assert restarted.next_input() is None
    assert restarted.report().state.inputs[0].id == item.id
    restarted.send(item.id, item.revision)
    dispatch = restarted.next_input()
    assert dispatch.text == "first"
    restarted.finish(dispatch, outcome="success")
    assert restarted.next_input() is None


def test_old_backup_and_policy_downgrade_cannot_hide_existing_workflow(tmp_path):
    runtime, session, _ = controller(tmp_path)
    backup = session_from_json(session.to_json())
    backup.workflow = None
    item = runtime.submit("do this once")
    runtime.next_input()
    restored, _, _ = controller(tmp_path, durable=False, session=backup)
    assert restored.report().state.inputs[0].state == "outcome_unknown"
    assert restored.report().blocking_input_ids == (item.id,)
    with pytest.raises(WorkflowError, match="input_not_queued"):
        restored.send(item.id, restored.report().state.inputs[0].revision)
    (tmp_path / "ops.db").unlink()
    with pytest.raises(WorkflowError):
        restored.report()


def test_cancel_preserves_pending_inputs_and_requires_explicit_send(tmp_path):
    runtime, _, _ = controller(tmp_path)
    first = runtime.submit("first")
    second = runtime.submit("second")
    runtime.next_input()
    runtime.interrupt()
    report = runtime.report()
    assert [item.state for item in report.state.inputs] == ["outcome_unknown", "queued"]
    assert runtime.next_input() is None
    runtime.abandon(first.id, report.state.inputs[0].revision, "Inspected; do not retry")
    assert runtime.next_input() is None
    runtime.send(second.id, second.revision)
    assert runtime.next_input().text == "second"


def test_process_mode_creates_no_store_and_session_restore_cannot_rearm_queue(tmp_path):
    runtime, session, _ = controller(tmp_path, durable=False)
    runtime.submit("held only in process")
    assert not (tmp_path / "ops.db").exists()
    restored, _, _ = controller(tmp_path, durable=False, session=session_from_json(session.to_json()))
    assert restored.next_input() is None
    assert not (tmp_path / "ops.db").exists()


def test_active_goal_restart_requires_user_resume_and_keeps_identity(tmp_path):
    runtime, session, _ = controller(tmp_path)
    goal = runtime.start_goal("Finish the work")
    assert runtime.goal_continuation_allowed()
    restored, _, _ = controller(tmp_path, session=session_from_json(session.to_json()))
    assert restored.goal().id == goal.id
    assert not restored.goal_continuation_allowed()
    restored.resume_goal()
    assert restored.goal_continuation_allowed()
    assert restored.goal().id == goal.id
    assert restored.goal().revision > goal.revision


def test_goal_policy_change_is_explicit_and_check_link_does_not_certify_task(tmp_path):
    runtime, session, settings = controller(tmp_path)
    runtime.start_goal("Verify configured assertions")
    settings.tools.network_access = "disabled"
    assert not runtime.goal_continuation_allowed()
    with pytest.raises(WorkflowError, match="goal_policy_changed"):
        runtime.resume_goal()
    runtime.resume_goal(accept_policy_change=True)
    status = {"spec_digest": "a" * 64, "run_id": "check-run", "current_checks_passed": True, "task_verified": False}
    runtime.check_status = lambda _identity: status
    runtime.bind_plan("plan")
    goal = runtime.goal()
    status["current_checks_passed"] = False
    with pytest.raises(WorkflowError, match="goal_checks_unverified"):
        runtime.complete_goal(goal.id, goal.revision, "claimed done")
    status["current_checks_passed"] = True
    completed = runtime.complete_goal(goal.id, goal.revision, "Configured checks pass; scope reviewed")
    assert completed.status == "complete"
    assert session.export_metadata["goal"]["checks"][0]["spec_digest"] == "a" * 64


def test_failed_acceptance_save_leaves_queued_intent_but_no_dispatch(tmp_path):
    runtime, session, _ = controller(tmp_path)
    runtime.save_session = lambda _session: (_ for _ in ()).throw(OSError("disk full"))
    with pytest.raises(WorkflowError, match="session_save_failed"):
        runtime.submit("not dispatched")
    assert runtime.report().state.inputs[0].state == "queued"
    assert runtime.next_input() is None
    assert session.workflow is not None


def test_budget_goal_save_failure_cannot_rollback_committed_workflow_goal(tmp_path):
    runtime, session, settings = controller(tmp_path)
    old = runtime.start_goal("old")
    accounting = SessionRunAccounting(settings, lambda: session, lambda _s: None, tmp_path / "ops.db")
    def fail():
        raise OSError("session save failed")
    with pytest.raises(Exception, match="session_save_failed"):
        accounting.apply_user_goal_transition(session, update=lambda: runtime.start_goal("new"), save=fail)
    assert runtime.goal().id != old.id
    assert GoalService().get(session).id == runtime.goal().id
    assert not runtime.goal_continuation_allowed()
    assert not accounting._goal_transitions


def test_session_switch_keeps_queued_input_in_original_session(tmp_path):
    original = Session("one", "project", "now", "now")
    selected = [original]
    settings = Settings()
    settings.operations.persistence = "durable"
    runtime = SessionWorkflow(settings, lambda: selected[0], lambda _s: None, tmp_path / "ops.db")
    runtime.attach(original, restored=False)
    item = runtime.submit("belongs to one")
    selected[0] = replace(original, id="two", workflow=None)
    runtime.attach(selected[0], restored=False)
    assert runtime.next_input() is None
    selected[0] = original
    runtime.attach(original, restored=True)
    assert runtime.next_input() is None
    assert runtime.report().state.inputs[0].id == item.id


def test_committed_goal_failure_disables_prior_runtime_continuation(tmp_path):
    runtime, session, _ = controller(tmp_path)
    runtime.start_goal("old")
    binding = runtime._bindings[(session.project_hash, session.id)]
    def fault(stage):
        if stage == "set_goal:after_commit":
            raise OSError("ambiguous commit acknowledgement")
    binding.journal.store._checkpoint = fault
    with pytest.raises(WorkflowError):
        runtime.start_goal("new committed objective")
    assert runtime.goal().objective == "new committed objective"
    assert not runtime.goal_continuation_allowed()


def test_claim_commit_failure_is_reported_unknown_without_replaying_next_entry(tmp_path):
    runtime, session, _ = controller(tmp_path)
    runtime.submit("first")
    runtime.submit("second")
    binding = runtime._bindings[(session.project_hash, session.id)]
    def fault(stage):
        if stage == "claim:after_commit":
            raise OSError("ambiguous start acknowledgement")
    binding.journal.store._checkpoint = fault
    with pytest.raises(WorkflowError):
        runtime.next_input()
    assert runtime.report().state.inputs[0].state == "outcome_unknown"
    assert runtime.next_input() is None


def test_live_secret_input_runs_only_from_original_runtime_memory(tmp_path):
    runtime, session, _ = controller(tmp_path)
    session.evidence_redactor.register_secret("private-live-input-canary")
    item = runtime.submit("inspect private-live-input-canary")
    assert item.text is None
    assert "private-live-input-canary" not in (tmp_path / "ops.db").read_bytes().decode("latin1")
    dispatch = runtime.next_input()
    assert dispatch.text == "inspect private-live-input-canary"
    runtime.finish(dispatch, outcome="success")


def test_goal_evidence_is_redacted_and_cannot_resume_from_projected_objective(tmp_path):
    runtime, session, _ = controller(tmp_path)
    session.evidence_redactor.register_secret("private-goal-canary")
    goal = runtime.start_goal("review private-goal-canary")
    assert runtime.goal().objective == goal.objective
    assert "private-goal-canary" not in (tmp_path / "ops.db").read_bytes().decode("latin1")
    restored, _, _ = controller(tmp_path, session=session_from_json(session.to_json()))
    with pytest.raises(WorkflowError, match="goal_payload_unavailable"):
        restored.resume_goal()


@pytest.mark.parametrize("durable", [False, True])
def test_forked_controller_cannot_reuse_goal_or_queue_permissions(tmp_path, monkeypatch, durable):
    import os

    runtime, _, _ = controller(tmp_path, durable=durable)
    goal = runtime.start_goal("parent goal")
    runtime.submit("parent queued input")
    original = os.getpid()
    monkeypatch.setattr(os, "getpid", lambda: original + 1)
    for action in (runtime.goal_continuation_allowed, runtime.next_input,
                   lambda: runtime.complete_goal(goal.id, goal.revision, "child claims done")):
        with pytest.raises(WorkflowError, match="process_authority_changed"):
            action()


def test_concurrent_goal_replacement_cannot_be_overwritten_by_stale_check_binding(tmp_path):
    runtime, session, _ = controller(tmp_path)
    runtime.start_goal("first")
    other, _, _ = controller(tmp_path, session=session_from_json(session.to_json()))
    def status(_plan_id):
        other.start_goal("concurrent replacement")
        return {"spec_digest": "b" * 64, "run_id": "run", "current_checks_passed": True}
    runtime.check_status = status
    with pytest.raises(WorkflowError, match="revision_conflict"):
        runtime.bind_plan("plan")
    assert runtime.goal().objective == "concurrent replacement"
    assert not runtime.goal_continuation_allowed()


@pytest.mark.parametrize("durable", [False, True])
def test_copying_session_preserves_evidence_but_never_runtime_dispatch_permission(tmp_path, durable):
    runtime, session, _ = controller(tmp_path, durable=durable)
    runtime.submit("original session only")
    copied = deepcopy(session)
    assert copied.workflow == session.workflow
    assert copied.workflow_runtime is None
    assert session.workflow_runtime is runtime
    assert runtime.next_input().text == "original session only"


def test_unattached_report_projects_rotated_credentials_without_binding_or_writing(tmp_path):
    runtime, session, settings = controller(tmp_path)
    runtime.submit("inspect newly-known-unattached-canary")
    runtime.start_goal("review newly-known-unattached-canary")
    restored = session_from_json(session.to_json())
    restored.evidence_redactor.register_secret("newly-known-unattached-canary")
    def forbid_save(_session):
        pytest.fail("Read-only inspection saved session evidence")
    inspector = SessionWorkflow(settings, lambda: restored, forbid_save, tmp_path / "ops.db")
    before = (tmp_path / "ops.db").read_bytes()
    report = inspector.report()
    assert "newly-known-unattached-canary" not in report.state.model_dump_json()
    assert report.state.inputs[0].text is None
    assert report.state.goal.availability == "redacted"
    assert report.goal_requires_resume
    assert not inspector._bindings
    assert restored.workflow_runtime is None
    assert (tmp_path / "ops.db").read_bytes() == before


def test_edit_drop_and_move_use_current_revisions_and_never_rearm_restored_input(tmp_path):
    runtime, session, _ = controller(tmp_path)
    first, second = runtime.submit("first"), runtime.submit("second")
    restored, _, _ = controller(tmp_path, session=session_from_json(session.to_json()))
    moved = restored.move(second.id, second.revision, 0)
    assert [item.id for item in sorted(restored.report().state.inputs, key=lambda item: item.order)] == [second.id, first.id]
    edited = restored.edit(moved.id, moved.revision, "edited second")
    assert restored.next_input() is None
    with pytest.raises(WorkflowError, match="revision_conflict"):
        restored.drop(edited.id, moved.revision)
    dropped = restored.drop(edited.id, edited.revision)
    assert dropped.state == "cancelled"
    assert restored.next_input() is None


@pytest.mark.parametrize("durable", [False, True])
def test_move_to_current_position_holds_input_until_explicit_send(tmp_path, durable):
    runtime, _, _ = controller(tmp_path, durable=durable)
    first = runtime.submit("first")
    second = runtime.submit("second")
    moved = runtime.move(first.id, first.revision, 0)
    dispatch = runtime.next_input()
    assert dispatch.permit.input_id == second.id
    runtime.finish(dispatch, outcome="success")
    assert runtime.next_input() is None
    runtime.send(moved.id, moved.revision)
    assert runtime.next_input().text == "first"


def test_edit_disarms_only_changed_input_and_cannot_modify_started_work(tmp_path):
    runtime, _, _ = controller(tmp_path)
    first, second = runtime.submit("first"), runtime.submit("second")
    edited = runtime.edit(first.id, first.revision, "edited first")
    dispatch = runtime.next_input()
    assert dispatch.text == "second"
    current = next(item for item in runtime.report().state.inputs if item.id == second.id)
    for action in (lambda: runtime.edit(current.id, current.revision, "different"),
                   lambda: runtime.move(current.id, current.revision, 0),
                   lambda: runtime.drop(current.id, current.revision)):
        with pytest.raises(WorkflowError, match="input_not_queued"):
            action()
    runtime.finish(dispatch, outcome="success")
    assert runtime.next_input() is None
    runtime.send(edited.id, edited.revision)
    assert runtime.next_input().text == "edited first"


def test_correlation_is_deduplicated_and_late_evidence_never_rearms_input(tmp_path):
    runtime, session, _ = controller(tmp_path)
    runtime.submit("parent request")
    dispatch = runtime.next_input()
    runtime.correlate(dispatch, session, budget_run_id="budget", operation_run_id="run")
    runtime.finish(dispatch, outcome="success")
    runtime.correlate(dispatch, session, operation_run_id="run", operation_id="late-child-operation")
    runtime.correlate(dispatch, session, operation_id="late-child-operation")
    item = runtime.report().state.inputs[0]
    assert item.budget_run_ids == ("budget",)
    assert item.operation_run_ids == ("run",)
    assert item.operation_ids == ("late-child-operation",)
    assert item.state == "completed" and item.outcome == "success"
    assert runtime.next_input() is None
    reopened, _, _ = controller(tmp_path, session=session_from_json(session.to_json()))
    assert reopened.report().state.inputs[0] == item
    assert reopened.next_input() is None


def test_correlation_rejects_wrong_session_claim_and_persistence_failure(tmp_path):
    runtime, session, _ = controller(tmp_path)
    runtime.submit("one request")
    dispatch = runtime.next_input()
    other = Session("other", "project", "now", "now")
    with pytest.raises(WorkflowError, match="session_identity_mismatch"):
        runtime.correlate(dispatch, other, operation_id="effect")
    forged = replace(dispatch, permit=dispatch.permit.model_copy(update={"claim_id": "wrong"}))
    with pytest.raises(WorkflowError, match="input_owner_changed"):
        runtime.correlate(forged, session, operation_id="effect")
    def failed_save(_session):
        raise OSError("disk full")
    runtime.save_session = failed_save
    with pytest.raises(WorkflowError, match="session_save_failed"):
        runtime.correlate(dispatch, session, operation_id="effect")
    assert runtime.has_active_dispatch()
    assert runtime.report().failure_reason == "session_save_failed"


def test_hold_pending_keeps_actual_worker_owned_until_interrupt_settles(tmp_path):
    runtime, _, _ = controller(tmp_path)
    runtime.submit("running")
    runtime.submit("waiting")
    runtime.next_input()
    runtime.hold_pending()
    assert runtime.has_active_dispatch()
    assert runtime.report().state.inputs[0].state == "started"
    runtime.interrupt()
    assert not runtime.has_active_dispatch()
    assert runtime.next_input() is None


def test_generated_goal_input_cannot_be_sent_after_restart_or_goal_revision_change(tmp_path):
    runtime, session, _ = controller(tmp_path)
    runtime.start_goal("objective")
    pending = runtime.submit_goal()
    runtime.pause_goal()
    runtime.resume_goal()
    assert runtime.next_input() is None
    with pytest.raises(WorkflowError, match="goal_input_requires_resume"):
        runtime.send(pending.id, pending.revision)
    restored, _, _ = controller(tmp_path, session=session_from_json(session.to_json()))
    assert restored.submit_goal() is None
    restored.resume_goal()
    current = restored.submit_goal()
    assert restored.next_input().permit.input_id == current.id


def test_direct_role_credential_projection_prevents_restored_replay(tmp_path):
    runtime, session, _ = controller(tmp_path)
    session.evidence_redactor.register_secret("role-canary")
    item = runtime.submit("inspect", kind="direct", role="role-canary")
    assert b"role-canary" not in (tmp_path / "ops.db").read_bytes()
    assert runtime.next_input().role == "role-canary"
    runtime.interrupt()
    runtime.abandon(item.id, runtime.report().state.inputs[0].revision, "effect inspected")
    pending = runtime.submit("inspect next", kind="direct", role="role-canary")
    restored, _, _ = controller(tmp_path, session=session_from_json(session.to_json()))
    with pytest.raises(WorkflowError, match="input_payload_unavailable"):
        restored.send(pending.id, pending.revision)
    with pytest.raises(WorkflowError, match="input_role_unavailable"):
        restored.edit(pending.id, pending.revision, "new text cannot restore a missing role")


def test_failed_interrupt_persistence_releases_joined_worker_but_keeps_recovery_barrier(tmp_path, monkeypatch):
    runtime, _, _ = controller(tmp_path)
    item = runtime.submit("started")
    runtime.next_input()
    journal = next(iter(runtime._bindings.values())).journal
    original = journal.cancel
    def failed_cancel(*_args):
        raise WorkflowError("store_unavailable")
    monkeypatch.setattr(journal, "cancel", failed_cancel)
    with pytest.raises(WorkflowError, match="store_unavailable"):
        runtime.interrupt()  # caller has already joined its actual worker
    assert not runtime.has_active_dispatch()
    report = runtime.report()
    assert report.blocking_input_ids == (item.id,)
    assert report.state.inputs[0].state == "outcome_unknown"
    monkeypatch.setattr(journal, "cancel", original)
    runtime.abandon(item.id, report.state.inputs[0].revision, "Checked external state")
    assert not runtime.report().blocking_input_ids
    assert runtime.next_input() is None


def test_missing_store_during_joined_interrupt_does_not_claim_worker_is_still_live(tmp_path):
    runtime, _, _ = controller(tmp_path)
    runtime.submit("started")
    runtime.next_input()
    (tmp_path / "ops.db").unlink()
    with pytest.raises(WorkflowError):
        runtime.interrupt()
    assert not runtime.has_active_dispatch()
    with pytest.raises(WorkflowError):
        runtime.next_input()


def test_losing_goal_check_binding_cannot_shadow_committed_checks_on_resume(tmp_path):
    runtime, session, _ = controller(tmp_path)
    runtime.start_goal("same objective")
    other, _, _ = controller(tmp_path, session=session_from_json(session.to_json()))
    status = {"spec_digest": "b" * 64, "run_id": "required-run", "current_checks_passed": False}
    other.check_status = lambda _identity: status

    def race(_identity):
        other.bind_plan("required-plan")
        return {"spec_digest": "a" * 64, "run_id": "losing-run", "current_checks_passed": True}

    runtime.check_status = race
    with pytest.raises(WorkflowError, match="revision_conflict"):
        runtime.bind_plan("losing-plan")
    committed = runtime.report().state.goal
    assert committed is not None
    assert runtime.goal() == committed
    assert [reference.plan_id for reference in committed.checks] == ["required-plan"]

    runtime.check_status = lambda _identity: status
    resumed = runtime.resume_goal()
    assert resumed.checks == committed.checks
    with pytest.raises(WorkflowError, match="goal_checks_unverified"):
        runtime.complete_goal(resumed.id, resumed.revision, "must not skip the committed check")


@pytest.mark.parametrize("durable", [False, True])
@pytest.mark.parametrize("known_before_restore", [False, True])
def test_restored_direct_role_requires_original_live_authority(tmp_path, durable, known_before_restore):
    runtime, session, _ = controller(tmp_path, durable=durable)
    if known_before_restore:
        session.evidence_redactor.register_secret("restored-role-canary")
    item = runtime.submit("inspect", kind="direct", role="restored-role-canary")
    runtime.attach(session, restored=True)
    if not known_before_restore:
        session.evidence_redactor.register_secret("restored-role-canary")
    with pytest.raises(WorkflowError, match="input_payload_unavailable"):
        runtime.send(item.id, item.revision)
    assert runtime.next_input() is None


@pytest.mark.parametrize("durable", [False, True])
@pytest.mark.parametrize("known_before_restore", [False, True])
def test_restored_goal_requires_original_live_objective(tmp_path, durable, known_before_restore):
    runtime, session, _ = controller(tmp_path, durable=durable)
    if known_before_restore:
        session.evidence_redactor.register_secret("restored-objective-canary")
    runtime.start_goal("inspect restored-objective-canary")
    runtime.attach(session, restored=True)
    if not known_before_restore:
        session.evidence_redactor.register_secret("restored-objective-canary")
    with pytest.raises(WorkflowError, match="goal_payload_unavailable"):
        runtime.resume_goal()
    assert not runtime.goal_continuation_allowed()


@pytest.mark.parametrize("durable", [False, True])
def test_original_live_goal_and_role_remain_executable_without_restore(tmp_path, durable):
    runtime, session, _ = controller(tmp_path, durable=durable)
    session.evidence_redactor.register_secret("original-live-canary")
    runtime.start_goal("inspect original-live-canary")
    assert runtime.goal_continuation_allowed()
    assert runtime.goal().objective == "inspect original-live-canary"
    runtime.submit("inspect", kind="direct", role="original-live-canary")
    assert runtime.next_input().role == "original-live-canary"


@pytest.mark.parametrize("transition", ["replace", "resume"])
def test_remote_goal_transition_cannot_inherit_local_continuation_permission(tmp_path, transition):
    runtime, session, _ = controller(tmp_path)
    runtime.start_goal("original local goal")
    other, _, _ = controller(tmp_path, session=session_from_json(session.to_json()))
    if transition == "replace":
        changed = other.start_goal("different goal authorized in another runtime")
    else:
        other.pause_goal()
        changed = other.resume_goal()
    assert runtime.goal().id == changed.id
    assert runtime.report().goal_requires_resume
    assert not runtime.goal_continuation_allowed()
    assert runtime.submit_goal() is None

    runtime.check_status = lambda _identity: {"spec_digest": "a" * 64, "run_id": "checks", "current_checks_passed": True}
    runtime.bind_plan("extra-plan")
    assert not runtime.goal_continuation_allowed()
    runtime.unbind_plan("extra-plan")
    assert not runtime.goal_continuation_allowed()
    runtime.resume_goal()
    assert runtime.goal_continuation_allowed()


@pytest.mark.parametrize("durable", [False, True])
def test_restored_direct_role_rotation_is_rechecked_immediately_before_claim(tmp_path, durable):
    runtime, session, _ = controller(tmp_path, durable=durable)
    item = runtime.submit("inspect", kind="direct", role="pending-role-canary")
    runtime.attach(session, restored=True)
    runtime.send(item.id, item.revision)
    session.evidence_redactor.register_secret("pending-role-canary")
    with pytest.raises(WorkflowError, match="input_payload_unavailable"):
        runtime.next_input()
    assert not runtime.has_active_dispatch()
    assert runtime.report().state.inputs[0].state == "queued"
