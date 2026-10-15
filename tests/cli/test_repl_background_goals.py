"""Responsive classic REPL input and serialized autonomous goal turns."""

import asyncio
from io import StringIO
from pathlib import Path
from unittest.mock import Mock

import pytest
from rich.console import Console

from henchman.cli.repl import Repl, ReplConfig


@pytest.fixture
def repl(tmp_path: Path) -> Repl:
    return Repl(
        provider=Mock(), console=Console(file=StringIO()),
        config=ReplConfig(history_file=tmp_path / "history", auto_save=False),
    )


async def test_run_accepts_commands_and_queues_messages_during_agent_turn(repl: Repl) -> None:
    started = asyncio.Event()
    release = asyncio.Event()
    second_done = asyncio.Event()
    calls: list[str] = []
    inputs = asyncio.Queue[str]()
    active = 0

    async def agent(message: str) -> None:
        nonlocal active
        active += 1
        assert active == 1
        calls.append(message)
        if message == "first":
            started.set()
            await release.wait()
        else:
            second_done.set()
        active -= 1

    async def command(message: str, *_args: object) -> bool:
        assert message == "/status"
        assert calls == ["first"]
        release.set()
        return True

    repl._run_agent = agent
    repl._get_input = inputs.get
    repl.command_processor.handle_command = command
    runner = asyncio.create_task(repl.run())
    try:
        await inputs.put("first")
        await asyncio.wait_for(started.wait(), 1)
        await inputs.put("second")
        await inputs.put("/status")
        await asyncio.wait_for(second_done.wait(), 1)
        assert calls == ["first", "second"]
    finally:
        runner.cancel()
        with pytest.raises(asyncio.CancelledError):
            await runner


async def test_run_exit_cancels_and_joins_active_turn(repl: Repl) -> None:
    started = asyncio.Event()
    stopped = asyncio.Event()
    inputs = asyncio.Queue[str]()

    async def agent(_message: str) -> None:
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()

    async def command(_message: str, *_args: object) -> bool:
        return False

    repl._run_agent = agent
    repl._get_input = inputs.get
    repl.command_processor.handle_command = command
    runner = asyncio.create_task(repl.run())
    try:
        await inputs.put("work")
        await asyncio.wait_for(started.wait(), 1)
        await inputs.put("/quit")
        await asyncio.wait_for(asyncio.shield(runner), 1)
        assert stopped.is_set()
    finally:
        if not runner.done():
            runner.cancel()
            with pytest.raises(asyncio.CancelledError):
                await runner


async def test_question_suspends_chat_input_and_resumes_after_answer(repl: Repl) -> None:
    chat_started = asyncio.Event()
    chat_stopped = asyncio.Event()
    question_started = asyncio.Event()
    answer_ready = asyncio.Event()
    calls = 0

    async def chat() -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            chat_started.set()
            try:
                await asyncio.Event().wait()
            finally:
                chat_stopped.set()
        return "next message"

    async def question(_question: str) -> str:
        assert chat_stopped.is_set()
        question_started.set()
        await answer_ready.wait()
        return "answer"

    repl.input_handler.get_input = chat
    repl.input_handler.ask_question = question
    reader = asyncio.create_task(repl._get_input())
    asker = None
    try:
        await asyncio.wait_for(chat_started.wait(), 1)
        asker = asyncio.create_task(repl._ask_question("Which?"))
        await asyncio.wait_for(question_started.wait(), 1)
        assert calls == 1
        answer_ready.set()
        assert await asyncio.wait_for(asker, 1) == "answer"
        assert await asyncio.wait_for(reader, 1) == "next message"
    finally:
        for task in (reader, asker):
            if task is not None and not task.done():
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task


async def test_goal_continues_after_turn_and_prioritizes_user_steering(
    repl: Repl, tmp_path: Path,
) -> None:
    from henchman.core.goals import GoalService
    from henchman.core.session import SessionManager

    manager = SessionManager(data_dir=tmp_path / "sessions")
    repl.session_manager.session_manager = manager
    session = manager.create_session(project_hash="test")
    repl.set_session(session)
    service = GoalService()
    service.start(session, "finish the task")
    first_started = asyncio.Event()
    release = asyncio.Event()
    complete = asyncio.Event()
    calls: list[str] = []
    inputs = asyncio.Queue[str]()

    async def agent(message: str) -> None:
        calls.append(message)
        if len(calls) == 1:
            first_started.set()
            await release.wait()
        elif len(calls) == 3:
            goal = service.get(session)
            assert goal is not None
            service.complete(session, goal_id=goal.id, summary="Verified completion")
            complete.set()

    repl._run_agent = agent
    repl._get_input = inputs.get
    runner = asyncio.create_task(repl.run())
    try:
        await asyncio.wait_for(first_started.wait(), 1)
        await repl.process_input("steering")
        release.set()
        await asyncio.wait_for(complete.wait(), 1)
        await asyncio.sleep(0)
        assert len(calls) == 3
        assert calls[1] == "steering"
        assert "finish the task" in calls[0]
        assert "finish the task" in calls[2]
        assert repl._turn_worker is None or repl._turn_worker.done()
    finally:
        runner.cancel()
        with pytest.raises(asyncio.CancelledError):
            await runner


