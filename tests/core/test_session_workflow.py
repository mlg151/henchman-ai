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
