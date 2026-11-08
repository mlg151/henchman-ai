"""Fresh UI submissions own OAuth; saved commands never grant browser authority."""

# ruff: noqa: F811 -- imported pytest fixtures.

import asyncio
import json
from contextlib import asynccontextmanager
from io import StringIO
from unittest.mock import MagicMock

import pytest
from rich.console import Console
from textual.widgets import TextArea

from henchman.cli.oauth_frontend import FrontendOAuth
from henchman.cli.repl import Repl, ReplConfig
from henchman.cli.textual_app import HenchmanTextualApp
from henchman.cli.textual_config import TextualConfig
from henchman.cli.textual_widgets import ChatPane
from henchman.config.schema import Settings
from tests.cli.test_oauth_browser import wait_until
from tests.mcp.oauth_fixture import OAuthPeer
from tests.mcp.test_oauth_discovery import tls_contexts, trusted_tls  # noqa: F401
from tests.mcp.test_oauth_flow import browser
from tests.mcp.test_oauth_manager import allowed, native_config


class FrontendPeer(OAuthPeer):
    """Independent JSON-RPC responses alongside the owned authorization server."""

    effects = 0

    def auth_route(self, method, path, body):
        if method != "POST" or path != "/mcp":
            return super().auth_route(method, path, body)
        request = json.loads(body)
        name = request["method"]
        if "id" not in request:
            return 202, b"", {}, 0
        if name == "server/discover":
            result = {"supportedVersions": ["2026-07-28"], "capabilities": {"tools": {}}}
        elif name == "initialize":
            result = {"protocolVersion": "2026-07-28", "capabilities": {"tools": {}},
                      "serverInfo": {"name": "frontend-fixture", "version": "1"}}
        elif name == "tools/list":
            result = {"tools": [{"name": "effect", "description": "Owned fixture effect",
                                 "inputSchema": {"type": "object", "properties": {}}}]}
        elif name == "tools/call":
            self.effects += 1
            result = {"content": [{"type": "text", "text": "owned fixture complete"}]}
        else:
            raise AssertionError("Unexpected fixture RPC")
        result["resultType"] = "complete"
        if name in {"server/discover", "tools/list"}:
            result.update({"ttlMs": 0, "cacheScope": "private"})
        return 200, {"jsonrpc": "2.0", "id": request["id"], "result": result}, {}, 0


@asynccontextmanager
async def frontend(kind, tmp_path, settings):
    async def no_browser(_url, _authorize):
        raise AssertionError("This test did not inject an owned synthetic browser")

    provider = MagicMock()
    provider.name = "fixture"
    if kind == "repl":
        ui = Repl(provider, settings=settings, console=Console(file=StringIO()),
                  config=ReplConfig(history_file=tmp_path / "history", auto_save=False))
        ui.session_manager.set_session(ui.session_manager.create_session(ui.session_manager.compute_project_hash(tmp_path)))
        ui._interactive_loop_active = True
        ui._oauth.controller._browser = no_browser
        try:
            yield ui
        finally:
            ui._interactive_loop_active = False
            await ui.aclose()
    else:
        ui = HenchmanTextualApp(provider=provider, settings=settings,
            config=TextualConfig(history_file=tmp_path / "history", auto_save=False))
        async with ui.run_test(size=(100, 40)):
            ui._oauth.controller._browser = no_browser
            yield ui


async def submit(ui, text):
    if isinstance(ui, Repl):
        async def read():
            return text
        ui._get_input = read
        assert await ui._process_one_turn()
    else:
        ui.query_one("#input", TextArea).load_text(text)
        ui.action_submit_message()
    await asyncio.sleep(0)


async def settle(ui):
    await wait_until(lambda: not ui._oauth.has_pending_actions())


def manager(ui):
    return ui.mcp_manager if isinstance(ui, Repl) else ui.core_context.mcp_manager