@pytest.mark.parametrize("key", [b"\x1b", b"\x03"])
async def test_interrupt_pauses_goal_and_cancels_turn_without_exiting(
    repl: Repl, tmp_path: Path, key: bytes,
) -> None:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput

    from henchman.core.goals import GoalService
    from henchman.core.session import SessionManager

    manager = SessionManager(data_dir=tmp_path / "sessions")
    repl.session_manager.session_manager = manager
    session = manager.create_session(project_hash="test")
    repl.set_session(session)
    service = GoalService()
    service.start(session, "long task")
    started = asyncio.Event()
    stopped = asyncio.Event()

    async def agent(_message: str) -> None:
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()

    repl._run_agent = agent
    with create_pipe_input() as pipe:
        assert repl.input_handler.prompt_session is not None
        repl.input_handler.prompt_session = PromptSession(
            input=pipe, output=DummyOutput(),
            key_bindings=repl.input_handler.prompt_session.key_bindings,
        )
        runner = asyncio.create_task(repl.run())
        try:
            await asyncio.wait_for(started.wait(), 1)
            pipe.send_bytes(key)
            await asyncio.wait_for(stopped.wait(), 2)
            assert repl.running
            assert service.get(session).status == "paused"
            pipe.send_text("/quit\n")
            await asyncio.wait_for(runner, 2)
        finally:
            if not runner.done():
                runner.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await runner


async def test_direct_agent_requests_wait_for_the_current_turn(repl: Repl) -> None:
    started = asyncio.Event()
    release = asyncio.Event()
    direct_done = asyncio.Event()
    inputs = asyncio.Queue[str]()

    async def agent(_message: str) -> None:
        started.set()
        await release.wait()

    async def direct_stream(stream, _agent, _content, detail) -> None:
        try:
            assert release.is_set(), "Direct agent turn overlapped the running turn"
            assert detail == "@tech_lead"
            direct_done.set()
        finally:
            await stream.aclose()

    repl._run_agent = agent
    repl._run_agent_with_monitor = direct_stream
    repl._get_input = inputs.get
    runner = asyncio.create_task(repl.run())
    try:
        await inputs.put("first")
        await asyncio.wait_for(started.wait(), 1)
        await asyncio.wait_for(repl._run_agent_direct("tech_lead", "second"), 1)
        assert not direct_done.is_set()
        release.set()
        await asyncio.wait_for(direct_done.wait(), 1)
    finally:
        runner.cancel()
        with pytest.raises(asyncio.CancelledError):
            await runner


async def test_interactive_confirmation_uses_async_question_input(repl: Repl) -> None:
    from henchman.tools.base import ConfirmationRequest

    repl._interactive_loop_active = True
    questions: list[str] = []

    async def answer(question: str) -> str:
        questions.append(question)
        return "yes"

    async def forbidden_thread_prompt(_request) -> bool:
        raise AssertionError("Interactive approval must remain cancellable")

    repl.input_handler.ask_question = answer
    repl.tool_executor.handle_confirmation = forbidden_thread_prompt
    request = ConfirmationRequest("shell", "execute", {"command": "echo test > output.txt"})
    assert await repl.tool_manager.handle_confirmation(request)
    assert len(questions) == 1
    assert "echo test > output.txt" in questions[0]


async def test_cancelled_question_pauses_goal(repl: Repl, tmp_path: Path) -> None:
    from henchman.core.goals import GoalService
    from henchman.core.session import SessionManager

    manager = SessionManager(data_dir=tmp_path / "sessions")
    repl.session_manager.session_manager = manager
    session = manager.create_session(project_hash="test")
    repl.set_session(session)
    GoalService().start(session, "finish")

    async def cancel(_question: str) -> str:
        raise asyncio.CancelledError

    repl.input_handler.ask_question = cancel
    with pytest.raises(asyncio.CancelledError):
        await repl._ask_question("Which?")
    assert GoalService().get(session).status == "paused"


