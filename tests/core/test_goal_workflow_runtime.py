"""Public goal services retain durable identity and recovery disposition."""

import pytest

from henchman.core.goals import GoalService
from henchman.core.session_data import session_from_json
from henchman.core.workflow_state import WorkflowError
from tests.core.test_session_workflow import controller


def test_goal_service_uses_authority_and_never_autoresumes_restored_session(tmp_path):
    runtime, session, _ = controller(tmp_path)
    service = GoalService()
    goal = service.start(session, "finish current work")
    assert runtime.goal().id == goal.id
    assert service.continuation_prompt(session)
    restored = session_from_json(session.to_json())
    assert service.continuation_prompt(restored) is None
    restarted, _, _ = controller(tmp_path, session=restored)
    assert service.get(restored).id == goal.id
    assert service.continuation_prompt(restored) is None
    resumed = service.resume(restored)
    assert resumed.id == goal.id and resumed.revision > goal.revision
    assert service.continuation_prompt(restored)
    assert restarted.goal_continuation_allowed()


def test_delayed_completion_cannot_complete_a_resumed_goal(tmp_path):
    runtime, session, _ = controller(tmp_path)
    service = GoalService()
    original = service.start(session, "do work")
    service.pause(session)
    current = service.resume(session)
    with pytest.raises(WorkflowError, match="goal_revision_conflict"):
        service.complete(session, goal_id=original.id, goal_revision=original.revision, summary="stale completion")
    assert runtime.goal().status == "active"
    completed = service.complete(session, goal_id=current.id, goal_revision=current.revision, summary="current completion")
    assert completed.status == "complete"


def test_goal_clear_is_authoritative_and_does_not_send_pending_input(tmp_path):
    runtime, session, _ = controller(tmp_path)
    GoalService().start(session, "old objective")
    item = runtime.submit("next task")
    runtime.interrupt()
    GoalService().clear(session)
    assert runtime.goal() is None
    assert GoalService().get(session) is None
    assert runtime.report().state.inputs[0].id == item.id
    assert runtime.next_input() is None


async def test_model_completion_requires_current_revision_and_records_model_source(tmp_path):
    from types import SimpleNamespace

    from henchman.tools.builtins.goal_status import GoalStatusTool

    runtime, session, _ = controller(tmp_path)
    goal = GoalService().start(session, "verified task")
    tool = GoalStatusTool()
    tool.bind_runtime(session_manager=SimpleNamespace(current=session), project_root=tmp_path)
    assert "goal_revision" in tool.parameters["properties"]
    missing = await tool.execute(action="complete", goal_id=goal.id, summary="verified")
    assert not missing.success and runtime.goal().status == "active"
    success = await tool.execute(action="complete", goal_id=goal.id, goal_revision=goal.revision, summary="verified")
    assert success.success
    assert runtime.goal().completion_source == "model"


@pytest.mark.parametrize("action", ["start", "pause", "resume", "complete", "acknowledge", "clear"])
def test_unattached_durable_goal_is_display_only_until_runtime_is_bound(tmp_path, action):
    runtime, session, _ = controller(tmp_path)
    runtime.start_goal("requires verified work")
    runtime.check_status = lambda _identity: {"spec_digest": "b" * 64, "run_id": "failed-check", "current_checks_passed": False}
    goal = runtime.bind_plan("required-plan")
    restored = session_from_json(session.to_json())
    assert restored.workflow is not None and restored.workflow_runtime is None
    service = GoalService()
    assert service.get(restored).objective == goal.objective
    assert service.continuation_prompt(restored) is None
    before = restored.to_json()
    kwargs = ({"objective": "replacement"} if action == "start" else
              {"goal_id": goal.id, "goal_revision": goal.revision, "summary": "unchecked completion"}
              if action == "complete" else {})
    with pytest.raises(WorkflowError, match="workflow_runtime_required"):
        getattr(service, action)(restored, **kwargs)
    assert restored.to_json() == before
    assert runtime.goal().status == "active"
    assert runtime.goal().checks == goal.checks
