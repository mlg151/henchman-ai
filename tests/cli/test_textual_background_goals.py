"""Interactive input is retained while an agent turn is active."""

import asyncio
from unittest.mock import MagicMock

import pytest
from textual.widgets import TextArea

from henchman.cli.textual_app import HenchmanTextualApp
from henchman.cli.textual_config import TextualConfig
from henchman.config.schema import Settings


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    provider = MagicMock()
    provider.name = "test"
    return HenchmanTextualApp(
        provider=provider,
        config=TextualConfig(auto_save=False, history_file=tmp_path / "history"),
        settings=Settings(),
    )


async def test_input_during_active_turn_is_processed_in_order(app, monkeypatch):
    started, release = asyncio.Event(), asyncio.Event()
    seen = []
    active = 0

    async def route(text, _chat):
        nonlocal active
        active += 1
        assert active == 1
        seen.append(text)
        if text == "first":
            started.set()
            await release.wait()
        active -= 1

    monkeypatch.setattr(app, "_route_input", route)
    async with app.run_test(size=(100, 40)):
        worker = app.process_user_input("first")
        await asyncio.wait_for(started.wait(), 3)
        widget = app.query_one("#input", TextArea)
        widget.load_text("second")
        app.action_submit_message()
        widget.load_text("third")
        app.action_submit_message()
        assert widget.text == ""
        assert seen == ["first"]
        release.set()
        await asyncio.wait_for(worker.wait(), 3)
        assert seen == ["first", "second", "third"]


async def test_goal_continues_until_explicit_completion(app, monkeypatch):
    from henchman.core.goals import GoalService

    seen = []
    async with app.run_test(size=(100, 40)):
        session = app.core_context.session_manager.current
        goal = GoalService().start(session, "Finish the fixture")

        async def route(text, _chat):
            seen.append(text)
            if len(seen) == 2:
                GoalService().complete(session, goal_id=goal.id, summary="Fixture verified")

        monkeypatch.setattr(app, "_route_input", route)
        worker = app.process_user_input("Begin")
        await asyncio.wait_for(worker.wait(), 3)
        assert len(seen) == 2
        assert "Finish the fixture" in seen[1]
        assert GoalService().get(session).status == "complete"


async def test_pause_command_during_work_prevents_continuation(app, monkeypatch):
    from henchman.core.goals import GoalService

    started, release = asyncio.Event(), asyncio.Event()
    seen = []
    async with app.run_test(size=(100, 40)) as pilot:
        session = app.core_context.session_manager.current
        GoalService().start(session, "Keep working")

        async def run(text, _chat):
            seen.append(text)
            started.set()
            await release.wait()

        monkeypatch.setattr(app, "_run_orchestrator", run)
        worker = app.process_user_input("Begin")
        await asyncio.wait_for(started.wait(), 3)
        app.query_one("#input", TextArea).load_text("/goal pause")
        app.action_submit_message()
        await pilot.pause()
        assert GoalService().get(session).status == "paused"
        release.set()
        await asyncio.wait_for(worker.wait(), 3)
        assert seen == ["Begin"]


async def test_user_input_precedes_goal_continuation(app, monkeypatch):
    from henchman.core.goals import GoalService

    started, release = asyncio.Event(), asyncio.Event()
    seen = []
    async with app.run_test(size=(100, 40)):
        session = app.core_context.session_manager.current
        goal = GoalService().start(session, "Finish the goal")

        async def route(text, _chat):
            seen.append(text)
            if len(seen) == 1:
                started.set()
                await release.wait()
            if len(seen) == 3:
                GoalService().complete(session, goal_id=goal.id, summary="Verified")

        monkeypatch.setattr(app, "_route_input", route)
        worker = app.process_user_input("Begin")
        await asyncio.wait_for(started.wait(), 3)
        app.query_one("#input", TextArea).load_text("Use the new requirements")
        app.action_submit_message()
        release.set()
        await asyncio.wait_for(worker.wait(), 3)
        assert seen[:2] == ["Begin", "Use the new requirements"]
        assert "Finish the goal" in seen[2]


@pytest.mark.parametrize("failure", [RuntimeError, asyncio.CancelledError])
async def test_failed_or_cancelled_turn_pauses_goal(app, monkeypatch, failure):
    from henchman.core.goals import GoalService

    async with app.run_test(size=(100, 40)):
        session = app.core_context.session_manager.current
        GoalService().start(session, "Finish the goal")
        calls = []

        async def route(text, _chat):
            calls.append(text)
            raise failure("Stopped")

        monkeypatch.setattr(app, "_route_input", route)
        worker = app.process_user_input("Begin")
        await asyncio.wait_for(worker.wait(), 3)
        assert GoalService().get(session).status == "paused"
        assert calls == ["Begin"]


async def test_goal_command_runs_real_provider_tool_completion(app):
    """The slash command, continuation loop and completion tool work together."""
    from copy import deepcopy

    from henchman.core.goals import GoalService
    from henchman.providers.base import FinishReason, ModelProvider, StreamChunk, ToolCall

    class GoalProvider(ModelProvider):
        def __init__(self):
            self.requests = []

        @property
        def name(self):
            return "goal-fixture"

        async def chat_completion_stream(self, messages, tools=None, **_kwargs):
            self.requests.append(deepcopy(messages))
            assert any(tool.name == "goal_status" for tool in tools)
            if len(self.requests) == 1:
                yield StreamChunk(content="I will check the fixture.", finish_reason=FinishReason.STOP)
            elif len(self.requests) == 2:
                session = app.core_context.session_manager.current
                goal = GoalService().get(session)
                yield StreamChunk(
                    tool_calls=[ToolCall(id="goal-done", name="goal_status", arguments={
                        "action": "complete", "goal_id": goal.id,
                        "summary": "Fixture requirements checked",
                    })], finish_reason=FinishReason.TOOL_CALLS,
                )
            else:
                yield StreamChunk(content="Fixture complete.", finish_reason=FinishReason.STOP)

    provider = GoalProvider()
    app.provider = provider
    app.config.agent_role = "engineer"
    async with app.run_test(size=(100, 40)):
        worker = app.process_user_input("/goal Check the fixture")
        await asyncio.wait_for(worker.wait(), 5)
        goal = GoalService().get(app.core_context.session_manager.current)
        assert goal.status == "complete"
        assert len(provider.requests) == 3
        assert any(message.role == "tool" and '"complete"' in message.content
                   for message in provider.requests[-1])


async def test_queued_message_is_not_stranded_by_failed_turn(app, monkeypatch):
    started, release, followed_up = asyncio.Event(), asyncio.Event(), asyncio.Event()
    seen = []

    async def route(text, _chat):
        seen.append(text)
        if text == "first":
            started.set()
            await release.wait()
            raise RuntimeError("Provider disconnected")
        followed_up.set()

    monkeypatch.setattr(app, "_route_input", route)
    async with app.run_test(size=(100, 40)):
        worker = app.process_user_input("first")
        await asyncio.wait_for(started.wait(), 3)
        app.query_one("#input", TextArea).load_text("second")
        app.action_submit_message()
        release.set()
        await asyncio.wait_for(worker.wait(), 3)
        await asyncio.wait_for(followed_up.wait(), 1)
        assert seen == ["first", "second"]
