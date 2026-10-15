"""Offline model transport, real adapters, tools, edits, and test subprocesses."""

import copy
import io
import json
import os
import shlex
import subprocess
import sys
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from anthropic.types import (
    RawContentBlockDeltaEvent,
    RawContentBlockStartEvent,
    RawContentBlockStopEvent,
    RawMessageDeltaEvent,
    RawMessageStopEvent,
)
from openai.types.chat import ChatCompletionChunk
from rich.console import Console
from tests.providers.stream_helpers import SDKResponse

from henchman.cli import app
from henchman.cli.json_output import event_to_dict
from henchman.config.schema import ProviderSettings
from henchman.core.agent import Agent, AgentConfig
from henchman.core.events import EventType
from henchman.providers.factory import create_configured_provider
from henchman.tools.builtins.file_edit import EditFileTool
from henchman.tools.builtins.file_read import ReadFileTool
from henchman.tools.builtins.shell import ShellTool
from henchman.tools.registry import ToolRegistry


def compatible_response(call):
    """Create SDK wire chunks including fragmented function arguments."""

    def chunk(delta, finish=None):
        return ChatCompletionChunk.model_validate(
            {
                "id": "completion",
                "object": "chat.completion.chunk",
                "created": 1,
                "model": "coding-test",
                "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
            }
        )

    async def chunks():
        if call is None:
            yield chunk({"content": "Fixed the addition bug; pytest now passes."}, "stop")
            return
        arguments = json.dumps(call[2])
        yield chunk(
            {
                "tool_calls": [
                    {
                        "index": 0,
                        "id": call[0],
                        "type": "function",
                        "function": {"name": call[1], "arguments": arguments[:8]},
                    }
                ]
            }
        )
        yield chunk({"tool_calls": [{"index": 0, "function": {"arguments": arguments[8:]}}]})
        yield chunk({}, "tool_calls")

    return SDKResponse(chunks())


@asynccontextmanager
async def anthropic_response(call):
    """Create native Anthropic tool-use/text events, without replacing the adapter."""

    async def chunks():
        block = (
            {"type": "tool_use", "id": call[0], "name": call[1], "input": {}}
            if call
            else {"type": "text", "text": ""}
        )
        yield RawContentBlockStartEvent.model_validate(
            {
                "type": "content_block_start",
                "index": 0,
                "content_block": block,
            }
        )
        delta = (
            {"type": "input_json_delta", "partial_json": json.dumps(call[2])}
            if call
            else {"type": "text_delta", "text": "Fixed the addition bug; pytest now passes."}
        )
        yield RawContentBlockDeltaEvent.model_validate(
            {
                "type": "content_block_delta",
                "index": 0,
                "delta": delta,
            }
        )
        yield RawContentBlockStopEvent(type="content_block_stop", index=0)
        yield RawMessageDeltaEvent.model_validate(
            {
                "type": "message_delta",
                "delta": {"stop_reason": "tool_use" if call else "end_turn", "stop_sequence": None},
                "usage": {"output_tokens": 10},
            }
        )
        yield RawMessageStopEvent(type="message_stop")

    yield chunks()


