"""Mounted presentation modes retain literal content and inspectable evidence."""

import asyncio
from copy import deepcopy

import pytest
from rich.markdown import Markdown
from rich.text import Text

from henchman.cli.evidence import runtime_evidence_redactor
from henchman.cli.textual_bridge import TuiConsoleAdapter
from henchman.cli.textual_config import ComponentConfig, ComponentInitializer
from henchman.cli.textual_messages import CommandOutputMessage
from henchman.cli.textual_widgets import (
    ChatMessage,
    ChatPane,
    HenchmanTextArea,
    ThinkingMessage,
    ToolMessage,
)
from henchman.config.runtime import RuntimeSettingsState
from henchman.config.schema import Settings
from henchman.core.events import AgentEvent, EventType
from henchman.tools.base import ConfirmationRequest
from tests.cli.test_textual_density_settings import DensityApp
from tests.cli.test_textual_tool_activity import request, result, send
from tests.cli.ui_scenarios import populate_history, settle_layout

MODES = ("rich", "plain", "quiet")
LITERAL = "# Exact heading\n[bold]literal[/bold] :smile:\n```python\nx = 1\n```\n[link](https://example.invalid/path)"


@pytest.fixture(autouse=True)
def isolated_project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


@pytest.mark.parametrize("mode", MODES)
async def test_streamed_answers_and_explicit_commands_keep_literal_plain_content(tmp_path, mode):
    app = DensityApp(tmp_path, Settings(ui={"output_mode": mode}))
    async with app.run_test() as pilot:
        await send(
            app, [AgentEvent(EventType.CONTENT, LITERAL), AgentEvent(EventType.FINISHED, None)]
        )
        app.post_message(CommandOutputMessage("Explicit [bold]brackets[/bold] :smile: `code`"))
        await settle_layout(pilot)
        messages = list(app.query(ChatMessage))
        answer = next(message for message in messages if message._content_text == LITERAL)
        if mode == "rich":
            assert isinstance(answer.renderable, Markdown)
        else:
            assert isinstance(answer.renderable, Text)
            assert LITERAL in answer.renderable.plain
            command = next(
                message for message in messages if message._content_text.startswith("Explicit")
            )
            assert "[bold]brackets[/bold] :smile: `code`" in command.renderable.plain
            assert answer.renderable.spans == []
        assert answer._content_text == LITERAL


@pytest.mark.parametrize("mode", MODES)
async def test_quiet_projects_routine_events_without_dropping_tool_evidence(tmp_path, mode):
    app = DensityApp(tmp_path, Settings(ui={"output_mode": mode, "detail_density": "detailed"}))
    events = [
        AgentEvent(EventType.THOUGHT, "Routine reasoning"),
        AgentEvent(
            EventType.AGENT_DELEGATED,
            {"from": "leader", "to": "worker", "reason": "Routine delegation"},
        ),
        request(identity="success", path="a.py"),
        result(identity="success", success=True, result="Routine successful detail"),
        request(identity="failure", path="b.py"),
        result(identity="failure", success=False, result="Critical failed detail"),
        request(identity="unknown", path="c.py"),
        result(identity="unknown", result="Critical unknown detail"),
        request(identity="interrupted", path="d.py"),
        AgentEvent(EventType.CONTENT, "Visible final answer"),
    ]
    original = deepcopy(events)
    async with app.run_test() as pilot:
        await send(app, events)
        await settle_layout(pilot)
        thought = app.query_one(ThinkingMessage)
        delegation = next(
            message
            for message in app.query(ChatMessage)
            if "Routine delegation" in message._content_text
        )
        assert thought.display is (mode != "quiet")
        assert delegation.display is (mode != "quiet")
        assert thought._content_text == "Routine reasoning"
        cards = list(app.query(ToolMessage))
        assert len(cards) == 4 and all(card.display for card in cards)
        assert cards[0].content.display is (mode != "quiet")
        policy = runtime_evidence_redactor(app)
        for card, label, detail in zip(
            cards,
            ("Succeeded", "Failed", "Unknown", "Interrupted"),
            (
                "Routine successful detail",
                "Critical failed detail",
                "Critical unknown detail",
                "effects may have occurred",
            ),
            strict=True,
        ):
            assert label in str(card.header.render())
            assert detail in card.activity.evidence(policy)
        assert all(card.content.display for card in cards[1:])
        assert events == original