async def test_question_preserves_chat_draft(repl: Repl) -> None:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput

    async def answer(_question: str) -> str:
        return "yes"

    repl.input_handler.ask_question = answer
    with create_pipe_input() as pipe:
        prompt = PromptSession(input=pipe, output=DummyOutput())
        repl.input_handler.prompt_session = prompt
        reader = asyncio.create_task(repl._get_input())
        try:
            pipe.send_text("draft")
            async with asyncio.timeout(2):
                while prompt.default_buffer.text != "draft":
                    await asyncio.sleep(0)
            assert await repl._ask_question("Which?") == "yes"
            async with asyncio.timeout(2):
                while not prompt.app.is_running:
                    await asyncio.sleep(0)
            pipe.send_text(" tail\n")
            assert await asyncio.wait_for(reader, 2) == "draft tail"
        finally:
            if not reader.done():
                reader.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await reader


async def test_error_event_pauses_goal_continuation(repl: Repl, tmp_path: Path) -> None:
    from henchman.core.events import AgentEvent, EventType
    from henchman.core.goals import GoalService
    from henchman.core.session import SessionManager

    manager = SessionManager(data_dir=tmp_path / "sessions")
    repl.session_manager.session_manager = manager
    session = manager.create_session(project_hash="test")
    repl.set_session(session)
    GoalService().start(session, "finish")
    repl._interactive_loop_active = True

    async def failing_stream():
        yield AgentEvent(EventType.ERROR, "Provider unavailable")

    await repl._run_agent_with_monitor(failing_stream(), repl.agent, [], None)
    assert GoalService().get(session).status == "paused"


async def test_history_commands_wait_without_blocking_input(repl: Repl) -> None:
    started = asyncio.Event()
    release = asyncio.Event()
    cleared = asyncio.Event()
    inputs = asyncio.Queue[str]()
    original_clear = repl.agent.clear_history

    async def agent(_message: str) -> None:
        started.set()
        await release.wait()

    def clear() -> None:
        assert release.is_set(), "History was mutated during the agent turn"
        original_clear()
        cleared.set()

    repl._run_agent = agent
    repl._get_input = inputs.get
    repl.agent.clear_history = clear
    runner = asyncio.create_task(repl.run())
    try:
        await inputs.put("first")
        await asyncio.wait_for(started.wait(), 1)
        assert await asyncio.wait_for(repl.process_input("/clear"), 1)
        assert not cleared.is_set()
        release.set()
        await asyncio.wait_for(cleared.wait(), 1)
    finally:
        runner.cancel()
        with pytest.raises(asyncio.CancelledError):
            await runner


async def test_background_output_redraws_prompt_and_preserves_draft(repl: Repl) -> None:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.application import create_app_session
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput

    class RecordingOutput(DummyOutput):
        def __init__(self) -> None:
            self.writes: list[str] = []
            self.raw_writes: list[str] = []

        def write(self, data: str) -> None:
            self.writes.append(data)

        def write_raw(self, data: str) -> None:
            self.writes.append(data)
            self.raw_writes.append(data)

    started = asyncio.Event()
    emit = asyncio.Event()
    received_draft = asyncio.Event()
    messages: list[str] = []
    terminal = RecordingOutput()

    async def agent(message: str) -> None:
        messages.append(message)
        if len(messages) == 1:
            started.set()
            await emit.wait()
            Console(force_terminal=True, color_system="standard", no_color=False).print(
                "[red]background result[/]",
            )
        else:
            received_draft.set()

    repl._run_agent = agent
    with create_pipe_input() as pipe, create_app_session(input=pipe, output=terminal):
        prompt = PromptSession(input=pipe, output=terminal)
        repl.input_handler.prompt_session = prompt
        runner = asyncio.create_task(repl.run())
        try:
            pipe.send_text("first\n")
            await asyncio.wait_for(started.wait(), 2)
            pipe.send_text("draft")
            async with asyncio.timeout(2):
                while prompt.default_buffer.text != "draft":
                    await asyncio.sleep(0)
            emit.set()
            async with asyncio.timeout(2):
                while "background result" not in "".join(terminal.writes):
                    await asyncio.sleep(0.01)
            assert "\x1b[31mbackground result" in "".join(terminal.raw_writes)
            pipe.send_text(" tail\n")
            await asyncio.wait_for(received_draft.wait(), 2)
            assert messages == ["first", "draft tail"]
            pipe.send_text("/quit\n")
            await asyncio.wait_for(runner, 2)
        finally:
            if not runner.done():
                runner.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await runner
