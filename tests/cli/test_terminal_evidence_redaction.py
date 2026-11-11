"""Terminal projections mask credentials without changing execution evidence."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from copy import deepcopy
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from rich.console import Console

from henchman.cli.output_handler import OutputHandler
from henchman.cli.session_manager import ReplSessionManager
from henchman.cli.stream_event_handlers import StreamState, dispatch_event
from henchman.cli.tool_executor import ToolExecutor
from henchman.cli.ui_renderer import UIRenderer
from henchman.core.events import AgentEvent, EventType
from henchman.core.session import SessionManager
from henchman.providers.base import ToolCall
from henchman.tools.base import ConfirmationRequest, ToolResult


@pytest.fixture
def runtime(tmp_path: Path) -> SimpleNamespace:
    transcript = StringIO()
    renderer = UIRenderer(console=Console(file=transcript, width=1000, highlight=False))
    provider = SimpleNamespace(api_key="configured-canary")
    sessions = ReplSessionManager(
        SessionManager(data_dir=tmp_path / "sessions"), auto_save=False, provider=provider,
    )
    sessions.set_session(sessions.create_session("project"))
    output = OutputHandler(renderer, MagicMock(), sessions, provider)
    agent = MagicMock()
    agent.identity.id = "leader"
    agent.unlimited_mode = True
    agent.messages = []
    executor = ToolExecutor(output, MagicMock(), provider)
    return SimpleNamespace(
        output=output, agent=agent, executor=executor, transcript=transcript, sessions=sessions,
    )


async def test_stream_redacts_interleaved_channels_without_changing_session_or_collection(runtime: SimpleNamespace) -> None:
    events = [
        AgentEvent(EventType.CONTENT, "Echo configured-", "leader"),
        AgentEvent(EventType.CONTENT, "other configured-", "reviewer"),
        AgentEvent(EventType.THOUGHT, "configured-", "leader"),
        AgentEvent(EventType.CONTENT, "canary! [bold]literal[/bold]", "leader"),
        AgentEvent(EventType.THOUGHT, "canary!", "leader"),
        AgentEvent(EventType.CONTENT, "canary!", "reviewer"),
        AgentEvent(EventType.FINISHED, "stop"),
    ]
    original = deepcopy(events)

    async def stream() -> AsyncIterator[AgentEvent]:
        for event in events:
            yield event

    collected = []
    await runtime.executor.process_agent_stream(stream(), runtime.agent, collected)

    rendered = runtime.transcript.getvalue()
    assert "configured-" not in rendered
    assert rendered.count("[REDACTED]") == 3
    assert "[bold]literal[/bold]" in rendered
    assert "".join(collected) == "Echo configured-canary! [bold]literal[/bold]"
    assert events == original
    assert runtime.sessions.current.messages[-1].content == "".join(collected)


@pytest.mark.parametrize("ending", ["error", "exception", "cancel"])
async def test_interruption_flushes_prefix_before_error_and_preserves_raw_content(runtime: SimpleNamespace, ending: str) -> None:
    closed = []

    async def stream() -> AsyncIterator[AgentEvent]:
        try:
            yield AgentEvent(EventType.CONTENT, "prefix configured-", "leader")
            if ending == "error":
                yield AgentEvent(EventType.ERROR, "failed configured-canary", "leader")
            elif ending == "exception":
                raise RuntimeError("provider interrupted")
            else:
                raise asyncio.CancelledError()
        finally:
            closed.append(True)

    collected = []
    if ending == "error":
        await runtime.executor.process_agent_stream(stream(), runtime.agent, collected)
    else:
        with pytest.raises(RuntimeError if ending == "exception" else asyncio.CancelledError):
            await runtime.executor.process_agent_stream(stream(), runtime.agent, collected)
    rendered = runtime.transcript.getvalue()
    assert "configured-" not in rendered
    assert "prefix [REDACTED]" in rendered
    if ending == "error":
        assert rendered.index("prefix [REDACTED]") < rendered.index("failed")
    assert collected == ["prefix configured-"]
    assert closed == [True]
    assert runtime.sessions.current.messages[-1].content == "prefix configured-"


def test_completion_flushes_other_channels_and_rotation_uses_session_registry(runtime: SimpleNamespace) -> None:
    state = StreamState()
    policy = runtime.sessions.session_manager.evidence_redactor
    dispatch_event(runtime.output, AgentEvent(EventType.CONTENT, "configured-", "worker"), state, runtime.agent, None)
    policy.register_secret("rotated-canary")
    dispatch_event(runtime.output, AgentEvent(EventType.CONTENT, "canary rotated-canary", "worker"), state, runtime.agent, None)
    dispatch_event(runtime.output, AgentEvent(EventType.THOUGHT, "configured-", "worker"), state, runtime.agent, None)
    dispatch_event(runtime.output, AgentEvent(EventType.AGENT_COMPLETED, {
        "agent": "leader", "scope": "run", "status": "failed",
    }, "orchestrator"), state, runtime.agent, None)
    rendered = runtime.transcript.getvalue()
    assert "configured-" not in rendered and "rotated-canary" not in rendered
    assert rendered.count("[REDACTED]") == 3
    assert rendered.rfind("[REDACTED]") < rendered.index("failed")


async def test_tool_display_redacts_marked_args_before_escape_and_preview(runtime: SimpleNamespace) -> None:
    secret = "marked-[bold]-canary"
    call = ToolCall("call", "echo", {"api_key": secret, "payload": secret})
    raw_result = "=" * 192 + secret
    result = ToolResult(raw_result)
    runtime.agent.tool_registry.execute = AsyncMock(return_value=result)

    await runtime.executor._execute_and_record_tool_call(call, runtime.agent, set())

    rendered = runtime.transcript.getvalue()
    assert "marked-" not in rendered
    assert "[REDACTED]" in rendered
    runtime.agent.tool_registry.execute.assert_awaited_once_with("echo", call.arguments)
    runtime.agent.submit_tool_result.assert_called_once_with("call", result)
    assert call.arguments["api_key"] == secret
    assert result.content == raw_result
    assert runtime.sessions.current.messages[-1].content == raw_result


def test_event_tool_requests_results_and_routing_are_safe_but_raw_records_survive(runtime: SimpleNamespace) -> None:
    secret = "marked-[bold]-canary"
    call = ToolCall("call", "echo", {"password": secret})
    state = StreamState()
    events = [
        AgentEvent(EventType.TOOL_CALL_REQUEST, call, "leader"),
        AgentEvent(EventType.TOOL_CALL_RESULT, {"tool_call_id": "call", "result": "=" * 192 + secret, "success": False}, "leader"),
        AgentEvent(EventType.AGENT_DELEGATED, {"from": "leader", "to": "reviewer", "task": secret}),
        AgentEvent(EventType.AGENT_MESSAGE, {"to": "leader", "message": secret}),
        AgentEvent(EventType.ERROR, {"password": secret, "message": secret}),
    ]
    original = deepcopy(events)
    for event in events:
        dispatch_event(runtime.output, event, state, runtime.agent, None)
    assert "marked-" not in runtime.transcript.getvalue()
    assert events == original
    assert state.pending_tool_calls[0] is call
    assert runtime.sessions.current.messages[0].tool_calls[0]["arguments"]["password"] == secret
    assert runtime.sessions.current.messages[1].content.endswith(secret)


@pytest.mark.parametrize("tool_name", ["shell", "write_file", "edit_file", "custom"])
@pytest.mark.parametrize("approved", [False, True])
async def test_confirmation_redacts_display_and_preserves_params_and_decision(
    runtime: SimpleNamespace, tool_name: str, approved: bool,
) -> None:
    secret = "marked-[bold]-canary"
    params = {"password": secret, "command": f"echo {secret}", "path": f"/tmp/{secret}"}
    request = ConfirmationRequest(tool_name, f"Use {secret}", params)
    runtime.output.renderer.confirm_tool_execution = AsyncMock(return_value=approved)

    assert await runtime.executor.handle_confirmation(request) is approved

    prompt = runtime.output.renderer.confirm_tool_execution.call_args.args[0]
    assert "marked-" not in prompt
    assert "[REDACTED]" in prompt
    assert request.params is params
    assert params["password"] == secret
    runtime.output.renderer.confirm_tool_execution.assert_awaited_once()


@pytest.mark.parametrize("short_secret", ["tool_name", "description", "params", "command", "path"])
async def test_confirmation_keeps_fixed_fields_when_credentials_match_their_names(
    runtime: SimpleNamespace, short_secret: str,
) -> None:
    runtime.sessions.session_manager.evidence_redactor.register_secret(short_secret)
    runtime.output.renderer.confirm_tool_execution = AsyncMock(return_value=False)
    request = ConfirmationRequest("write_file", "Create file", {"path": "/tmp/public.txt"})

    assert await runtime.executor.handle_confirmation(request) is False

    prompt = runtime.output.renderer.confirm_tool_execution.call_args.args[0]
    assert "/tmp/public.txt" in prompt


async def test_generic_confirmation_does_not_preserve_dynamic_argument_names(runtime: SimpleNamespace) -> None:
    runtime.sessions.session_manager.evidence_redactor.register_secret("path")
    runtime.output.renderer.confirm_tool_execution = AsyncMock(return_value=True)
    request = ConfirmationRequest("custom", "Run tool", {"path": "public"})

    await runtime.executor.handle_confirmation(request)

    prompt = runtime.output.renderer.confirm_tool_execution.call_args.args[0]
    assert '"path"' not in prompt
    assert "[REDACTED]" in prompt


async def test_full_tool_batch_registers_later_credentials_before_earlier_results(runtime: SimpleNamespace) -> None:
    secret = "later-marked-canary"
    calls = [ToolCall("one", "echo", {}), ToolCall("two", "echo", {"password": secret})]
    runtime.agent.tool_registry.execute = AsyncMock(side_effect=[ToolResult(secret), ToolResult("Done")])
    runtime.executor._split_tools_by_confirmation_requirement = MagicMock(return_value=([], calls))
    runtime.output.show_turn_status = MagicMock()

    async def continuation() -> AsyncIterator[AgentEvent]:
        yield AgentEvent(EventType.FINISHED, "stop")

    runtime.agent.continue_with_tool_results = continuation
    await runtime.executor.execute_tool_calls(calls, runtime.agent)

    assert secret not in runtime.transcript.getvalue()
    assert runtime.agent.submit_tool_result.call_args_list[0].args == ("one", ToolResult(secret))
    assert calls[1].arguments["password"] == secret


@pytest.mark.parametrize("channel", [EventType.CONTENT, EventType.THOUGHT])
def test_auth_headers_across_every_terminal_chunk_boundary(runtime: SimpleNamespace, channel: EventType) -> None:
    text = "Before\n Authorization\u00a0: Bearer unknown-header-canary\r\nAfter!"
    for cut in range(len(text) + 1):
        runtime.transcript.seek(0)
        runtime.transcript.truncate()
        state = StreamState()
        for chunk in (text[:cut], text[cut:]):
            dispatch_event(runtime.output, AgentEvent(channel, chunk, "leader"), state, runtime.agent, None)
        dispatch_event(runtime.output, AgentEvent(EventType.FINISHED, "stop", "leader"), state, runtime.agent, None)
        rendered = runtime.transcript.getvalue()
        assert "unknown-header-canary" not in rendered
        assert "[REDACTED]" in rendered
        assert "Before" in rendered and "After!" in rendered