async def test_mode_is_captured_at_launch_and_adapter_emits_no_ansi_for_plain(tmp_path):
    state = RuntimeSettingsState.from_settings(Settings())
    app = DensityApp(tmp_path, state.settings, state=state)
    state.update({"ui": {"output_mode": "plain"}})
    async with app.run_test() as pilot:
        state.update({"ui": {"output_mode": "rich"}})
        adapter = TuiConsoleAdapter(app)
        adapter.print(Text("Literal [bold] :smile:", style="bold red"))
        await send(
            app, [AgentEvent(EventType.CONTENT, LITERAL), AgentEvent(EventType.FINISHED, None)]
        )
        await settle_layout(pilot)
        assert not adapter.console.is_terminal
        messages = list(app.query(ChatMessage))
        assert all("\x1b" not in message._content_text for message in messages)
        answer = next(message for message in messages if message._content_text == LITERAL)
        assert isinstance(answer.renderable, Text)
        assert LITERAL in answer.renderable.plain
        assert app.query_one(ChatPane).follow_live


@pytest.mark.parametrize("mode", ["plain", "quiet"])
async def test_actual_command_renderer_keeps_projection_before_layout_and_literal_content(
    tmp_path, mode
):
    app = DensityApp(tmp_path, Settings(ui={"output_mode": mode}))
    secret = "retained-output-canary-" + "x" * 100
    async with app.run_test() as pilot:
        policy = runtime_evidence_redactor(app)
        policy.register_secret(secret)
        initializer = ComponentInitializer(
            ComponentConfig(
                provider=app.provider,
                config=app.config,
                settings=app.settings,
                environment_context=None,
                app=app,
            )
        )
        initializer._initialize_tui_adapter()
        initializer._initialize_renderer()
        renderer, adapter = initializer._ui_renderer, initializer._tui_adapter
        assert renderer.output_mode == mode
        assert renderer.console is adapter.console
        long_line = "literal[brackets] :smile: `code` " * 12
        renderer.markdown(LITERAL + "\n" + secret)
        renderer.markdown(long_line)
        renderer.code("x = '[bold]literal[/bold]' # :smile:\n")
        renderer.warning("Explicit warning stays")
        renderer.error("Explicit failure stays")
        renderer.success("Explicit command success stays")
        adapter.flush_to_chat()
        await settle_layout(pilot)
        messages = list(app.query(ChatMessage))
        raw = "\n".join(message._content_text for message in messages)
        displayed = "\n".join(message.renderable.plain for message in messages)
        for text in (
            LITERAL,
            "x = '[bold]literal[/bold]' # :smile:",
            "Explicit warning stays",
            "Explicit failure stays",
            "Explicit command success stays",
        ):
            assert text in raw and text in displayed
        assert secret not in raw and "retained-output-canary" not in displayed
        assert "[REDACTED]" in displayed and "\x1b" not in displayed
        assert long_line.rstrip() in raw and long_line.rstrip() in displayed


async def test_quiet_manual_tool_choice_and_reading_position_survive_results(tmp_path):
    app = DensityApp(tmp_path, Settings(ui={"output_mode": "quiet", "detail_density": "detailed"}))
    async with app.run_test(size=(120, 40)) as pilot:
        chat = app.query_one(ChatPane)
        populate_history(chat)
        chat.begin_agent_stream("earlier")
        # Keep a single stream open while explicitly inspecting the pending row.
        from henchman.cli.textual_messages import ToolCallRequestMessage, ToolCallResultMessage
        from henchman.providers.base import ToolCall

        app.post_message(
            ToolCallRequestMessage(
                ToolCall("one", "read_file", {"path": "a.py"}), stream_id="owned"
            )
        )
        await settle_layout(pilot)
        card = app.query_one(ToolMessage)
        assert not card.content.display
        populate_history(chat)
        card.focus()
        await pilot.press("space")
        await settle_layout(pilot)
        assert card.content.display
        scrolled = asyncio.Event()
        card.scroll_visible(top=True, animate=False, on_complete=scrolled.set)
        await asyncio.wait_for(scrolled.wait(), 5)
        await settle_layout(pilot)
        offset = card.region.y - chat.content_region.y
        composer = app.query_one(HenchmanTextArea)
        composer.load_text("Keep\nmy draft")
        composer.focus()
        chat.append_agent_chunk("earlier", "Earlier content\n" * 5)
        app.post_message(
            ToolCallResultMessage(
                {
                    "tool_call_id": "one",
                    "tool_name": "read_file",
                    "success": True,
                    "result": "Explicit inspection [bold] :smile:",
                },
                stream_id="owned",
            )
        )
        await settle_layout(pilot)
        await pilot.resize_terminal(80, 24)
        await settle_layout(pilot)
        assert card.content.display
        assert card.region.y - chat.content_region.y == offset
        assert not chat.follow_live and chat.new_activity
        assert "Explicit inspection [bold] :smile:" in card.content.render().plain
        assert composer.text == "Keep\nmy draft" and app.focused is composer


