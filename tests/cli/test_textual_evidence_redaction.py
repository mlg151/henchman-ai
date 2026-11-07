"""Textual receives display copies while tool execution retains original inputs."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from henchman.cli.evidence import runtime_evidence_redactor
from henchman.cli.session_manager import ReplSessionManager
from henchman.cli.textual_bridge import EventBridge, TuiConsoleAdapter
from henchman.cli.textual_messages import (
    AgentContentMessage,
    AgentThoughtMessage,
    ToolCallRequestMessage,
)
from henchman.cli.textual_questions import ToolPromptChannel
from henchman.core.events import AgentEvent, EventType
from henchman.core.session_manager import SessionManager
from henchman.providers.base import ToolCall
from henchman.tools.base import ConfirmationRequest
from henchman.utils.evidence_redaction import EvidenceRedactor


def runtime(tmp_path, *secrets):
    policy = EvidenceRedactor(secrets)
    sessions = ReplSessionManager(SessionManager(data_dir=tmp_path, evidence_redactor=policy))
    app = SimpleNamespace(
        core_context=SimpleNamespace(session_manager=sessions), post_message=MagicMock(),
    )
    return app, policy


async def test_bridge_masks_split_and_marked_credentials_without_changing_tools(tmp_path):
    app, _ = runtime(tmp_path, "known-canary")
    bridge = EventBridge(app)
    call = ToolCall(id="call", name="custom", arguments={"api_key": "marked-canary"})
    events = [
        AgentEvent(EventType.CONTENT, "known-", "leader"),
        AgentEvent(EventType.THOUGHT, "known-", "reviewer"),
        AgentEvent(EventType.TOOL_CALL_REQUEST, call, "leader"),
        AgentEvent(EventType.CONTENT, "canary marked-canary!", "leader"),
        AgentEvent(EventType.THOUGHT, "canary!", "reviewer"),
        AgentEvent(EventType.FINISHED, "stop", "leader"),
        AgentEvent(EventType.FINISHED, "stop", "reviewer"),
    ]

    async def stream():
        for event in events:
            yield event

    await bridge.forward_events(stream())
    messages = [item.args[0] for item in app.post_message.call_args_list]
    assert "".join(msg.content for msg in messages if isinstance(msg, AgentContentMessage)) == "[REDACTED] [REDACTED]!"
    assert "".join(msg.thought for msg in messages if isinstance(msg, AgentThoughtMessage)) == "[REDACTED]!"
    shown = next(msg.tool_call for msg in messages if isinstance(msg, ToolCallRequestMessage))
    assert shown.id == call.id
    assert shown.arguments["api_key"] == "[REDACTED]"
    assert call.arguments["api_key"] == "marked-canary"
    assert events[0].data == "known-"


@pytest.mark.parametrize("cancel", [False, True])
async def test_bridge_flushes_interruption_and_masks_traceback(tmp_path, cancel):
    app, _ = runtime(tmp_path, "private-canary")
    bridge = EventBridge(app)

    async def stream():
        yield AgentEvent(EventType.CONTENT, "prefix private-", "worker")
        if cancel:
            raise asyncio.CancelledError
        raise RuntimeError("transport private-canary")

    if cancel:
        with pytest.raises(asyncio.CancelledError):
            await bridge.forward_events(stream())
    else:
        await bridge.forward_events(stream())
    messages = [item.args[0] for item in app.post_message.call_args_list]
    visible = "".join(msg.content for msg in messages if isinstance(msg, AgentContentMessage))
    assert "private-" not in visible
    assert "[REDACTED]" in visible


async def test_approval_uses_a_safe_copy_and_retains_explicit_answer(tmp_path):
    app, _ = runtime(tmp_path)
    channel = ToolPromptChannel(app)
    channel._show = AsyncMock(return_value=True)
    request = ConfirmationRequest(
        "shell", "run marked-canary", {"api_key": "marked-canary", "command": "echo marked-canary"},
    )
    assert await channel.confirm(request) is True
    shown = channel._show.call_args.args[0]._request
    assert shown is not request
    assert shown.description == "run [REDACTED]"
    assert shown.params["command"] == "echo [REDACTED]"
    assert request.params["api_key"] == "marked-canary"
    channel._show.return_value = False
    assert await channel.confirm(request) is False


async def test_approval_redacts_metadata_and_non_json_parameter_objects(tmp_path):
    from pathlib import Path

    app, _ = runtime(tmp_path, "private-canary")
    channel = ToolPromptChannel(app)
    channel._show = AsyncMock(return_value=False)
    request = ConfirmationRequest(
        "tool-private-canary", "safe", {"path": Path("private-canary")}, "private-canary",
    )
    assert await channel.confirm(request) is False
    shown = channel._show.call_args.args[0]._request
    assert shown.tool_name == "tool-[REDACTED]"
    assert shown.risk_level == "[REDACTED]"
    assert shown.params["path"] == "[REDACTED]"
    assert request.params["path"] == Path("private-canary")


def test_embedded_fallback_policy_persists_marked_credentials():
    app = SimpleNamespace()
    policy = runtime_evidence_redactor(app)
    policy.register_config({"secret": "embedded-canary"})
    assert runtime_evidence_redactor(app).text("embedded-canary") == "[REDACTED]"


def test_console_adapter_masks_credentials_across_styles_and_prints(tmp_path):
    from rich.text import Text

    app, _ = runtime(tmp_path, "private-canary")
    adapter = TuiConsoleAdapter(app)
    adapter.print("private-", end="")
    adapter.print("canary!")
    styled = Text("private-canary!")
    styled.stylize("bold red", 3, 10)
    adapter.print(styled)
    shown = "".join(call.args[0].text for call in app.post_message.call_args_list)
    assert "private-" not in shown
    assert shown.count("[REDACTED]") == 2


def test_console_adapter_consumes_separate_newline_after_auth_header(tmp_path):
    app, _ = runtime(tmp_path)
    adapter = TuiConsoleAdapter(app)
    adapter.print("Authorization: unknown-canary", end="")
    adapter.print("")
    adapter.print("ordinary next line!")
    shown = "".join(call.args[0].text for call in app.post_message.call_args_list)
    assert "unknown-canary" not in shown
    assert "ordinary next line!" in shown


async def test_outer_run_completion_flushes_workers_before_status(tmp_path):
    from henchman.cli.textual_messages import AgentStatusMessage

    app, _ = runtime(tmp_path, "private-canary")
    bridge = EventBridge(app)

    async def stream():
        yield AgentEvent(EventType.CONTENT, "private-", "worker")
        yield AgentEvent(EventType.AGENT_COMPLETED, {
            "agent": "leader", "status": "failed", "scope": "run",
        }, "orchestrator")

    await bridge.forward_events(stream())
    messages = [item.args[0] for item in app.post_message.call_args_list]
    assert isinstance(messages[0], AgentContentMessage)
    assert messages[0].content == "[REDACTED]"
    assert isinstance(messages[-1], AgentStatusMessage)


async def test_queued_approval_refreshes_rotated_key_before_mount(tmp_path):
    from textual.app import App
    from textual.widgets import Label

    context, policy = runtime(tmp_path)
    app = App()
    app.core_context = context.core_context
    channel = ToolPromptChannel(app)
    request = ConfirmationRequest("shell", "run rotated-canary", {"command": "echo rotated-canary"})
    async with app.run_test(size=(100, 40)) as pilot:
        first = asyncio.create_task(channel.ask("First question"))
        await pilot.pause()
        approval = asyncio.create_task(channel.confirm(request))
        await pilot.pause()
        policy.register_secret("rotated-canary")
        await pilot.press("escape")
        assert await first is None
        await pilot.pause()
        visible = " ".join(str(label.content) for label in app.screen.query(Label))
        assert "rotated-canary" not in visible
        assert "REDACTED" in visible
        await pilot.press("y")
        assert await approval is True
        assert request.params["command"] == "echo rotated-canary"


@pytest.mark.parametrize("direct_console", [False, True])
@pytest.mark.parametrize("kind", ["long", "header", "markup", "split_ansi"])
def test_console_projects_before_wrapping_and_markup(tmp_path, direct_console, kind):
    long_secret = "private-canary-" + "0123456789" * 12
    markup_secret = "before[bold]private-middle[/bold]after"
    app, _ = runtime(tmp_path, long_secret, markup_secret, "private-canary")
    adapter = TuiConsoleAdapter(app)
    adapter.console.width = 30
    printer = adapter.console.print if direct_console else adapter.print
    parts = {
        "long": [long_secret],
        "header": ["Authorization: " + "sensitive-header-" * 12],
        "markup": [markup_secret],
        "split_ansi": ["private-\x1b[", "31mcanary\x1b[0m!"],
    }[kind]
    for part in parts:
        printer(part, end="")
        adapter.flush_to_chat()
    printer("")
    adapter.flush_to_chat()
    shown = "".join(call.args[0].text for call in app.post_message.call_args_list)
    for forbidden in ("private-", "0123456789", "sensitive-header", "private-middle"):
        assert forbidden not in shown
    assert "[REDACTED]" in shown


@pytest.mark.parametrize("kind", ["text", "panel", "table", "markdown"])
def test_console_redacts_nested_rich_renderables_without_mutating_them(tmp_path, kind):
    from rich.markdown import Markdown
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text

    secret = "nested-private-" + "0123456789" * 12
    app, _ = runtime(tmp_path, secret)
    adapter = TuiConsoleAdapter(app)
    adapter.console.width = 35
    original = Text(secret, style="bold red")
    original.stylize("italic", 3, 12)
    spans = original.spans.copy()
    table = Table("Details")
    table.add_row(Panel(original))
    renderable = {
        "text": original,
        "panel": Panel(original),
        "table": table,
        "markdown": Markdown(f"**Details**\n\n{secret}"),
    }[kind]
    adapter.console.print(renderable)
    adapter.flush_to_chat()
    shown = "".join(call.args[0].text for call in app.post_message.call_args_list)
    assert "nested-private" not in shown
    assert "0123456789" not in shown
    assert "[REDACTED]" in shown
    assert original.plain == secret
    assert original.spans == spans


def test_console_retains_safe_styles_and_masks_links(tmp_path, monkeypatch):
    from rich.text import Text

    monkeypatch.setenv("TERM", "xterm-256color")
    app, _ = runtime(tmp_path, "private-canary")
    adapter = TuiConsoleAdapter(app)
    adapter.console.print("[bold green]Safe ordinary output![/bold green]")
    adapter.flush_to_chat()
    safe = app.post_message.call_args.args[0].text
    assert "Safe ordinary output!" in safe
    assert "\x1b[" in safe
    linked = Text("Safe link", style="link https://example.test/private-canary")
    adapter.console.print(linked)
    adapter.flush_to_chat()
    assert "private-canary" not in app.post_message.call_args.args[0].text
    assert linked.style == "link https://example.test/private-canary"


@pytest.mark.parametrize("text", [
    "private-\x1b[31mcanary\x1b[0m!",
    "\x1b[31mAuthorization:\x1b[0m unknown-header-canary\nordinary next line!",
    "before[bold]private-middle[/bold]after!",
])
def test_console_streams_every_ansi_and_markup_boundary(tmp_path, text):
    for split in range(len(text) + 1):
        app, _ = runtime(tmp_path, "private-canary", "before[bold]private-middle[/bold]after")
        adapter = TuiConsoleAdapter(app)
        for part in (text[:split], text[split:]):
            adapter.console.print(part, end="")
            adapter.flush_to_chat()
        adapter.console.print("")
        adapter.flush_to_chat()
        shown = "".join(call.args[0].text for call in app.post_message.call_args_list)
        assert all(value not in shown for value in ("private-", "unknown-header-canary", "private-middle"))
        assert "[REDACTED]" in shown
        if "ordinary next line!" in text:
            assert "ordinary next line!" in shown


@pytest.mark.parametrize("kind", ["panel", "table", "markdown", "markdown_code"])
def test_console_masks_unknown_headers_in_nested_renderables(tmp_path, kind):
    from rich.markdown import Markdown
    from rich.panel import Panel
    from rich.table import Table

    app, _ = runtime(tmp_path)
    adapter = TuiConsoleAdapter(app)
    adapter.console.width = 30
    text = "Authorization: " + "unknown-header-canary-" * 12
    table = Table("Details")
    table.add_row(Panel(text))
    renderable = {
        "panel": Panel(text), "table": table,
        "markdown": Markdown(text), "markdown_code": Markdown(f"```text\n{text}\n```"),
    }[kind]
    adapter.console.print(renderable)
    adapter.flush_to_chat()
    shown = "".join(call.args[0].text for call in app.post_message.call_args_list)
    assert "unknown-header" not in shown
    assert "canary" not in shown
    assert "[REDACTED]" in shown


def test_console_marks_structured_credentials_before_pretty_rendering(tmp_path):
    app, _ = runtime(tmp_path)
    adapter = TuiConsoleAdapter(app)
    secret = "new-structured-canary-" + "1234567890" * 10
    value = {"echo": secret, "api_key": secret}
    adapter.console.print(value)
    adapter.flush_to_chat()
    shown = "".join(call.args[0].text for call in app.post_message.call_args_list)
    assert "new-structured" not in shown
    assert "1234567890" not in shown
    assert value == {"echo": secret, "api_key": secret}


def test_console_masks_pending_prefix_before_structured_output(tmp_path):
    from rich.panel import Panel

    app, _ = runtime(tmp_path, "private-canary")
    adapter = TuiConsoleAdapter(app)
    adapter.console.print("private-", end="")
    adapter.flush_to_chat()
    assert not app.post_message.called
    adapter.console.print(Panel("Ordinary output!"))
    adapter.flush_to_chat()
    shown = "".join(call.args[0].text for call in app.post_message.call_args_list)
    assert "private-" not in shown
    assert "[REDACTED]" in shown
    assert "Ordinary output!" in shown


@pytest.mark.parametrize("secret", ["[bold]", "[/bold]", "bold"])
@pytest.mark.parametrize("nested", [False, True])
def test_console_handles_redaction_that_invalidates_rich_markup(tmp_path, secret, nested):
    from rich.panel import Panel

    app, _ = runtime(tmp_path, secret)
    adapter = TuiConsoleAdapter(app)
    value = "[bold]Ordinary output![/bold]"
    adapter.console.print(Panel(value) if nested else value)
    adapter.flush_to_chat()
    shown = "".join(call.args[0].text for call in app.post_message.call_args_list)
    assert secret not in shown
    assert "Ordinary output!" in shown