@pytest.mark.parametrize("kind", ["repl", "textual"])
async def test_fresh_login_then_separate_explicit_connect_and_tool(tmp_path, monkeypatch, trusted_tls, kind):
    monkeypatch.chdir(tmp_path)
    async with FrontendPeer(trusted_tls) as peer:
        peer.enable_oauth()
        async with frontend(kind, tmp_path, Settings(mcp_servers={"fixture": native_config(peer)})) as ui:
            failures = []
            original_connect = manager(ui).connect_oauth_server
            async def connect(*args, **kwargs):
                try:
                    await original_connect(*args, **kwargs)
                except Exception as error:
                    failures.append((str(error), str(error.__context__)))
                    raise
            monkeypatch.setattr(manager(ui), "connect_oauth_server", connect)
            async def open_browser(url, authorize):
                authorize()
                await browser(url)
            ui._oauth.controller._browser = open_browser
            await submit(ui, "/mcp auth login fixture")
            await settle(ui)
            assert manager(ui).oauth_status("fixture", authorize=allowed).state == "ready"
            assert len(peer.token_forms) == 1 and not manager(ui).clients
            await submit(ui, "/mcp connect fixture")
            await settle(ui)
            assert not failures, failures
            tool, = manager(ui).get_all_tools()
            assert (await tool.execute()).success and peer.effects == 1
            await submit(ui, "/mcp auth refresh fixture")
            await settle(ui)
            assert len(peer.token_forms) == 2
            await submit(ui, "/mcp auth logout fixture")
            await settle(ui)
            assert manager(ui).oauth_status("fixture", authorize=allowed).state == "revoked"


@pytest.mark.parametrize("kind", ["repl", "textual"])
async def test_generic_command_cannot_mint_intent_or_open_browser(tmp_path, monkeypatch, trusted_tls, kind):
    monkeypatch.chdir(tmp_path)
    async with FrontendPeer(trusted_tls) as peer:
        peer.enable_oauth()
        async with frontend(kind, tmp_path, Settings(mcp_servers={"fixture": native_config(peer)})) as ui:
            async def forbidden(*_args):
                pytest.fail("Generic command opened browser")
            ui._oauth.controller._browser = forbidden
            for text in ("/mcp auth login fixture", "/mcp auth logout fixture", "/mcp connect fixture"):
                await ui.command_processor.handle_command(text, ui.agent, ui)
            assert not peer.requests
            assert manager(ui).oauth_status("fixture", authorize=allowed).state == "missing"


@pytest.mark.parametrize("kind", ["repl", "textual"])
async def test_busy_network_auth_refused_but_status_logout_remain_available(tmp_path, monkeypatch, trusted_tls, kind):
    monkeypatch.chdir(tmp_path)
    async with (
        FrontendPeer(trusted_tls) as peer,
        frontend(kind, tmp_path, Settings(mcp_servers={"fixture": native_config(peer)})) as ui,
    ):
        busy = asyncio.create_task(asyncio.Event().wait())
        if kind == "repl":
            ui._turn_worker = busy
        else:
            ui.current_agent_task = busy
            ui.is_processing = True
        try:
            for command in ("/mcp auth login fixture", "/mcp auth refresh fixture", "/mcp connect fixture"):
                await submit(ui, command)
                await settle(ui)
            assert peer.requests == []
            await submit(ui, "/mcp auth status fixture")
            await settle(ui)
            await submit(ui, "/mcp auth logout fixture")
            await settle(ui)
            assert manager(ui)._require_oauth_runtime()._store.status("fixture").state == "revoked"
            assert not busy.done()
        finally:
            busy.cancel()
            await asyncio.gather(busy, return_exceptions=True)
            if kind == "textual":
                del ui.current_agent_task
                ui.is_processing = False


@pytest.mark.parametrize("kind", ["repl", "textual"])
async def test_cancel_owned_login_keeps_prompt_responsive_and_joins_callback(tmp_path, monkeypatch, trusted_tls, kind):
    monkeypatch.chdir(tmp_path)
    async with FrontendPeer(trusted_tls) as peer:
        peer.enable_oauth()
        async with frontend(kind, tmp_path, Settings(mcp_servers={"fixture": native_config(peer)})) as ui:
            entered, joined = asyncio.Event(), asyncio.Event()
            async def open_browser(_url, authorize):
                authorize()
                entered.set()
                try:
                    await asyncio.Event().wait()
                finally:
                    joined.set()
            ui._oauth.controller._browser = open_browser
            await submit(ui, "/mcp auth login fixture")
            await asyncio.wait_for(entered.wait(), 3)
            assert ui._oauth.has_pending_actions()
            await submit(ui, "/mcp auth status fixture")
            if kind == "repl":
                ui.interrupt_agent()
            else:
                ui.action_cancel_or_clear()
            await settle(ui)
            assert joined.is_set() and not peer.token_forms
            assert not [task for task in asyncio.all_tasks() if task.get_name().startswith("henchman-oauth-callback")]