@pytest.mark.parametrize(
    "provider_name", ["openrouter", "openai_compat", "deepseek", "ollama", "anthropic"]
)
@pytest.mark.parametrize("output_mode", ["events", "json-complete"])
async def test_real_coding_loop_recovers_from_failed_test_and_edit(
    tmp_path,
    monkeypatch,
    provider_name,
    output_mode,
):
    """Read, fail, recover from a bad edit, edit correctly, verify, and finish."""
    source = tmp_path / "arithmetic.py"
    source.write_bytes(b"def add(a, b):\n    return a - b\n")
    (tmp_path / "test_arithmetic.py").write_bytes(
        b"from arithmetic import add\n\ndef test_add():\n    assert add(2, 3) == 5\n"
    )
    # Disable ambient plugins only inside the scratch test subprocess.
    monkeypatch.setenv("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
    # Scripted model replies can edit within the same timestamp second. The
    # same-size +/- edit would otherwise reuse Python's stale timestamp pyc.
    monkeypatch.setenv("PYTHONDONTWRITEBYTECODE", "1")
    pytest_argv = [sys.executable, "-m", "pytest", "-q", "test_arithmetic.py"]
    pytest_command = (
        subprocess.list2cmdline(pytest_argv) if os.name == "nt" else shlex.join(pytest_argv)
    )
    script = [
        ("read", "read_file", {"path": str(source)}),
        (
            "test-fail",
            "shell",
            {"command": pytest_command, "cwd": str(tmp_path), "timeout": 20, "background": False},
        ),
        (
            "bad-edit",
            "edit_file",
            {"path": str(source), "old_str": "return a / b", "new_str": "return a + b"},
        ),
        (
            "fix",
            "edit_file",
            {"path": str(source), "old_str": "return a - b", "new_str": "return a + b"},
        ),
        (
            "test-pass",
            "shell",
            {"command": pytest_command, "cwd": str(tmp_path), "timeout": 20, "background": False},
        ),
        None,
    ]
    saved = {"api_key": "offline-test", "model": "coding-test"}
    if provider_name == "openai_compat":
        saved["base_url"] = "https://offline.invalid/v1"
    if provider_name == "ollama":
        saved.pop("api_key")
    provider = create_configured_provider(
        ProviderSettings(
            default=provider_name,
            **{provider_name: saved},
        )
    )
    requests = []

    def next_response(**kwargs):
        requests.append(copy.deepcopy(kwargs))
        assert len(requests) <= len(script), "Unexpected extra model request"
        call = script[len(requests) - 1]
        return (
            anthropic_response(call) if provider_name == "anthropic" else compatible_response(call)
        )

    if provider_name == "anthropic":
        monkeypatch.setattr(provider._client.messages, "stream", next_response)
    else:
        monkeypatch.setattr(
            provider._client.chat.completions, "create", AsyncMock(side_effect=next_response)
        )

    registry = ToolRegistry()
    for tool in (ReadFileTool(), EditFileTool(), ShellTool()):
        registry.register(tool)
    confirmations = []

    async def approve(request):
        confirmations.append(request.tool_name)
        return True

    registry.set_confirmation_handler(approve)
    agent = Agent(
        provider=provider, tool_registry=registry, config=AgentConfig(base_tool_iterations=6)
    )
    repl = SimpleNamespace(
        agent=agent, tool_registry=registry, initialize_mcp=AsyncMock(), rag_system=None
    )
    try:
        if output_mode == "json-complete":
            output = io.StringIO()
            monkeypatch.setattr(
                app, "console", Console(file=output, width=10000, highlight=False, markup=False)
            )
            await app._run_headless_json_complete(repl, "Fix addition and verify the tests")
            events = json.loads(output.getvalue())
        else:
            raw_events = []
            assert await app._run_headless_json_mode(
                repl, "Fix addition and verify the tests", raw_events.append
            )
            events = [event_to_dict(event) for event in raw_events]
    finally:
        await provider._client.close()

    assert source.read_bytes() == b"def add(a, b):\n    return a + b\n"
    assert len(requests) == 6
    assert confirmations == ["shell", "edit_file", "edit_file", "shell"]
    results = [event["data"] for event in events if event["type"] == "tool_call_result"]
    assert [result["tool_call_id"] for result in results] == [call[0] for call in script[:-1]]
    assert [result["success"] for result in results] == [True, False, False, True, True], results
    assert "1 failed" in results[1]["result"]
    assert "1 passed" in results[4]["result"]
    # Each adapter must send the real previous result back to the model.
    for index, result in enumerate(results, 1):
        encoded = json.dumps(requests[index]["messages"])
        assert json.dumps(result["result"])[1:-1] in encoded
        assert result["tool_call_id"] in encoded
    assert len([event for event in events if event["type"] == "finished"]) == 1
    assert events[-1]["type"] == "finished"
    finish = events[-1]["data"]
    assert (finish["finish_reason"] if isinstance(finish, dict) else finish) == "stop"
    assert events[-2]["type"] == "content"
    assert "pytest now passes" in events[-2]["data"]
    assert agent.turn.iteration == 5
    assert agent.turn.tool_count == 5


@pytest.mark.parametrize("ids", [["duplicate", "duplicate"], [""]])
async def test_malformed_openrouter_calls_never_edit_file(tmp_path, monkeypatch, ids):
    source = tmp_path / "target.py"
    source.write_bytes(b"original\n")
    provider = create_configured_provider(
        ProviderSettings(
            default="openrouter",
            openrouter={"api_key": "offline", "model": "coding-test"},
        )
    )

    async def chunks():
        calls = [
            {
                "index": index,
                "id": call_id,
                "type": "function",
                "function": {
                    "name": "edit_file",
                    "arguments": json.dumps(
                        {
                            "path": str(source),
                            "old_str": "original",
                            "new_str": "changed",
                        }
                    ),
                },
            }
            for index, call_id in enumerate(ids)
        ]
        for delta, finish in [({"tool_calls": calls}, None), ({}, "tool_calls")]:
            yield ChatCompletionChunk.model_validate(
                {
                    "id": "completion",
                    "object": "chat.completion.chunk",
                    "created": 1,
                    "model": "coding-test",
                    "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
                }
            )

    monkeypatch.setattr(
        provider._client.chat.completions, "create", AsyncMock(return_value=SDKResponse(chunks()))
    )
    registry = ToolRegistry()
    registry.register(EditFileTool())
    confirmation = AsyncMock(return_value=True)
    registry.set_confirmation_handler(confirmation)
    agent = Agent(provider=provider, tool_registry=registry)
    events = []
    try:
        assert not await app._run_headless_json_mode(
            SimpleNamespace(agent=agent, tool_registry=registry),
            "Edit file",
            events.append,
        )
    finally:
        await provider._client.close()
    assert source.read_bytes() == b"original\n"
    confirmation.assert_not_awaited()
    assert not any(event.type == EventType.TOOL_CALL_REQUEST for event in events)
    assert any(event.type == EventType.ERROR for event in events)
