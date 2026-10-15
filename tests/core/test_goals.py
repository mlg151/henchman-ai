"""Session goal lifecycle and structured completion contracts."""

import pytest

from henchman.core.goals import GoalService
from henchman.core.session_data import Session, session_from_json


def make_session() -> Session:
    return Session(id="test", project_hash="project", started="now", last_updated="now")


def test_goal_survives_roundtrip_and_pause_resume() -> None:
    session = make_session()
    service = GoalService()
    goal = service.start(session, "  Fix the regression  ")
    restored = session_from_json(session.to_json())
    assert service.get(restored) == goal
    assert goal.objective == "Fix the regression"
    assert service.continuation_prompt(restored)
    service.pause(restored)
    assert service.continuation_prompt(restored) is None
    service.resume(restored)
    assert service.get(restored).status == "active"
    assert service.continuation_prompt(restored)


def test_stale_completion_cannot_complete_replacement_goal() -> None:
    service = GoalService()
    session = make_session()
    old = service.start(session, "First")
    new = service.start(session, "Second")
    with pytest.raises(ValueError, match="changed"):
        service.complete(session, goal_id=old.id, summary="Verified")
    assert service.get(session) == new
    service.complete(session, goal_id=new.id, summary="All relevant checks passed")
    assert service.continuation_prompt(session) is None
    assert service.get(session).completion_summary == "All relevant checks passed"


def test_empty_objective_and_empty_completion_are_rejected() -> None:
    service = GoalService()
    session = make_session()
    with pytest.raises(ValueError):
        service.start(session, "  ")
    goal = service.start(session, "Test")
    with pytest.raises(ValueError):
        service.complete(session, goal_id=goal.id, summary="  ")
    assert service.get(session).status == "active"


def test_paused_goal_cannot_be_completed_by_late_tool_call() -> None:
    service = GoalService()
    session = make_session()
    goal = service.start(session, "Test")
    service.pause(session)
    with pytest.raises(ValueError, match="active"):
        service.complete(session, goal_id=goal.id, summary="Done")
    assert service.get(session).status == "paused"
    service.clear(session)
    assert service.get(session) is None
    with pytest.raises(ValueError):
        service.resume(session)


def test_goal_prompt_preserves_objective_as_user_data() -> None:
    service = GoalService()
    session = make_session()
    goal = service.start(session, 'Fix "quotes"\nand tests')
    prompt = service.continuation_prompt(session)
    assert goal.id in prompt
    assert 'goal_status' in prompt
    assert 'Fix \\"quotes\\"\\nand tests' in prompt