@pytest.mark.parametrize("kind", ["repl", "textual"])
@pytest.mark.parametrize("change", ["session", "settings", "project", "agent", "manager"])
async def test_fresh_submission_rechecks_exact_runtime_during_browser_wait(
    tmp_path, monkeypatch, trusted_tls, kind, change,
):
    monkeypatch.chdir(tmp_path)
    async with FrontendPeer(trusted_tls) as peer:
        peer.enable_oauth()
        async with frontend(kind, tmp_path, Settings(mcp_servers={"fixture": native_config(peer)})) as ui:
            entered, release = asyncio.Event(), asyncio.Event()
            async def open_browser(url, authorize):
                entered.set()
                await release.wait()
                authorize()
                await browser(url)
            ui._oauth.controller._browser = open_browser
            await submit(ui, "/mcp auth login fixture")
            await asyncio.wait_for(entered.wait(), 3)
            if change == "session":
                ui.session_manager.session = None
            elif change == "settings":
                ui.settings = ui.settings.model_copy(deep=True)
            elif change == "agent":
                target = ui if kind == "repl" else ui.core_context
                target.agent = ui.orchestrator.pool.get_agent("engineer")
            elif change == "manager":
                from henchman.mcp.manager import McpManager

                target = ui if kind == "repl" else ui.core_context
                target.mcp_manager = McpManager.create_from_settings(ui.settings, project_root=tmp_path)
            else:
                other = tmp_path / "other"
                other.mkdir()
                monkeypatch.chdir(other)
            release.set()
            await settle(ui)
            assert peer.token_forms == []


async def test_task_exclusion_does_not_accept_arbitrary_busy_bypass(tmp_path):
    from types import SimpleNamespace

    from henchman.cli.workflow import frontend_has_active_work

    busy = asyncio.create_task(asyncio.Event().wait())
    ui = SimpleNamespace(_idle_control_task=busy)
    pretend = SimpleNamespace(owns_network_task=lambda *_args: True)
    try:
        assert frontend_has_active_work(ui, _oauth_owner=pretend)
        unrelated = FrontendOAuth(SimpleNamespace(), tmp_path, emit=lambda _text: None, settled=lambda _ok: None)
        assert frontend_has_active_work(ui, _oauth_owner=unrelated)
    finally:
        busy.cancel()
        await asyncio.gather(busy, return_exceptions=True)


@pytest.mark.parametrize("kind", ["repl", "textual"])
@pytest.mark.parametrize("cancel", [False, True])
async def test_message_during_login_waits_and_cancel_keeps_queue_held(tmp_path, monkeypatch, trusted_tls, kind, cancel):
    monkeypatch.chdir(tmp_path)
    async with FrontendPeer(trusted_tls) as peer:
        peer.enable_oauth()
        async with frontend(kind, tmp_path, Settings(mcp_servers={"fixture": native_config(peer)})) as ui:
            entered, release, ran = asyncio.Event(), asyncio.Event(), asyncio.Event()
            async def open_browser(url, authorize):
                entered.set()
                await release.wait()
                authorize()
                await browser(url)
            async def agent(_text, *_args):
                assert not ui._oauth.controller.has_active_action()
                ran.set()
            ui._oauth.controller._browser = open_browser
            monkeypatch.setattr(ui, "_run_agent" if kind == "repl" else "_route_input", agent)
            await submit(ui, "/mcp auth login fixture")
            await asyncio.wait_for(entered.wait(), 3)
            await submit(ui, "queued user task")
            await asyncio.sleep(.05)
            assert not ran.is_set()
            if cancel:
                ui.interrupt_agent() if kind == "repl" else ui.action_cancel_or_clear()
            else:
                release.set()
            await settle(ui)
            if cancel:
                await submit(ui, "/mcp auth status fixture")
                await settle(ui)
                assert not ran.is_set()
                report = ui._workflow().report()
                assert [item.state for item in report.state.inputs] == ["queued"]
            else:
                await asyncio.wait_for(ran.wait(), 3)


