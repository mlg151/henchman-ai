"""JSON rendering projects private evidence without changing execution events."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from henchman.cli.json_output import JsonOutputRenderer
from henchman.core.events import AgentEvent, EventType
from henchman.providers.base import ToolCall
from henchman.utils.evidence_redaction import EvidenceRedactor


@pytest.mark.parametrize("batch", [False, True])
def test_split_credentials_and_interleaved_agents_are_masked(batch: bool) -> None:
    console = MagicMock()
    renderer = JsonOutputRenderer(console, redactor=EvidenceRedactor(["private-canary"]))
    events = [
        AgentEvent(EventType.CONTENT, "Echo private-", source_agent="leader"),
        AgentEvent(EventType.CONTENT, "ordinary!", source_agent="reviewer"),
        AgentEvent(EventType.THOUGHT, "private-", source_agent="leader"),
        AgentEvent(EventType.CONTENT, "canary!", source_agent="leader"),
        AgentEvent(EventType.THOUGHT, "canary!", source_agent="leader"),
        AgentEvent(EventType.FINISHED),
    ]
    if batch:
        renderer.render_final_json(events)
        output = json.loads(console.print.call_args.args[0])
    else:
        for event in events:
            renderer.render(event)
        output = [json.loads(call.args[0]) for call in console.print.call_args_list]
    content = "".join(item.get("data", "") for item in output if item["type"] == "content" and item["source_agent"] == "leader")
    thought = "".join(item.get("data", "") for item in output if item["type"] == "thought")
    assert content == "Echo [REDACTED]!"
    assert thought == "[REDACTED]!"
    assert events[0].data == "Echo private-"
    assert events[3].data == "canary!"


def test_marked_arguments_register_echoes_without_mutating_executable_call() -> None:
    console = MagicMock()
    renderer = JsonOutputRenderer(console, redactor=EvidenceRedactor(["id"]))
    call = ToolCall(id="id", name="read_file", arguments={"api_key": "marked-canary", "path": "example"})
    renderer.render(AgentEvent(EventType.TOOL_CALL_REQUEST, call, source_agent="id"))
    renderer.render(AgentEvent(EventType.TOOL_CALL_RESULT, {
        "tool_call_id": "id", "result": "marked-canary", "success": False,
    }, source_agent="id"))
    output = [json.loads(item.args[0]) for item in console.print.call_args_list]
    assert output[0]["data"]["id"] == "id"
    assert output[0]["source_agent"] == "id"
    assert output[0]["data"]["arguments"]["api_key"] == "[REDACTED]"
    assert output[1]["data"]["result"] == "[REDACTED]"
    assert output[1]["data"]["tool_call_id"] == "id"
    assert call.arguments["api_key"] == "marked-canary"


def test_flush_masks_partial_credentials_after_interruption() -> None:
    console = MagicMock()
    renderer = JsonOutputRenderer(console, redactor=EvidenceRedactor(["private-canary"]))
    renderer.render(AgentEvent(EventType.CONTENT, "prefix private-", source_agent="leader"))
    renderer.flush()
    renderer.flush()
    output = [json.loads(item.args[0]) for item in console.print.call_args_list]
    assert "".join(event["data"] for event in output) == "prefix [REDACTED]"
    assert all(event["source_agent"] == "leader" for event in output)


def test_complete_json_collects_marked_fields_before_rendering_earlier_echoes() -> None:
    console = MagicMock()
    renderer = JsonOutputRenderer(console)
    renderer.render_final_json([
        AgentEvent(EventType.CONTENT, "Echo marked-canary!"),
        AgentEvent(EventType.ERROR, {"secret": "marked-canary", "message": "marked-canary"}),
    ])
    assert "marked-canary" not in console.print.call_args.args[0]


@pytest.mark.parametrize("batch", [False, True])
def test_terminal_orchestrator_failure_flushes_every_agent_before_finished(batch: bool) -> None:
    console = MagicMock()
    renderer = JsonOutputRenderer(console, redactor=EvidenceRedactor(["private-canary"]))
    events = [
        AgentEvent(EventType.CONTENT, "prefix private-", source_agent="worker"),
        AgentEvent(EventType.FINISHED, {"finish_reason": "error"}, source_agent="orchestrator"),
    ]
    if batch:
        renderer.render_final_json(events)
        output = json.loads(console.print.call_args.args[0])
    else:
        for event in events:
            renderer.render(event)
        renderer.flush()
        output = [json.loads(item.args[0]) for item in console.print.call_args_list]
    assert output[-1]["type"] == "finished"
    assert "".join(item["data"] for item in output[:-1]) == "prefix [REDACTED]"


def test_error_name_is_evidence_not_a_protocol_identity() -> None:
    console = MagicMock()
    renderer = JsonOutputRenderer(console, redactor=EvidenceRedactor(["private-canary"]))
    renderer.render(AgentEvent(EventType.ERROR, {"name": "private-canary"}))
    assert "private-canary" not in console.print.call_args.args[0]


def test_tool_preview_is_derived_after_redaction() -> None:
    from henchman.agents.orchestrator_events import create_tool_result_event

    console = MagicMock()
    renderer = JsonOutputRenderer(console, redactor=EvidenceRedactor(["private-canary"]))
    result = "=" * 492 + "private-canary"
    agent = MagicMock()
    agent.identity.id = "worker"
    call = ToolCall(id="call", name="tool", arguments={})
    event = create_tool_result_event(agent, call, result)
    renderer.render(event)
    data = json.loads(console.print.call_args.args[0])["data"]
    assert "private-" not in data["preview"]
    assert "private-canary" not in data["result"]
    assert event.data["result"] == result


def test_validated_completion_controls_keep_meaning_with_short_credentials() -> None:
    console = MagicMock()
    renderer = JsonOutputRenderer(console, redactor=EvidenceRedactor(["stop", "completed", "run"]))
    data = {"finish_reason": "stop", "status": "completed", "scope": "run", "message": "completed run"}
    renderer.render(AgentEvent(EventType.FINISHED, data))
    output = json.loads(console.print.call_args.args[0])["data"]
    assert {key: output[key] for key in ("finish_reason", "status", "scope")} == {
        "finish_reason": "stop", "status": "completed", "scope": "run",
    }
    assert output["message"] == "[REDACTED] [REDACTED]"


def test_scalar_finished_reason_preserves_validated_protocol_value() -> None:
    console = MagicMock()
    renderer = JsonOutputRenderer(console, redactor=EvidenceRedactor(["stop"]))
    renderer.render(AgentEvent(EventType.FINISHED, "stop"))
    assert json.loads(console.print.call_args.args[0])["data"] == "stop"


async def test_json_initialization_reuses_session_credential_registry(tmp_path, monkeypatch) -> None:
    from henchman.cli import app
    from henchman.cli.session_manager import ReplSessionManager
    from henchman.core.session_manager import SessionManager

    policy = EvidenceRedactor(["configured-canary"])
    sessions = ReplSessionManager(SessionManager(data_dir=tmp_path, evidence_redactor=policy))
    repl = SimpleNamespace(session_manager=sessions, initialize_mcp=AsyncMock(), rag_system=None)
    console = MagicMock()
    monkeypatch.setattr(app, "console", console)
    renderer = await app._initialize_json_processing(repl)
    assert renderer.evidence.redactor is policy
    renderer.render(AgentEvent(EventType.CONTENT, "configured-canary!"))
    policy.register_secret("rotated-canary")
    renderer.render(AgentEvent(EventType.CONTENT, "rotated-canary!"))
    assert all("canary" not in call.args[0] for call in console.print.call_args_list)


async def test_json_cancellation_flushes_pending_secret_and_closes_runtime(monkeypatch) -> None:
    import asyncio

    from henchman.cli import app

    console = MagicMock()
    renderer = JsonOutputRenderer(console, redactor=EvidenceRedactor(["private-canary"]))
    closed = AsyncMock()

    async def cancel(_repl, _prompt, render, _role):
        render(AgentEvent(EventType.CONTENT, "prefix private-", source_agent="worker"))
        raise asyncio.CancelledError

    monkeypatch.setattr(app, "_initialize_json_processing", AsyncMock(return_value=renderer))
    monkeypatch.setattr(app, "_run_headless_json_mode", cancel)
    monkeypatch.setattr(app, "_close_headless_repl", closed)
    repl = object()
    with pytest.raises(asyncio.CancelledError):
        await app._run_headless_json_format(repl, "task", "stream-json")
    closed.assert_awaited_once_with(repl)
    output = [json.loads(call.args[0]) for call in console.print.call_args_list]
    assert "".join(event["data"] for event in output) == "prefix [REDACTED]"
    assert not any(event["type"] == "finished" for event in output)
