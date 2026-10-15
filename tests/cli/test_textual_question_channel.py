"""Real Textual input and tool channel lifecycle regressions."""

import asyncio
from copy import deepcopy
from unittest.mock import MagicMock

import pytest
from textual.screen import ModalScreen
from textual.widgets import Input, Label

from henchman.cli.textual_app import HenchmanTextualApp
from henchman.cli.textual_config import TextualConfig
from henchman.config.schema import Settings
from henchman.providers.base import FinishReason, ModelProvider, StreamChunk, ToolCall
from henchman.tools.base import ConfirmationRequest


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


@pytest.mark.asyncio
async def test_registered_tool_accepts_exact_answer(app):
    async with app.run_test(size=(100, 40)) as pilot:
        tool = app.core_context.tool_registry.get("ask_user")
        task = asyncio.create_task(tool.execute(question="Use [red] café?"))
        await pilot.pause()
        label = app.screen.query_one("#tool-question", Label)
        assert str(label.content) == "Use [red] café?"
        app.screen.query_one(Input).value = "  café yes  "
        await pilot.press("enter")
        result = await asyncio.wait_for(task, 2)
        assert result.success
        assert result.content == "  café yes  "
        await pilot.pause()
        assert len(app.screen_stack) == 1


@pytest.mark.asyncio
async def test_escape_does_not_fabricate_answer(app):
    async with app.run_test(size=(100, 40)) as pilot:
        tool = app.core_context.tool_registry.get("ask_user")
        task = asyncio.create_task(tool.execute(question="Which option?"))
        await pilot.pause()
        await pilot.press("escape")
        result = await asyncio.wait_for(task, 2)
        assert not result.success
        assert "No user answer" in result.error
        assert len(app.screen_stack) == 1


@pytest.mark.asyncio
async def test_blank_answer_keeps_question_open(app):
    async with app.run_test(size=(100, 40)) as pilot:
        task = asyncio.create_task(app._textual_question("Choose"))
        await pilot.pause()
        app.screen.query_one(Input).value = "   "
        await pilot.press("enter")
        assert not task.done()
        await pilot.press("escape")
        assert await task is None


@pytest.mark.asyncio
async def test_tool_timeout_removes_screen(app):
    async with app.run_test(size=(100, 40)) as pilot:
        tool = app.core_context.tool_registry.get("ask_user")
        task = asyncio.create_task(tool.execute(question="Choose", timeout=1))
        await pilot.pause()
        result = await asyncio.wait_for(task, 3)
        assert not result.success
        assert "timed out" in result.error
        await pilot.pause()
        assert len(app.screen_stack) == 1


@pytest.mark.asyncio
async def test_cancellation_removes_screen_and_allows_next_question(app):
    async with app.run_test(size=(100, 40)) as pilot:
        task = asyncio.create_task(app._textual_question("First"))
        await pilot.pause()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        await pilot.pause()
        assert len(app.screen_stack) == 1
        next_task = asyncio.create_task(app._textual_question("Next"))
        await pilot.pause()
        await pilot.press("escape")
        assert await next_task is None


@pytest.mark.asyncio
async def test_questions_and_confirmations_are_serialized(app):
    async with app.run_test(size=(100, 40)) as pilot:
        first = asyncio.create_task(app._textual_question("First"))
        await pilot.pause()
        confirm = asyncio.create_task(app._textual_confirm(ConfirmationRequest(
            tool_name="shell", description="Run", params={}, risk_level="high",
        )))
        second = asyncio.create_task(app._textual_question("Second"))
        await pilot.pause()
        assert len(app.screen_stack) == 2
        await pilot.press("escape")
        assert await first is None
        await pilot.pause()
        assert app.screen.query_one("#confirm-title")
        await pilot.press("n")
        assert await confirm is False
        await pilot.pause()
        assert str(app.screen.query_one("#tool-question", Label).content) == "Second"
        await pilot.press("escape")
        assert await second is None