@pytest.mark.parametrize("kind", ["repl", "textual"])
async def test_frontend_shutdown_joins_login_without_token_exchange(tmp_path, monkeypatch, trusted_tls, kind):
    monkeypatch.chdir(tmp_path)
    async with FrontendPeer(trusted_tls) as peer:
        peer.enable_oauth()
        joined = asyncio.Event()
        async with frontend(kind, tmp_path, Settings(mcp_servers={"fixture": native_config(peer)})) as ui:
            entered = asyncio.Event()
            async def open_browser(_url, authorize):
                authorize()
                entered.set()
                try:
                    await asyncio.Event().wait()
                finally:
                    joined.set()
            ui._oauth.controller._browser = open_browser
            await submit(ui, "/mcp auth login fixture")
            await asyncio.wait_for(entered.wait(), 3)
        assert joined.is_set() and not peer.token_forms
        assert not ui._oauth.has_pending_actions()
        assert not [task for task in asyncio.all_tasks() if task.get_name().startswith("henchman-oauth-callback")]


@pytest.mark.parametrize("kind", ["repl", "textual"])
async def test_restored_queue_command_has_no_authentication_authority(tmp_path, monkeypatch, trusted_tls, kind):
    from henchman.core.workflow_state import WorkflowError

    monkeypatch.chdir(tmp_path)
    async with (
        FrontendPeer(trusted_tls) as peer,
        frontend(kind, tmp_path, Settings(mcp_servers={"fixture": native_config(peer)})) as ui,
    ):
        item = ui._workflow().submit("/mcp auth login fixture", kind="command")
        restored = ui.session_manager.session_manager.load(ui.session_manager.current.id)
        assert restored is not None
        ui.session_manager.set_session(restored)
        workflow = ui._workflow()
        workflow.send(item.id, item.revision)
        if kind == "repl":
            with pytest.raises(WorkflowError, match="explicit"):
                await ui._drain_workflow_inputs(workflow, continue_goals=False)
        else:
            worker = ui.process_user_input(None)
            await asyncio.wait_for(worker.wait(), 3)
        assert peer.requests == [] and not ui._oauth.has_pending_actions()
        assert manager(ui).oauth_status("fixture", authorize=allowed).state == "missing"


async def test_textual_auth_candidates_never_echo_or_enter_recall_session_or_queue(tmp_path, monkeypatch, trusted_tls):
    monkeypatch.chdir(tmp_path)
    async with (
        FrontendPeer(trusted_tls) as peer,
        frontend("textual", tmp_path, Settings(mcp_servers={"fixture": native_config(peer)})) as ui,
    ):
        chat = ui.query_one("#chat-pane", ChatPane)
        user = MagicMock(wraps=chat.add_user_message)
        system = MagicMock(wraps=chat.add_system_message)
        monkeypatch.setattr(chat, "add_user_message", user)
        monkeypatch.setattr(chat, "add_system_message", system)
        raw = "/mcp auth login fixture https://private.invalid/code-canary"
        await submit(ui, raw)
        await settle(ui)
        assert "canary" not in repr(user.call_args_list) + repr(system.call_args_list)
        assert not ui.command_history
        assert "canary" not in ui.session_manager.current.to_json()
        path = tmp_path / "history"
        assert not path.exists() or "canary" not in path.read_text()
        assert peer.requests == []


async def test_programmatic_textual_auth_command_does_not_echo_unknown_url(tmp_path, monkeypatch, trusted_tls):
    monkeypatch.chdir(tmp_path)
    async with (
        FrontendPeer(trusted_tls) as peer,
        frontend("textual", tmp_path, Settings(mcp_servers={"fixture": native_config(peer)})) as ui,
    ):
        chat = ui.query_one("#chat-pane", ChatPane)
        user = MagicMock(wraps=chat.add_user_message)
        monkeypatch.setattr(chat, "add_user_message", user)
        worker = ui.process_user_input("/mcp auth login fixture https://private.invalid/code-canary")
        await asyncio.wait_for(worker.wait(), 3)
        assert "canary" not in repr(user.call_args_list)
        assert peer.requests == []


async def test_cancel_before_frontend_action_starts_releases_exact_reservation(tmp_path, monkeypatch, trusted_tls):
    monkeypatch.chdir(tmp_path)
    async with (
        FrontendPeer(trusted_tls) as peer,
        frontend("repl", tmp_path, Settings(mcp_servers={"fixture": native_config(peer)})) as ui,
    ):
        assert ui._oauth.submit("/mcp auth login fixture")
        task = ui._idle_control_task
        assert ui._oauth.cancel()
        await settle(ui)
        await asyncio.sleep(0)
        assert task.cancelled() and ui._idle_control_task is None
        assert not peer.requests


