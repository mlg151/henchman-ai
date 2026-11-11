"""Configured classic REPL editing modes exercise actual prompt key dispatch."""

import asyncio
from io import StringIO

import pytest
from prompt_toolkit.application import create_app_session
from prompt_toolkit.enums import EditingMode
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput
from rich.console import Console

from henchman.cli.input import create_session
from henchman.cli.repl import Repl, ReplConfig
from henchman.config.schema import Settings
from henchman.providers.base import ModelProvider


class OfflineProvider(ModelProvider):
    name = "mock"

    async def chat_completion_stream(self, messages, tools=None, **kwargs):
        raise AssertionError("Keyboard tests never request inference")
        yield


@pytest.mark.parametrize("mode,expected", [("standard", EditingMode.EMACS), ("vim", EditingMode.VI)])
def test_repl_captures_keyboard_profile_at_prompt_startup(tmp_path, monkeypatch, mode, expected):
    monkeypatch.chdir(tmp_path)
    settings = Settings(ui={"keyboard_mode": mode}, rag={"enabled": False})
    repl = Repl(provider=OfflineProvider(), settings=settings,
                config=ReplConfig(history_file=tmp_path / "history", auto_save=False),
                console=Console(file=StringIO()))
    prompt = repl.input_handler.prompt_session
    assert prompt.app.editing_mode is expected
    settings.ui.keyboard_mode = "standard" if mode == "vim" else "vim"
    assert prompt.app.editing_mode is expected
    assert not (tmp_path / "history").exists()


@pytest.mark.asyncio
async def test_vim_escape_preserves_draft_then_normal_edit_and_submit():
    with create_pipe_input() as pipe, create_app_session(input=pipe, output=DummyOutput()):
        session = create_session(keyboard_mode="vim")
        # Escape enters normal mode; 0x deletes the first character; iH replaces
        # it in insert mode. An Escape-to-clear binding would instead lose hello.
        pipe.send_text("hello\x1b0xiH\r")
        assert await asyncio.wait_for(session.prompt_async("> "), 3) == "Hello"


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["standard", "vim"])
async def test_bracketed_multiline_paste_stays_one_unsubmitted_draft(mode):
    with create_pipe_input() as pipe, create_app_session(input=pipe, output=DummyOutput()):
        session = create_session(keyboard_mode=mode)
        changed = asyncio.Event()
        session.default_buffer.on_text_changed += lambda _buffer: changed.set()
        prompt = asyncio.create_task(session.prompt_async("> "))
        try:
            pipe.send_text("\x1b[200~first\nsecond\x1b[201~")
            await asyncio.wait_for(changed.wait(), 3)
            assert session.default_buffer.text == "first\nsecond"
            assert not prompt.done()
            pipe.send_text("\r")
            assert await asyncio.wait_for(prompt, 3) == "first\nsecond"
        finally:
            if not prompt.done():
                prompt.cancel()
            await asyncio.gather(prompt, return_exceptions=True)


def test_invalid_direct_keyboard_profile_fails_before_prompt_creation():
    with pytest.raises(ValueError, match="keyboard_mode"):
        create_session(keyboard_mode="unknown")


@pytest.mark.asyncio
async def test_active_turn_escape_keeps_cancellation_priority_in_vim(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with create_pipe_input() as pipe, create_app_session(input=pipe, output=DummyOutput()):
        repl = Repl(provider=OfflineProvider(), settings=Settings(ui={"keyboard_mode": "vim"}, rag={"enabled": False}),
                    config=ReplConfig(history_file=tmp_path / "history", auto_save=False),
                    console=Console(file=StringIO()))
        interrupted = asyncio.Event()
        monkeypatch.setattr(repl, "interrupt_agent", interrupted.set)
        worker = asyncio.create_task(asyncio.Event().wait())
        repl._turn_worker = worker
        session = repl.input_handler.prompt_session
        prompt = asyncio.create_task(session.prompt_async("> "))
        try:
            pipe.send_text("unsent draft\x1b")
            await asyncio.wait_for(interrupted.wait(), 3)
            assert not prompt.done()
            assert session.default_buffer.text == "unsent draft"
        finally:
            prompt.cancel()
            worker.cancel()
            await asyncio.gather(prompt, worker, return_exceptions=True)
