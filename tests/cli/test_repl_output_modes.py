"""Real classic REPL consumers, evidence, and pipe prompts for output modes."""

import asyncio
from io import StringIO
from types import SimpleNamespace

import pytest
from prompt_toolkit import PromptSession
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput
from prompt_toolkit.output.plain_text import PlainTextOutput
from rich.console import Console

from henchman.cli import app
from henchman.cli.output_handler import OutputHandler
from henchman.cli.repl import Repl, ReplConfig
from henchman.cli.session_manager import ReplSessionManager
from henchman.cli.tool_executor import ToolExecutor
from henchman.cli.ui_renderer import UIRenderer
from henchman.config.schema import Settings
from henchman.core.agent import Agent
from henchman.core.events import AgentEvent, EventType
from henchman.core.session import SessionManager
from henchman.providers.base import Message, ModelProvider, ToolCall
from henchman.tools.base import ConfirmationRequest, Tool, ToolResult
from henchman.tools.registry import ToolRegistry


class OfflineProvider(ModelProvider):
    name = "mock"

    async def chat_completion_stream(self, messages, tools=None, **kwargs):
        raise AssertionError("No inference is needed by output tests")
        yield  # pragma: no cover


def make_repl(tmp_path, mode, **kwargs):
    settings = Settings(ui={"output_mode": mode}, rag={"enabled": False})
    output = StringIO()
    repl = Repl(
        provider=OfflineProvider(), settings=settings,
        config=ReplConfig(history_file=tmp_path / "history", auto_save=False, **kwargs),
        console=Console(file=output, force_terminal=True, color_system="standard", no_color=False),
    )
    return repl, output


@pytest.mark.parametrize("mode", ["rich", "plain", "quiet"])
def test_direct_repl_captures_mode_and_toolbar_at_startup(tmp_path, monkeypatch, mode):
    monkeypatch.chdir(tmp_path)
    repl, output = make_repl(tmp_path, mode)
    assert repl.renderer.output_mode == mode
    assert repl.console is repl.renderer.console
    assert bool(repl.input_handler.prompt_session.bottom_toolbar) == (mode == "rich")
    repl.settings.ui.output_mode = "rich" if mode != "rich" else "quiet"
    assert repl.renderer.output_mode == mode
    repl.renderer.warning("still visible")
    assert "still visible" in output.getvalue()
    assert ("\x1b" in output.getvalue()) == (mode == "rich")


@pytest.mark.parametrize("mode", ["plain", "quiet"])
def test_noninteractive_repl_does_not_apply_interactive_mode(tmp_path, monkeypatch, mode):
    monkeypatch.chdir(tmp_path)
    repl, _ = make_repl(tmp_path, mode, interactive=False)
    assert repl.renderer.output_mode == "rich"


@pytest.mark.parametrize("mode", ["plain", "quiet"])
def test_app_renderer_only_opts_interactive_startup_into_mode(mode, monkeypatch):
    console = Console(file=StringIO(), force_terminal=True)
    monkeypatch.setattr(app, "console", console)
    settings = Settings(ui={"output_mode": mode})
    _, interactive = app._get_theme_and_renderer(settings, interactive=True)
    _, headless = app._get_theme_and_renderer(settings, silent=True)
    assert interactive.output_mode == mode
    assert headless.output_mode == "rich"
    assert headless.console is console
    assert console.is_terminal


@pytest.mark.asyncio
async def test_stream_modes_keep_identical_evidence_and_critical_outcomes(tmp_path):
    transcripts = []
    for mode in ("rich", "plain", "quiet"):
        stream = StringIO()
        provider = OfflineProvider()
        registry = ToolRegistry()
        agent = Agent(provider=provider, tool_registry=registry)
        sessions = ReplSessionManager(SessionManager(data_dir=tmp_path / mode))
        sessions.set_session(sessions.create_session("project"))
        manager = SimpleNamespace(registry=registry)
        output = OutputHandler(UIRenderer(console=Console(file=stream, width=200), output_mode=mode), manager, sessions, provider)
        executor = ToolExecutor(output, manager, provider)

        async def events():
            yield AgentEvent(EventType.THOUGHT, "private reasoning chatter")
            yield AgentEvent(EventType.TOOL_CALL_REQUEST, ToolCall("one", "fixture_tool", {"api_key": "rotated-secret-canary"}))
            yield AgentEvent(EventType.TOOL_CALL_RESULT, {"tool_call_id": "one", "result": "routine successful preview", "success": True})
            for success in (False, None, "true"):
                yield AgentEvent(EventType.TOOL_CALL_RESULT, {"tool_call_id": "observed", "result": f"critical outcome {success}", "success": success}, source_agent="other")
            yield AgentEvent(EventType.TOOL_CALL_RESULT, {"result": "missing outcome"}, source_agent="other")
            yield AgentEvent(EventType.AGENT_DELEGATED, {"from": "leader", "to": "engineer", "task": "routine delegation"})
            yield AgentEvent(EventType.AGENT_COMPLETED, {"agent": "engineer", "status": "no_work_done"})
            yield AgentEvent(EventType.CONTENT, "Final answer rotated-secret-canary [bold]literal[/bold]")
            yield AgentEvent(EventType.ERROR, "important failure")
            yield AgentEvent(EventType.FINISHED, None)

        collector = []
        await executor.process_agent_stream(events(), agent, collector)
        transcripts.append([item.to_dict() for item in sessions.current.messages])
        text = stream.getvalue()
        for value in ("Final answer", "[bold]literal[/bold]", "important failure", "without making changes", "critical outcome False", "critical outcome None", "critical outcome true", "missing outcome"):
            assert value in text
        assert "rotated-secret-canary" not in text and "[REDACTED]" in text
        assert collector == ["Final answer rotated-secret-canary [bold]literal[/bold]"]
        for chatter in ("private reasoning chatter", "routine successful preview", "routine delegation"):
            assert (chatter in text) == (mode != "quiet")
    assert transcripts[0] == transcripts[1] == transcripts[2]


