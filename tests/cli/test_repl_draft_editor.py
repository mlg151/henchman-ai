"""Actual prompt key dispatch opens composition without accepting the draft."""
import asyncio
from io import StringIO

import pytest
from prompt_toolkit.application import create_app_session
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput
from rich.console import Console

from henchman.cli import input_handler
from henchman.cli.repl import Repl, ReplConfig
from henchman.config.schema import Settings
from tests.cli.test_repl_keyboard_mode import OfflineProvider


@pytest.mark.parametrize("mode", ["standard", "vim"])
async def test_f11_edits_without_submit_or_queue_permission(tmp_path, monkeypatch, mode):
    monkeypatch.chdir(tmp_path)
    entered, release = asyncio.Event(), asyncio.Event()
    async def edit(text, *, authorize, **_kwargs):
        authorize()
        assert text == "original"
        entered.set()
        await release.wait()
        authorize()
        return "edited\ncafé\n"
    monkeypatch.setattr(input_handler, "edit_draft", edit)
    with create_pipe_input() as pipe, create_app_session(input=pipe, output=DummyOutput()):
        repl = Repl(provider=OfflineProvider(), settings=Settings(ui={"keyboard_mode": mode}, rag={"enabled": False}),
                    config=ReplConfig(history_file=tmp_path / "history", auto_save=False), console=Console(file=StringIO()))
        session = repl.input_handler.prompt_session
        prompt = asyncio.create_task(session.prompt_async("> "))
        try:
            pipe.send_text("original\x1b[23~")
            await asyncio.wait_for(entered.wait(), 3)
            assert not prompt.done()
            release.set()
            await repl.input_handler._editor_task
            assert session.default_buffer.text == "edited\ncafé\n"
            assert not prompt.done() and not (tmp_path / "history").exists()
            assert repl._turn_worker is None
        finally:
            await repl.input_handler.close_editor()
            prompt.cancel()
            await asyncio.gather(prompt, return_exceptions=True)


async def test_prompt_shutdown_joins_editor_and_preserves_first_cancel(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    entered, cleanup, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
    async def edit(*_args, **_kwargs):
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            cleanup.set()
            await release.wait()
    monkeypatch.setattr(input_handler, "edit_draft", edit)
    with create_pipe_input() as pipe, create_app_session(input=pipe, output=DummyOutput()):
        repl = Repl(provider=OfflineProvider(), settings=Settings(rag={"enabled": False}),
                    config=ReplConfig(auto_save=False), console=Console(file=StringIO()))
        prompt = asyncio.create_task(repl.input_handler.prompt_session.prompt_async("> "))
        try:
            pipe.send_text("keep\x1b[23~")
            await asyncio.wait_for(entered.wait(), 3)
            close = asyncio.create_task(repl.input_handler.close_editor())
            await cleanup.wait()
            close.cancel("first")
            await asyncio.sleep(0)
            close.cancel("second")
            await asyncio.sleep(0)
            assert not close.done()
            release.set()
            with pytest.raises(asyncio.CancelledError, match="first"):
                await close
            await repl.input_handler.close_editor()
            assert repl.input_handler.prompt_session.default_buffer.text == "keep"
        finally:
            release.set()
            await repl.input_handler.close_editor()
            prompt.cancel()
            await asyncio.gather(prompt, return_exceptions=True)


async def test_explicit_f11_binding_retains_priority_over_editor(tmp_path):
    from henchman.cli.input import create_session

    called = []
    with create_pipe_input() as pipe, create_app_session(input=pipe, output=DummyOutput()):
        prompt = create_session(tmp_path / "history", keybindings={"f11": "abort"}, editor_action=lambda: called.append(True))
        pipe.send_text("keep\x1b[23~")
        async def read():
            # Catch inside the coroutine: KeyboardInterrupt escaping a Task
            # stops asyncio's runner before pytest can observe its result.
            try:
                await prompt.prompt_async("> ")
            except KeyboardInterrupt:
                return "aborted"
            return "submitted"
        assert await asyncio.wait_for(read(), 3) == "aborted"
        assert called == []


async def test_classic_project_switch_revokes_inflight_composition(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    other = tmp_path / "other"
    other.mkdir()
    entered, release = asyncio.Event(), asyncio.Event()
    async def edit(_text, *, authorize, **_kwargs):
        authorize()
        entered.set()
        await release.wait()
        authorize()
        return "wrong project"
    monkeypatch.setattr(input_handler, "edit_draft", edit)
    with create_pipe_input() as pipe, create_app_session(input=pipe, output=DummyOutput()):
        repl = Repl(provider=OfflineProvider(), settings=Settings(rag={"enabled": False}),
                    config=ReplConfig(auto_save=False), console=Console(file=StringIO()))
        prompt = asyncio.create_task(repl.input_handler.prompt_session.prompt_async("> "))
        try:
            pipe.send_text("keep\x1b[23~")
            await asyncio.wait_for(entered.wait(), 3)
            repl.project_root = other
            release.set()
            await repl.input_handler._editor_task
            assert repl.input_handler.prompt_session.default_buffer.text == "keep"
            assert not prompt.done()
        finally:
            release.set()
            await repl.input_handler.close_editor()
            prompt.cancel()
            await asyncio.gather(prompt, return_exceptions=True)


async def test_cancel_before_terminal_entry_preserves_previous_owner(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    async def forbidden(*_args, **_kwargs):
        raise AssertionError("cancelled editor must not start")
    monkeypatch.setattr(input_handler, "edit_draft", forbidden)
    with create_pipe_input() as pipe, create_app_session(input=pipe, output=DummyOutput()):
        repl = Repl(provider=OfflineProvider(), settings=Settings(rag={"enabled": False}),
                    config=ReplConfig(auto_save=False), console=Console(file=StringIO()))
        session = repl.input_handler.prompt_session
        prior = asyncio.get_running_loop().create_future()
        prompt = asyncio.create_task(session.prompt_async("> "))
        try:
            # Wait until prompt has attached its input, then emulate an already
            # owned terminal-print interval ahead of this user composition.
            while not session.app.is_running:
                await asyncio.sleep(0)
            session.app._running_in_terminal_f = prior
            pipe.send_text("keep\x1b[23~")
            async with asyncio.timeout(3):
                while session.app._running_in_terminal_f is prior:
                    await asyncio.sleep(0)
            owned = session.app._running_in_terminal_f
            repl.input_handler.cancel_editor()
            await repl.input_handler._editor_task
            assert not prior.cancelled()
            prior.set_result(None)
            await asyncio.sleep(0)
            assert owned.done()
            assert session.default_buffer.text == "keep" and not prompt.done()
        finally:
            if not prior.done():
                prior.set_result(None)
            # A red implementation leaves its future unresolved; release it
            # only during test teardown, after the ownership assertions.
            hanging = session.app._running_in_terminal_f
            if hanging is not None and not hanging.done():
                hanging.set_result(None)
            await repl.input_handler.close_editor()
            prompt.cancel()
            await asyncio.gather(prompt, return_exceptions=True)
