"""Frontend session selection binds workflow authority independently of autosave."""

import pytest

from henchman.cli.session_manager import ReplSessionManager
from henchman.config.schema import Settings
from henchman.core.goals import GoalService
from henchman.core.session import SessionManager
from henchman.core.session_data import session_from_json
from henchman.core.workflow_state import WorkflowError


def test_session_binding_preserves_recovered_work_without_automatic_dispatch(tmp_path):
    settings = Settings(operations={"persistence": "durable"})
    manager = ReplSessionManager(SessionManager(data_dir=tmp_path / "sessions"), settings=settings, auto_save=False)
    session = manager.create_session("project")
    manager.set_session(session)
    runtime = session.workflow_runtime
    item = runtime.submit("retained before dispatch")
    GoalService().start(session, "complete this goal")
    restored = session_from_json(session.to_json())
    manager.set_session(restored)
    assert restored.workflow_runtime.report().state.inputs[0].id == item.id
    assert restored.workflow_runtime.next_input() is None
    assert GoalService().continuation_prompt(restored) is None
    assert manager.session_manager.load(session.id).workflow == session.workflow


def test_active_dispatch_prevents_session_switch_before_history_mutation(tmp_path):
    manager = ReplSessionManager(SessionManager(data_dir=tmp_path / "sessions"), settings=Settings())
    original = manager.create_session("project")
    manager.set_session(original)
    original.workflow_runtime.submit("running")
    original.workflow_runtime.next_input()
    replacement = manager.create_session("project")
    with pytest.raises(WorkflowError, match="workflow_dispatch_active"):
        manager.set_session(replacement)
    assert manager.current is original
    assert original.workflow_runtime.has_active_dispatch()


def test_workflow_verification_uses_runtime_settings_and_current_redactor(tmp_path, monkeypatch):
    import henchman.advanced.plans as plans

    seen = []
    class Verification:
        def __init__(self, project_root, *, settings, redactor):
            seen.append((project_root, settings, redactor))

        def verification_status(self, plan_id):
            return {"spec_digest": "a" * 64, "run_id": "check-run", "current_checks_passed": True}

    monkeypatch.setattr(plans, "PlanExecutionService", Verification)
    settings = Settings()
    manager = ReplSessionManager(SessionManager(data_dir=tmp_path / "sessions"), settings=settings)
    session = manager.create_session("project")
    manager.set_session(session)
    session.workflow_runtime.start_goal("verified goal")
    goal = session.workflow_runtime.bind_plan("plan")
    assert goal.checks[0].observed_run_id == "check-run"
    assert seen[0][1] is settings and seen[0][2] is session.evidence_redactor