@pytest.mark.asyncio
async def test_cancel_under_overlay_preserves_overlay_and_expires_on_resume(app):
    async with app.run_test(size=(100, 40)) as pilot:
        task = asyncio.create_task(app._textual_question("Hidden"))
        await pilot.pause()
        overlay = ModalScreen()
        await app.push_screen(overlay)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert app.screen is overlay
        await overlay.dismiss()
        await pilot.pause()
        assert len(app.screen_stack) == 1


@pytest.mark.asyncio
async def test_shutdown_cancels_active_and_queued_questions(app):
    async with app.run_test(size=(100, 40)) as pilot:
        first = asyncio.create_task(app._textual_question("First"))
        second = asyncio.create_task(app._textual_question("Second"))
        await pilot.pause()
    for task in (first, second):
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 2)


@pytest.mark.asyncio
async def test_failed_screen_mount_does_not_block_next_question(app, monkeypatch):
    async with app.run_test(size=(100, 40)) as pilot:
        original_push = app.push_screen
        with monkeypatch.context() as patch:
            def fail_push(*_args, **_kwargs):
                raise RuntimeError("UI unavailable")
            patch.setattr(app, "push_screen", fail_push)
            with pytest.raises(RuntimeError, match="UI unavailable"):
                await app._textual_question("First")
        assert app.push_screen == original_push
        task = asyncio.create_task(app._textual_question("Next"))
        await pilot.pause()
        assert len(app.screen_stack) == 2
        await pilot.press("escape")
        assert await asyncio.wait_for(task, 2) is None


@pytest.mark.asyncio
async def test_clarification_flows_through_provider_and_saved_session(app, tmp_path):
    """An actual modal answer survives tool execution, continuation, and disk storage."""
    answer = "  Use café labels  "
    question = "Which naming convention should the Python package use?"
    call_id = "clarification-1"

    class ClarifyingProvider(ModelProvider):
        def __init__(self):
            self.calls = []

        @property
        def name(self):
            return "clarification-test"

        async def chat_completion_stream(self, messages, tools=None, **_kwargs):
            self.calls.append(deepcopy(messages))
            if len(self.calls) == 1:
                assert any(tool.name == "ask_user" for tool in tools)
                yield StreamChunk(
                    tool_calls=[ToolCall(
                        id=call_id, name="ask_user", arguments={"question": question},
                    )],
                    finish_reason=FinishReason.TOOL_CALLS,
                )
            else:
                yield StreamChunk(
                    content="I will use the naming convention you chose.",
                    finish_reason=FinishReason.STOP,
                )

    provider = ClarifyingProvider()
    app.provider = provider
    async with app.run_test(size=(100, 40)) as pilot:
        manager = app.core_context.session_manager
        manager.session_manager.data_dir = tmp_path / "sessions"
        manager.auto_save = True
        worker = app.process_user_input("Ask me how to name the Python package.")
        async with asyncio.timeout(5):
            while not app.screen.query("#question-answer"):
                await pilot.pause()
        assert str(app.screen.query_one("#tool-question", Label).content) == question
        app.screen.query_one(Input).value = answer
        await pilot.press("enter")
        await asyncio.wait_for(worker.wait(), 5)
        await pilot.pause()

        assert len(provider.calls) == 2
        continuation = provider.calls[1]
        actual_answers = [message for message in continuation if message.role == "tool"]
        assert len(actual_answers) == 1
        assert actual_answers[0].tool_call_id == call_id
        assert actual_answers[0].content == answer
        requests = [message for message in continuation if message.tool_calls]
        assert requests[-1].tool_calls[0].id == call_id
        assert requests[-1].tool_calls[0].name == "ask_user"

        # Read the auto-saved artifact back from disk, without saving in the test.
        saved = manager.session_manager.load(manager.current.id)
        saved_answers = [message for message in saved.messages if message.role == "tool"]
        assert len(saved_answers) == 1
        assert saved_answers[0].tool_call_id == call_id
        assert saved_answers[0].content == answer
        saved_requests = [message for message in saved.messages if message.tool_calls]
        assert saved_requests[-1].tool_calls[0]["id"] == call_id
        assert saved.messages[-1].content == "I will use the naming convention you chose."
        assert len(app.screen_stack) == 1