@pytest.mark.parametrize("mode", ["plain", "quiet"])
async def test_approval_stays_pending_and_draft_focus_survive_critical_events(tmp_path, mode):
    app = DensityApp(tmp_path, Settings(ui={"output_mode": mode}))
    async with app.run_test() as pilot:
        composer = app.query_one(HenchmanTextArea)
        composer.load_text("Keep\nthis approval draft")
        approval = asyncio.create_task(
            app._textual_confirm(
                ConfirmationRequest(
                    "write_file",
                    "Write only the proposed file",
                    params={"path": "a.py"},
                )
            )
        )
        try:
            await settle_layout(pilot)
            decision, focus = app.screen, app.focused
            await send(
                app,
                [
                    request(path="a.py"),
                    result(success=False, result="Failure stays visible"),
                    AgentEvent(EventType.ERROR, "Cancellation cleanup incomplete"),
                ],
            )
            await settle_layout(pilot)
            assert not approval.done() and app.screen is decision and app.focused is focus
            assert "Failed" in str(app.query_one(ToolMessage).header.render())
            assert any(
                "Cancellation cleanup incomplete" in row._content_text
                for row in app.query(ChatMessage)
            )
            await pilot.press("n")
            assert await approval is False
        finally:
            if not approval.done():
                approval.cancel()
                await asyncio.gather(approval, return_exceptions=True)
        await settle_layout(pilot)
        assert app.focused is composer and composer.text == "Keep\nthis approval draft"


@pytest.mark.parametrize("mode", ["plain", "quiet"])
async def test_runtime_notices_keep_literal_payloads_without_style_syntax(tmp_path, mode):
    app = DensityApp(tmp_path, Settings(ui={"output_mode": mode}))
    payload = "Preserve [bold]literal[/bold] :smile: `criteria`"
    async with app.run_test() as pilot:
        await send(
            app,
            [
                AgentEvent(
                    EventType.AGENT_DELEGATED, {"from": "leader", "to": "worker", "reason": payload}
                ),
                AgentEvent(EventType.AGENT_MESSAGE, payload),
                AgentEvent(EventType.CONTEXT_COMPACTED, {}),
            ],
        )
        await settle_layout(pilot)
        rows = list(app.query(ChatMessage))
        assert all(
            "[dim]" not in row.renderable.plain and "[/dim]" not in row.renderable.plain
            for row in rows
        )
        assert any(payload in row.renderable.plain and row.display for row in rows)
        assert any(
            "Context window was compacted" in row.renderable.plain and row.display for row in rows
        )


async def test_quiet_manual_collapse_survives_critical_result_refresh_and_redaction(tmp_path):
    from henchman.cli.textual_messages import ToolCallRequestMessage, ToolCallResultMessage
    from henchman.providers.base import ToolCall

    app = DensityApp(tmp_path, Settings(ui={"output_mode": "quiet"}))
    secret = "newly-known-result-canary"
    async with app.run_test() as pilot:
        app.post_message(
            ToolCallRequestMessage(
                ToolCall("one", "read_file", {"path": "a.py"}), stream_id="owned"
            )
        )
        app.post_message(
            ToolCallResultMessage(
                {
                    "tool_call_id": "one",
                    "tool_name": "read_file",
                    "success": False,
                    "result": secret,
                },
                stream_id="owned",
            )
        )
        await settle_layout(pilot)
        card = app.query_one(ToolMessage)
        assert card.content.display and "Failed" in str(card.header.render())
        card.focus()
        await pilot.press("space")
        await settle_layout(pilot)
        assert not card.content.display
        runtime_evidence_redactor(app).register_secret(secret)
        app.query_one(ChatPane).refresh_tool_activity()
        await settle_layout(pilot)
        assert not card.content.display and "Failed" in str(card.header.render())
        assert secret not in card.content.render().plain
        assert "[REDACTED]" in card.content.render().plain
        await pilot.press("space")
        await settle_layout(pilot)
        assert card.content.display


@pytest.mark.parametrize("mode", ["plain", "quiet"])
async def test_startup_welcome_preserves_literal_provider_and_model_identity(tmp_path, mode):
    from henchman.cli.textual_mixins import _ContextTreeMixin

    class WelcomeApp(DensityApp):
        def _show_welcome(self):
            _ContextTreeMixin._show_welcome(self)

    app = WelcomeApp(tmp_path, Settings(ui={"output_mode": mode}))
    provider_name = "fixture[bold]provider[/bold]"
    model_name = "fixture[bold]variant[/bold] :smile: `model`"
    app.provider._name = provider_name
    app.provider.default_model = model_name
    async with app.run_test() as pilot:
        await settle_layout(pilot)
        banner = next(row for row in app.query(ChatMessage) if "Henchman-AI" in row._content_text)
        assert provider_name in banner.renderable.plain
        assert model_name in banner.renderable.plain
        assert banner.display is (mode != "quiet")
        assert banner.renderable.spans == []
