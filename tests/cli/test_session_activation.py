"""Failed activation cannot split selected session and agent authority."""

import asyncio
from copy import deepcopy

import pytest

from henchman.cli.session_manager import ReplSessionManager
from henchman.config.schema import Settings
from henchman.core.agent import Agent
from henchman.core.session import SessionManager, SessionMessage
from henchman.core.workflow_state import WorkflowError
from henchman.tools.registry import ToolRegistry
from tests.agents.test_agent_budget_scope import AccountingProvider


@pytest.fixture
def activation(tmp_path):
    core = SessionManager(tmp_path / "sessions")
    manager = ReplSessionManager(core)
    actor = Agent(AccountingProvider(), system_prompt="system")
    previous = core.create_session("project", "previous")
    previous.messages = [SessionMessage("user", "earlier")]
    manager.set_session(previous, history_agent=actor)
    candidate = core.create_session("project", "candidate")
    candidate.messages = [SessionMessage("user", "replacement")]
    return manager, actor, previous, candidate


@pytest.mark.parametrize("boundary", ["grants", "core", "history", "malformed_history"])
def test_activation_failure_preserves_selected_session_and_actor(activation, monkeypatch, boundary):
    manager, actor, previous, candidate = activation
    before = deepcopy(actor.messages)
    actor._stall.nudge_count = 2
    actor._delegation_tool_errors.append("prior failure")
    failure = OSError("fixture activation failure")

    def fail(*_args, **_kwargs):
        raise failure

    if boundary == "grants":
        registry = ToolRegistry()
        manager.bind_tool_registry(registry)
        monkeypatch.setattr(registry, "clear_grants", fail)
    elif boundary == "core":
        original = manager.session_manager.set_current

        def after_core(session):
            original(session)
            raise failure

        monkeypatch.setattr(manager.session_manager, "set_current", after_core)
    elif boundary == "history":
        original_clear = actor.clear_history

        def after_clear():
            original_clear()
            raise failure

        monkeypatch.setattr(actor, "clear_history", after_clear)
    else:
        candidate.messages.append(SessionMessage("assistant", tool_calls=["invalid"]))

    with pytest.raises((OSError, AttributeError)) as caught:
        manager.set_session(candidate, history_agent=actor)
    if boundary != "malformed_history":
        assert caught.value is failure
    assert manager.current is previous
    assert manager.session_manager.current is previous
    assert actor.messages == before
    assert actor._stall.nudge_count == 2
    assert actor._delegation_tool_errors == ["prior failure"]
    assert manager.workflow_runtime.current() is previous


def test_successful_activation_detaches_history_and_resets_turn_state(activation):
    manager, actor, previous, candidate = activation
    actor._stall.nudge_count = 2
    actor._delegation_tool_errors.append("prior failure")
    manager.set_session(candidate, history_agent=actor)
    assert manager.current is manager.session_manager.current is candidate
    assert actor.messages[-1].content == "replacement"
    assert actor.messages[0].content == "system"
    assert actor._stall.nudge_count == 0
    assert actor._delegation_tool_errors == []
    candidate.messages[-1].content = "later edit"
    assert actor.messages[-1].content == "replacement"
    assert previous.messages[0].content == "earlier"


@pytest.mark.parametrize("persistence", ["process", "durable"])
def test_invalid_legacy_goal_cannot_be_bypassed_by_retry(tmp_path, persistence):
    core = SessionManager(tmp_path / "sessions")
    settings = Settings(operations={"persistence": persistence})
    manager = ReplSessionManager(core, settings=settings)
    previous = core.create_session("project", "previous")
    manager.set_session(previous)
    candidate = core.create_session("project", "candidate")
    candidate.export_metadata["goal"] = "invalid legacy goal"
    for _ in range(2):
        with pytest.raises(WorkflowError, match="invalid_legacy_goal"):
            manager.set_session(candidate)
        assert manager.current is core.current is previous
        assert candidate.export_metadata["goal"] == "invalid legacy goal"
        assert candidate.workflow is None


@pytest.mark.parametrize("same_session", [False, True])
def test_interrupted_history_restore_preserves_primary_and_holds_dispatch(activation, monkeypatch, same_session):
    manager, actor, previous, candidate = activation
    if same_session:
        candidate = previous
    messages, turn, provider = actor.messages, actor.turn, actor.provider
    failure = asyncio.CancelledError("original activation cancellation")
    clear = actor.clear_history

    def interrupt():
        clear()
        raise failure

    monkeypatch.setattr(actor, "clear_history", interrupt)
    with pytest.raises(asyncio.CancelledError) as caught:
        manager.set_session(candidate, history_agent=actor)
    assert caught.value is failure
    assert manager.current is manager.session_manager.current is previous
    assert actor.messages is messages and actor.turn is turn
    assert actor.provider is provider
    assert not manager.workflow_runtime.has_ready_input()


def test_invalid_instruction_provenance_fails_before_activation(activation, tmp_path):
    from henchman.config.context import ContextLoader

    manager, actor, previous, candidate = activation
    manager.instruction_snapshot = ContextLoader(start_dir=tmp_path).load_snapshot()
    candidate.export_metadata["instruction_sources"] = {"digest": "invalid prior provenance"}
    metadata = deepcopy(candidate.export_metadata)
    messages = actor.messages
    with pytest.raises(ValueError):
        manager.set_session(candidate, history_agent=actor)
    assert manager.current is manager.session_manager.current is previous
    assert actor.messages is messages
    assert candidate.export_metadata == metadata
