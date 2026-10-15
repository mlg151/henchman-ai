"""Question prompts relinquish the real key monitor and survive cancellation."""

import asyncio
from contextlib import suppress
from unittest.mock import Mock

import pytest
from prompt_toolkit import PromptSession
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput

from henchman.cli.input import KeyMonitor
from henchman.cli.repl import Repl, ReplConfig


@pytest.mark.asyncio
async def test_ctrl_c_question_releases_monitor_for_next_answer(monkeypatch, tmp_path):
    """A cancelled prompt cannot steal input from the next question or monitor."""
    repl = Repl(
        provider=Mock(),
        config=ReplConfig(auto_save=False, history_file=tmp_path / "history"),
    )
    with create_pipe_input() as pipe:
        # Keep the real monitor loop and input parser, substituting only stdin.
        with monkeypatch.context() as patch:
            patch.setattr("prompt_toolkit.input.create_input", lambda: pipe)
            monitor = KeyMonitor()
        repl.current_monitor = monitor
        repl.input_handler.prompt_session = PromptSession(input=pipe, output=DummyOutput())
        prompt_started = asyncio.Queue()
        ask_question = repl.input_handler.ask_question

        async def observe_prompt(question):
            # Repl calls this only after the monitor has relinquished raw mode.
            prompt_started.put_nowait(question)
            return await ask_question(question)

        monkeypatch.setattr(repl.input_handler, "ask_question", observe_prompt)
        monitoring = asyncio.create_task(monitor.monitor())
        questions = []

        async def wait_for_raw_mode():
            while not monitor._in_raw_mode:
                await asyncio.sleep(0)

        try:
            await asyncio.wait_for(wait_for_raw_mode(), 2)
            first = asyncio.create_task(
                repl.tool_registry.execute("ask_user", {"question": "First question?"})
            )
            questions.append(first)
            assert await asyncio.wait_for(prompt_started.get(), 2) == "First question?"
            assert not monitor._in_raw_mode
            pipe.send_bytes(b"\x03")
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(first, 2)

            # Require the actual monitor to reacquire input before a new prompt.
            await asyncio.wait_for(wait_for_raw_mode(), 2)
            second = asyncio.create_task(
                repl.tool_registry.execute("ask_user", {"question": "Second question?"})
            )
            questions.append(second)
            assert await asyncio.wait_for(prompt_started.get(), 2) == "Second question?"
            assert not monitor._in_raw_mode
            pipe.send_text("actual answer\n")
            result = await asyncio.wait_for(second, 2)
            assert result.success
            assert result.content == "actual answer"

            await asyncio.wait_for(wait_for_raw_mode(), 2)
            # Ctrl+C must again reach the monitor rather than an abandoned prompt.
            pipe.send_bytes(b"\x03")
            await asyncio.wait_for(monitoring, 2)
            assert monitor.exit_requested
            assert not monitor._in_raw_mode
        finally:
            for question in questions:
                question.cancel()
            await asyncio.wait_for(asyncio.gather(*questions, return_exceptions=True), 2)
            monitor._stop_event.set()
            with suppress(asyncio.CancelledError):
                await asyncio.wait_for(monitoring, 2)
