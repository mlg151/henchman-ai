"""Real terminal input and runtime binding for agent clarification questions."""

import asyncio
from unittest.mock import Mock

import pytest
from prompt_toolkit import PromptSession
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput
from rich.console import Console

from henchman.cli.input_handler import InputHandler
from henchman.cli.repl import Repl, ReplConfig
from henchman.cli.tool_manager import ToolManager


@pytest.mark.asyncio
async def test_question_reads_literal_answer_without_command_history(tmp_path):
    handler = InputHandler(ReplConfig(), Console(), tmp_path / "history")
    with create_pipe_input() as pipe:
        handler.prompt_session = PromptSession(input=pipe, output=DummyOutput())
        pipe.send_text("/quit @secret.py\n")
        answer = await asyncio.wait_for(handler.ask_question("Which option?"), 2)
    assert answer == "/quit @secret.py"
    assert handler.prompt_session.history.get_strings() == []
    assert not (tmp_path / "history").exists()


@pytest.mark.asyncio
async def test_question_eof_is_unanswered():
    handler = InputHandler(ReplConfig(), Console())
    with create_pipe_input() as pipe:
        handler.prompt_session = PromptSession(input=pipe, output=DummyOutput())
        pipe.send_bytes(b"\x04")
        assert await asyncio.wait_for(handler.ask_question("Continue?"), 2) is None


@pytest.mark.asyncio
async def test_question_ctrl_c_cancels():
    handler = InputHandler(ReplConfig(), Console())
    with create_pipe_input() as pipe:
        handler.prompt_session = PromptSession(input=pipe, output=DummyOutput())
        pipe.send_bytes(b"\x03")
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(handler.ask_question("Continue?"), 2)


@pytest.mark.asyncio
async def test_question_cancellation_releases_prompt_for_next_answer():
    handler = InputHandler(ReplConfig(), Console())
    with create_pipe_input() as pipe:
        handler.prompt_session = PromptSession(input=pipe, output=DummyOutput())
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(handler.ask_question("Old question?"), 0.1)
        pipe.send_text("new answer\n")
        assert await asyncio.wait_for(handler.ask_question("New question?"), 2) == "new answer"


@pytest.mark.asyncio
async def test_tool_manager_binds_question_callback():
    async def answer(question):
        return f"Answer to {question}"

    manager = ToolManager(question_handler=answer)
    manager.register_builtin_tools()
    result = await manager.registry.execute("ask_user", {"question": "Which?"})
    assert result.success
    assert result.content == "Answer to Which?"


class Monitor:
    """Tracks exclusive stdin ownership across concurrent tool requests."""

    def __init__(self):
        self.suspended = False
        self.resumes = 0

    async def suspend(self):
        assert not self.suspended
        self.suspended = True

    def resume(self):
        assert self.suspended
        self.suspended = False
        self.resumes += 1


@pytest.mark.asyncio
async def test_repl_questions_serialize_and_release_monitor_on_cancel(tmp_path):
    repl = Repl(provider=Mock(), config=ReplConfig(history_file=tmp_path / "history"))
    monitor = Monitor()
    repl.current_monitor = monitor
    first_started = asyncio.Event()
    second_started = asyncio.Event()

    async def answer(question):
        assert monitor.suspended
        if question == "first":
            first_started.set()
            await asyncio.Event().wait()
        second_started.set()
        return "second answer"

    repl.input_handler.ask_question = answer
    first = asyncio.create_task(repl.tool_registry.execute("ask_user", {"question": "first"}))
    await asyncio.wait_for(first_started.wait(), 2)
    second = asyncio.create_task(repl.tool_registry.execute("ask_user", {"question": "second"}))
    await asyncio.sleep(0)
    assert not second_started.is_set()
    first.cancel()
    with pytest.raises(asyncio.CancelledError):
        await first
    result = await asyncio.wait_for(second, 2)
    assert result.success
    assert result.content == "second answer"
    assert not monitor.suspended
    assert monitor.resumes == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("output_format", ["text", "json", "stream-json", "json-complete"])
async def test_cli_headless_construction_never_reads_terminal(output_format, tmp_path, monkeypatch):
    from henchman.cli.app import RunConfig, RuntimeContext, _build_repl_instance

    monkeypatch.chdir(tmp_path)
    repl = _build_repl_instance(
        RuntimeContext(provider=Mock(), settings=None, system_prompt="", env_block=""),
        RunConfig(prompt="Do work", output_format=output_format),
        renderer=None,
    )
    touched = False

    async def forbidden_input(_question):
        nonlocal touched
        touched = True
        raise AssertionError("Headless must not read stdin")

    repl.input_handler.ask_question = forbidden_input
    result = await repl.tool_registry.execute("ask_user", {"question": "Which?"})
    assert not touched
    assert not result.success
    assert "No user input handler" in result.error