@pytest.mark.parametrize("mode", ["plain", "quiet"])
@pytest.mark.asyncio
async def test_pipe_approvals_and_literal_questions_remain_usable(tmp_path, monkeypatch, mode):
    monkeypatch.chdir(tmp_path)
    repl, _ = make_repl(tmp_path, mode)
    repl._interactive_loop_active = True
    request = ConfirmationRequest("write_file", "Write exact file", {"path": "important.txt"})
    prompts = StringIO()
    with create_pipe_input() as pipe:
        repl.input_handler.prompt_session = PromptSession(input=pipe, output=PlainTextOutput(prompts))
        pipe.send_text("yes\n")
        assert await asyncio.wait_for(repl._handle_confirmation(request), 2)
        pipe.send_text("no\n")
        assert not await asyncio.wait_for(repl._handle_confirmation(request), 2)
        pipe.send_text("/quit @literal\n")
        assert await asyncio.wait_for(repl._ask_question("Which value?"), 2) == "/quit @literal"
        assert repl.input_handler.prompt_session.history.get_strings() == []
    assert "important.txt" in prompts.getvalue()
    assert "[y/N]" in prompts.getvalue()
    assert "Which value?" in prompts.getvalue()


@pytest.mark.parametrize("mode", ["plain", "quiet"])
@pytest.mark.asyncio
async def test_interrupt_feedback_precedes_joined_cleanup(tmp_path, monkeypatch, mode):
    monkeypatch.chdir(tmp_path)
    repl, output = make_repl(tmp_path, mode)
    repl._interactive_loop_active = True
    started, cleaning, release, closed = (asyncio.Event() for _ in range(4))

    async def stream():
        try:
            yield AgentEvent(EventType.CONTENT, "partial answer")
            started.set()
            await asyncio.Event().wait()
        finally:
            cleaning.set()
            await release.wait()
            closed.set()

    repl._turn_worker = asyncio.create_task(repl._run_agent_with_monitor(stream(), repl.agent, [], None))
    try:
        await asyncio.wait_for(started.wait(), 2)
        repl.interrupt_agent()
        await asyncio.wait_for(cleaning.wait(), 2)
        assert "Interrupt requested; pending work is held." in output.getvalue()
        assert not closed.is_set() and not repl._turn_worker.done()
    finally:
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await repl._turn_worker
    assert closed.is_set()
    assert "partial answer" in output.getvalue()
    assert not repl.renderer.is_thinking


def test_quiet_keeps_limit_warning_and_background_indexing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    repl, output = make_repl(tmp_path, "quiet")
    calls = []
    monkeypatch.setattr(repl.output_handler, "_start_rag_indexing", lambda: calls.append("index"))
    turn = SimpleNamespace(get_status_string=lambda **_kw: "healthy status", is_spinning=lambda: False, is_approaching_limit=lambda _: False)
    repl.output_handler.show_turn_status(SimpleNamespace(turn=turn), 25)
    assert calls == ["index"]
    assert "healthy status" not in output.getvalue()
    turn.is_spinning = lambda: True
    repl.output_handler.show_turn_status(SimpleNamespace(turn=turn), 25)
    assert "healthy status" in output.getvalue()


@pytest.mark.parametrize("mode", ["plain", "quiet"])
@pytest.mark.asyncio
async def test_explicit_commands_still_show_results_and_errors(tmp_path, monkeypatch, mode):
    monkeypatch.chdir(tmp_path)
    repl, output = make_repl(tmp_path, mode)
    for command in ("/config get ui.output_mode", "/usage", "/not_a_command"):
        assert await repl.command_processor.handle_command(command, repl.agent, repl)
    text = output.getvalue()
    assert mode in text
    assert "No run accounting is available." in text
    assert "Unknown command: /not_a_command" in text
    assert "Type /help for available commands" in text
    assert "\x1b" not in text