async def test_real_repl_pipe_login_escape_and_quit_join_owned_action(tmp_path, monkeypatch, trusted_tls):
    from prompt_toolkit.application import create_app_session
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput

    monkeypatch.chdir(tmp_path)
    async with FrontendPeer(trusted_tls) as peer:
        peer.enable_oauth()
        with create_pipe_input() as pipe, create_app_session(input=pipe, output=DummyOutput()):
            async with frontend("repl", tmp_path, Settings(mcp_servers={"fixture": native_config(peer)})) as ui:
                entered, joined = asyncio.Event(), asyncio.Event()
                async def open_browser(_url, authorize):
                    authorize()
                    entered.set()
                    try:
                        await asyncio.Event().wait()
                    finally:
                        joined.set()
                ui._oauth.controller._browser = open_browser
                monkeypatch.setattr(ui.output_handler, "start_background_indexing", lambda: None)
                runner = asyncio.create_task(ui.run())
                prompt = ui.input_handler.prompt_session
                try:
                    await wait_until(lambda: prompt.app.is_running)
                    pipe.send_text("/mcp auth login fixture\n")
                    await asyncio.wait_for(entered.wait(), 3)
                    await wait_until(lambda: prompt.app.is_running)
                    pipe.send_text("\x1b")
                    await asyncio.wait_for(joined.wait(), 3)
                    await settle(ui)
                    pipe.send_text("/quit\n")
                    await asyncio.wait_for(runner, 3)
                    assert not peer.token_forms
                    assert all("/mcp auth" not in text for text in prompt.history.get_strings())
                finally:
                    if not runner.done():
                        runner.cancel()
                    await asyncio.gather(runner, return_exceptions=True)


async def test_textual_without_live_oauth_owner_refuses_without_history(tmp_path, monkeypatch, trusted_tls):
    monkeypatch.chdir(tmp_path)
    async with (
        FrontendPeer(trusted_tls) as peer,
        frontend("textual", tmp_path, Settings(mcp_servers={"fixture": native_config(peer)})) as ui,
    ):
        owner = ui._oauth
        del ui._oauth
        try:
            await submit(ui, "/mcp auth login fixture https://private.invalid/code-canary")
            await asyncio.sleep(.05)
            assert not ui.command_history
            path = tmp_path / "history"
            assert not path.exists() or "canary" not in path.read_text()
        finally:
            ui._oauth = owner


@pytest.mark.parametrize("kind", ["repl", "textual"])
async def test_browser_failure_is_value_free_and_never_exchanges_token(tmp_path, monkeypatch, trusted_tls, kind):
    monkeypatch.chdir(tmp_path)
    async with FrontendPeer(trusted_tls) as peer:
        peer.enable_oauth()
        async with frontend(kind, tmp_path, Settings(mcp_servers={"fixture": native_config(peer)})) as ui:
            messages = []
            original_emit = ui._oauth._emit
            def emit(text):
                messages.append(text)
                original_emit(text)
            ui._oauth._emit = emit
            async def failed_browser(_url, authorize):
                authorize()
                raise OSError("https://private.invalid/novel-url-canary")
            ui._oauth.controller._browser = failed_browser
            await submit(ui, "/mcp auth login fixture")
            await settle(ui)
            assert "failed" in " ".join(messages).lower() and "canary" not in " ".join(messages)
            assert peer.token_forms == [] and manager(ui).clients == {}


@pytest.mark.parametrize("kind", ["repl", "textual"])
async def test_goal_start_during_login_requires_fresh_submission_after_idle(tmp_path, monkeypatch, trusted_tls, kind):
    from henchman.core.goals import GoalService

    monkeypatch.chdir(tmp_path)
    async with FrontendPeer(trusted_tls) as peer:
        peer.enable_oauth()
        async with frontend(kind, tmp_path, Settings(mcp_servers={"fixture": native_config(peer)})) as ui:
            entered = asyncio.Event()
            async def open_browser(_url, authorize):
                authorize()
                entered.set()
                await asyncio.Event().wait()
            ui._oauth.controller._browser = open_browser
            await submit(ui, "/mcp auth login fixture")
            await asyncio.wait_for(entered.wait(), 3)
            await submit(ui, "/goal Finish the fixture")
            await asyncio.sleep(.05)
            assert GoalService().get(ui.session_manager.current) is None
            if kind == "textual":
                assert ui.query_one("#input", TextArea).text == "/goal Finish the fixture"
            ui.interrupt_agent() if kind == "repl" else ui.action_cancel_or_clear()
            await settle(ui)
            assert peer.token_forms == []