@pytest.mark.parametrize("mode", ["plain", "quiet"])
@pytest.mark.parametrize("output_format", ["text", "json", "stream-json", "json-complete"])
def test_actual_headless_factory_keeps_rich_mode(mode, output_format, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    settings = Settings(ui={"output_mode": mode}, rag={"enabled": False})
    monkeypatch.setattr(app, "_prepare_runtime_context", lambda: app.RuntimeContext(
        provider=OfflineProvider(), settings=settings, system_prompt="", env_block="",
    ))
    monkeypatch.setattr(app, "_setup_repl_session", lambda _repl: None)
    monkeypatch.setattr(app, "_setup_repl_rag", lambda *_args, **_kwargs: None)
    repl, _, _ = app._create_headless_repl(app.RunConfig(prompt="scripted", output_format=output_format))
    assert not repl.config.interactive
    assert repl.renderer.output_mode == "rich"


@pytest.mark.parametrize("mode", ["plain", "quiet"])
def test_actual_interactive_factory_uses_mode_for_startup_and_rag(mode, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    output = StringIO()
    monkeypatch.setattr(app, "console", Console(file=output, force_terminal=True))
    settings = Settings(ui={"output_mode": mode}, rag={"enabled": False})
    monkeypatch.setattr(app, "_prepare_runtime_context", lambda: app.RuntimeContext(
        provider=OfflineProvider(), settings=settings, system_prompt="", env_block="",
    ))
    monkeypatch.setattr(app, "_setup_repl_session", lambda _repl: None)
    consoles = []

    def initialize(_settings, *, console, index):
        assert index is False
        consoles.append(console)
        return None

    monkeypatch.setattr("henchman.rag.initialize_rag", initialize)
    rendered = []

    def dispatch(repl, _config):
        rendered.append(repl)
        repl.renderer.print_welcome()
        repl.renderer.warning("startup warning")

    monkeypatch.setattr(app, "_dispatch_interactive_run", dispatch)
    app._run_interactive(app.RunConfig())
    assert rendered[0].renderer.output_mode == mode
    assert consoles == [rendered[0].renderer.console]
    assert "startup warning" in output.getvalue()
    assert "\x1b" not in output.getvalue()
    assert ("Henchman-AI" in output.getvalue()) == (mode == "plain")


@pytest.mark.parametrize("mode", ["plain", "quiet"])
@pytest.mark.asyncio
async def test_question_cancellation_releases_prompt_without_hiding_next_answer(mode, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    repl, _ = make_repl(tmp_path, mode)
    repl._interactive_loop_active = True
    with create_pipe_input() as pipe:
        repl.input_handler.prompt_session = PromptSession(input=pipe, output=DummyOutput())
        pipe.send_bytes(b"\x03")
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(repl._ask_question("Old question?"), 2)
        pipe.send_text("fresh answer\n")
        assert await asyncio.wait_for(repl._ask_question("Next question?"), 2) == "fresh answer"


@pytest.mark.parametrize("mode", ["rich", "plain", "quiet"])
@pytest.mark.asyncio
async def test_real_tool_execution_receives_raw_arguments_and_records_same_result(mode, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    repl, output = make_repl(tmp_path, mode)
    observed = []

    class Echo(Tool):
        name = "fixture_echo"
        description = "Local fixture only"

        async def execute(self, **params):
            observed.append(params)
            return ToolResult("successful fixture result")

    repl.tool_registry.register(Echo())
    call = ToolCall("echo-call", "fixture_echo", {"api_key": "execution-secret-canary"})
    repl.agent.messages.append(Message(role="assistant", tool_calls=[call]))
    session = repl.session_manager.create_session("project")
    repl.session_manager.set_session(session)
    repl.session_manager.record_agent_message(None, tool_calls=[{"id": call.id, "name": call.name, "arguments": call.arguments}])
    responded = set()
    await repl.tool_executor._execute_and_record_tool_call(call, repl.agent, responded)
    assert observed == [{"api_key": "execution-secret-canary"}]
    assert responded == {call.id}
    assert repl.agent.messages[-1].content == "successful fixture result"
    assert session.messages[-1].content == "successful fixture result"
    assert session.messages[-1].tool_call_id == call.id
    assert "execution-secret-canary" not in output.getvalue()
    assert ("successful fixture result" in output.getvalue()) == (mode != "quiet")


@pytest.mark.parametrize("mode", ["plain", "quiet"])
def test_interactive_format_warning_uses_transcript_console(mode, monkeypatch):
    scoped_output, global_output = StringIO(), StringIO()
    renderer = UIRenderer(console=Console(file=scoped_output), output_mode=mode)
    monkeypatch.setattr(app, "console", Console(file=global_output))
    monkeypatch.setattr(app.anyio, "run", lambda *_args: None)
    repl = SimpleNamespace(renderer=renderer, run=lambda: None)
    app._dispatch_interactive_run(repl, app.RunConfig(output_format="json"))
    assert "JSON output formats not supported" in scoped_output.getvalue()
    assert not global_output.getvalue()