@pytest.mark.parametrize("kind", ["repl", "textual"])
async def test_stale_action_completion_does_not_hold_replacement_session_input(tmp_path, monkeypatch, trusted_tls, kind):
    monkeypatch.chdir(tmp_path)
    async with FrontendPeer(trusted_tls) as peer:
        peer.enable_oauth()
        async with frontend(kind, tmp_path, Settings(mcp_servers={"fixture": native_config(peer)})) as ui:
            entered, release = asyncio.Event(), asyncio.Event()
            async def open_browser(_url, authorize):
                entered.set()
                await release.wait()
                authorize()
            ui._oauth.controller._browser = open_browser
            await submit(ui, "/mcp auth login fixture")
            await asyncio.wait_for(entered.wait(), 3)
            replacement = ui.session_manager.create_session(ui.session_manager.compute_project_hash(tmp_path))
            ui.session_manager.set_session(replacement)
            workflow = ui._workflow()
            workflow.submit("new session task")
            assert workflow.has_ready_input()
            release.set()
            await settle(ui)
            assert workflow.has_ready_input()
            assert peer.token_forms == []


@pytest.mark.parametrize("phase", ["hold", "prompts", "activity"])
async def test_unmount_retirement_failure_still_joins_owned_oauth_and_remaining_runtime(
    tmp_path, monkeypatch, trusted_tls, phase,
):
    from henchman.cli.textual_activity_state import activity_for
    from henchman.core.workflow_state import WorkflowError

    monkeypatch.chdir(tmp_path)
    async with FrontendPeer(trusted_tls) as peer:
        peer.enable_oauth()
        async with frontend("textual", tmp_path, Settings(mcp_servers={"fixture": native_config(peer)})) as ui:
            entered, joined = asyncio.Event(), asyncio.Event()
            async def open_browser(_url, authorize):
                authorize()
                entered.set()
                try:
                    await asyncio.Event().wait()
                finally:
                    joined.set()
            ui._oauth.controller._browser = open_browser
            await submit(ui, "/mcp auth login fixture")
            await asyncio.wait_for(entered.wait(), 3)
            primary = WorkflowError("simulated durable hold failure")
            owner, method = {
                "hold": (ui._workflow(), "hold_pending"),
                "prompts": (ui, "_cleanup_confirm_futures"),
                "activity": (activity_for(ui), "shutdown"),
            }[phase]
            original_retire = getattr(owner, method)
            def fail_retirement():
                raise primary
            monkeypatch.setattr(owner, method, fail_retirement)
            closed = []
            original_agent_close = ui.core_context.orchestrator.aclose
            original_mcp_close = manager(ui).disconnect_all
            async def close_agent():
                await original_agent_close()
                closed.append("agent")
            async def close_mcp():
                await original_mcp_close()
                closed.append("mcp")
            monkeypatch.setattr(ui.core_context.orchestrator, "aclose", close_agent)
            monkeypatch.setattr(manager(ui), "disconnect_all", close_mcp)
            worker_joined, background_joined = asyncio.Event(), asyncio.Event()
            async def owned_work(settled):
                try:
                    await asyncio.Event().wait()
                finally:
                    settled.set()
            worker = asyncio.create_task(owned_work(worker_joined))
            background = asyncio.create_task(owned_work(background_joined))
            ui.current_agent_task = worker
            ui.core_context.background_tasks.add(background)
            await asyncio.sleep(0)
            try:
                with pytest.raises(WorkflowError) as caught:
                    await ui.on_unmount()
                assert caught.value is primary
                assert joined.is_set() and worker_joined.is_set() and background_joined.is_set()
                assert closed == ["agent", "mcp"]
                assert not ui._oauth.has_pending_actions() and not peer.token_forms
                assert not ui.core_context.background_tasks
                assert not [task for task in asyncio.all_tasks() if task.get_name().startswith("henchman-oauth-callback")]
            finally:
                monkeypatch.setattr(owner, method, original_retire)
                await ui._oauth.aclose()
                worker.cancel()
                background.cancel()
                await asyncio.gather(worker, background, return_exceptions=True)
