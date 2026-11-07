"""Independent stdio peers qualify negotiated SDK 2.x behavior and boundaries."""

from __future__ import annotations

import asyncio
import json
import os
import signal
import sys
from contextlib import suppress

import pytest

from henchman.config.schema import McpServerConfig
from henchman.mcp.client import McpClient

SERVER = r'''
import json, sys
version, transcript, behavior = sys.argv[1:]
for line in sys.stdin:
    request = json.loads(line)
    with open(transcript, "a", encoding="utf-8") as output:
        output.write(json.dumps(request) + "\n")
    if "id" not in request:
        continue
    method = request["method"]
    error = None
    if method == "server/discover":
        if version == "2026-07-28":
            result = {"supportedVersions": [version], "capabilities": {"tools": {}},
                      "resultType": "complete"}
        else:
            error = {"code": -32601, "message": "Method not found"}
    elif method == "initialize":
        result = {"protocolVersion": version, "capabilities": {"tools": {}},
                  "serverInfo": {"name": "independent-compat", "version": "1"}}
    elif method == "tools/list":
        result = {"tools": [{"name": "effect", "inputSchema": {"type": "object"}}]}
    elif method == "tools/call":
        if behavior == "stall_call":
            continue
        if behavior == "disconnect":
            break
        if behavior == "oversize":
            sys.stdout.write("x" * (1024 * 1024 + 1))
            sys.stdout.flush()
            continue
        if behavior == "deep":
            sys.stdout.write('{"jsonrpc":"2.0","id":' + str(request["id"]) + ',"result":' + '[' * 1000)
            sys.stdout.write('0' + ']' * 1000 + '}\n')
            sys.stdout.flush()
            continue
        if behavior == "header_mismatch":
            error = {"code": -32020, "message": "private-error-canary"}
        elif behavior == "input_required":
            result = {"resultType": "input_required", "inputRequests": {}, "requestState": "private-state"}
        elif behavior == "mixed_input_required":
            result = {"resultType": "input_required", "inputRequests": {}, "requestState": "private-state",
                      "content": [{"type": "text", "text": "not a complete result"}]}
        elif behavior == "scalar":
            result = {"content": [], "structuredContent": [None, 42, "value"]}
        else:
            result = {"content": [{"type": "text", "text": "executed"}], "structuredContent": None}
    else:
        error = {"code": -32601, "message": "Method not found"}
    if not error and version == "2026-07-28":
        result.setdefault("resultType", "complete")
        if method in {"server/discover", "tools/list"}:
            result.update({"ttlMs": 0, "cacheScope": "private"})
    response = {"jsonrpc": "2.0", "id": request["id"]}
    response["error" if error else "result"] = error if error else result
    print(json.dumps(response), flush=True)
with open(transcript + ".closed", "w", encoding="utf-8") as output:
    output.write("closed")
'''


def fixture(tmp_path, *, version="2026-07-28", behavior="complete"):
    transcript = tmp_path / "protocol.jsonl"
    config = McpServerConfig(command=sys.executable, args=[
        "-I", "-u", "-c", SERVER, version, str(transcript), behavior,
    ])
    return McpClient("protocol-fixture", config), transcript


def requests(transcript):
    return [json.loads(line) for line in transcript.read_text().splitlines()] if transcript.exists() else []


@pytest.mark.parametrize("version", ["2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25", "2026-07-28"])
async def test_negotiation_preserves_null_arguments_and_never_injects_trace_metadata(tmp_path, version):
    client, transcript = fixture(tmp_path, version=version)
    try:
        async with asyncio.timeout(5):
            await client.connect()
            assert client.protocol_version == version
            result = await client.call_tool("effect", {"optional": None})
        assert result.structured_content_present
        assert result.structured_content is None
        wire = requests(transcript)
        assert wire[0]["method"] == "server/discover"
        assert [item["method"] for item in wire].count("initialize") == (version != "2026-07-28")
        assert wire[-1]["params"]["arguments"] == {"optional": None}
        assert not any(key in json.dumps(wire) for key in ("traceparent", "tracestate", "baggage"))
    finally:
        await client.disconnect()


@pytest.mark.parametrize("behavior", ["header_mismatch", "input_required", "mixed_input_required", "disconnect"])
async def test_tool_failure_or_continuation_never_replays_an_effect(tmp_path, behavior):
    client, transcript = fixture(tmp_path, behavior=behavior)
    try:
        async with asyncio.timeout(5):
            await client.connect()
            with pytest.raises(Exception) as error:
                await client.call_tool("effect", {})
        assert "private-error-canary" not in str(error.value)
        assert "private-state" not in str(error.value)
        assert [item["method"] for item in requests(transcript)].count("tools/call") == 1
        assert [item["method"] for item in requests(transcript)].count("tools/list") == 1
        if behavior == "disconnect":
            assert not client.is_connected
    finally:
        await client.disconnect()


async def test_modern_structured_arrays_are_preserved(tmp_path):
    client, _ = fixture(tmp_path, behavior="scalar")
    try:
        async with asyncio.timeout(5):
            await client.connect()
            result = await client.call_tool("effect", {})
        assert result.structured_content == [None, 42, "value"]
        assert result.structured_content_present
    finally:
        await client.disconnect()


async def test_oversized_unterminated_frame_fails_and_closes_owned_process(tmp_path):
    client, transcript = fixture(tmp_path, behavior="oversize")
    try:
        async with asyncio.timeout(5):
            await client.connect()
            with pytest.raises(Exception, match="mcp_wire_frame_limit"):
                await client.call_tool("effect", {})
    finally:
        await client.disconnect()
    assert transcript.with_suffix(".jsonl.closed").read_text() == "closed"


async def test_active_telemetry_refuses_before_spawning(tmp_path, monkeypatch):
    from opentelemetry import trace

    client, transcript = fixture(tmp_path)
    monkeypatch.setattr(trace, "get_tracer_provider", lambda: object())
    with pytest.raises(RuntimeError, match="telemetry"):
        await client.connect()
    assert not transcript.exists()
    assert client._owner_task is None


async def test_ambient_propagation_refuses_before_tool_dispatch(tmp_path):
    from opentelemetry import baggage, context

    client, transcript = fixture(tmp_path)
    try:
        await client.connect()
        token = context.attach(baggage.set_baggage("sensitive", "private-baggage-canary"))
        try:
            with pytest.raises(RuntimeError, match="telemetry") as error:
                await client.call_tool("effect", {})
            assert "private-baggage-canary" not in str(error.value)
        finally:
            context.detach(token)
        assert not [item for item in requests(transcript) if item["method"] == "tools/call"]
    finally:
        await client.disconnect()


async def test_excessive_json_nesting_fails_without_waiting_for_request_timeout(tmp_path):
    client, transcript = fixture(tmp_path, behavior="deep")
    try:
        async with asyncio.timeout(3):
            await client.connect()
            with pytest.raises(Exception, match="mcp_wire_frame"):
                await client.call_tool("effect", {})
    finally:
        await client.disconnect()
    assert transcript.with_suffix(".jsonl.closed").exists()


async def test_private_connection_does_not_change_an_application_tracing_provider(tmp_path, monkeypatch):
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(trace, "get_tracer_provider", lambda: provider)
    client, transcript = fixture(tmp_path)
    try:
        with pytest.raises(RuntimeError, match="telemetry"):
            await client.connect()
        assert not transcript.exists()
        assert not exporter.get_finished_spans()
        with provider.get_tracer("application").start_as_current_span("still-enabled"):
            pass
        assert [span.name for span in exporter.get_finished_spans()] == ["still-enabled"]
        assert trace.get_tracer_provider() is provider
    finally:
        provider.shutdown()


async def test_cancelled_tool_dispatch_is_not_replayed_and_process_closes(tmp_path):
    client, transcript = fixture(tmp_path, behavior="stall_call")
    pending = None
    try:
        async with asyncio.timeout(5):
            await client.connect()
            pending = asyncio.create_task(client.call_tool("effect", {}))
            while not any(item["method"] == "tools/call" for item in requests(transcript)):
                await asyncio.sleep(0.01)
            pending.cancel()
            with pytest.raises(asyncio.CancelledError):
                await pending
    finally:
        if pending is not None and not pending.done():
            pending.cancel()
            await asyncio.gather(pending, return_exceptions=True)
        await client.disconnect()
    assert [item["method"] for item in requests(transcript)].count("tools/call") == 1
    assert transcript.with_suffix(".jsonl.closed").exists()


async def test_tool_request_timeout_is_bounded_and_does_not_replay(tmp_path, monkeypatch):
    from henchman.mcp import protocol

    monkeypatch.setattr(protocol, "REQUEST_TIMEOUT_SECONDS", 0.1, raising=False)
    client, transcript = fixture(tmp_path, behavior="stall_call")
    try:
        async with asyncio.timeout(3):
            await client.connect()
            with pytest.raises(RuntimeError, match="no automatic replay"):
                await client.call_tool("effect", {})
        assert [item["method"] for item in requests(transcript)].count("tools/call") == 1
    finally:
        await client.disconnect()


async def test_descendant_retaining_stdout_does_not_block_transport_cleanup(tmp_path):
    client, transcript = fixture(tmp_path)
    spawn = r'''
import subprocess
child = subprocess.Popen([sys.executable, "-I", "-c", "import time; time.sleep(2)"], stdin=subprocess.DEVNULL)
with open(transcript + ".pid", "w") as output:
    output.write(str(child.pid))
'''
    client.config.args[3] = SERVER.replace(
        "version, transcript, behavior = sys.argv[1:]",
        "version, transcript, behavior = sys.argv[1:]\n" + spawn,
    )
    try:
        async with asyncio.timeout(5):
            await client.connect()
            started = asyncio.get_running_loop().time()
            await client.disconnect()
            assert asyncio.get_running_loop().time() - started < 1
    finally:
        await client.disconnect()
        pid_file = transcript.with_suffix(".jsonl.pid")
        if pid_file.exists():
            with suppress(OSError):
                os.kill(int(pid_file.read_text()), signal.SIGTERM)
    assert transcript.with_suffix(".jsonl.closed").exists()


async def test_sdk_notification_validation_logs_are_scoped_and_value_projected(tmp_path, caplog):
    import logging

    client, _ = fixture(tmp_path)
    client.config.env["FIXTURE_API_TOKEN"] = "notification-private-canary"
    client.config.args[3] = SERVER.replace(
        'elif method == "tools/list":',
        '''elif method == "tools/list":
        print(json.dumps({"jsonrpc":"2.0","method":"notifications/progress","params":{
            "progressToken":"fixture","progress":"notification-private-canary"}}),flush=True)''',
    )
    with caplog.at_level(logging.WARNING, logger="client"):
        try:
            await client.connect()
        finally:
            await client.disconnect()
    records = [record for record in caplog.records if record.name == "client"]
    assert records
    assert "notification-private-canary" not in caplog.text
    for record in records:
        assert record.exc_info is None
        assert "notification-private-canary" not in logging.Formatter().format(record)


async def test_invalid_modern_header_annotation_cannot_partially_replace_catalog(tmp_path):
    from henchman.tools.contracts import SchemaContractError
    from tests.mcp.test_catalog_fidelity import Fixture, declaration, state

    good = {**state(declaration("kept")), "protocolVersion": "2026-07-28"}
    peer = Fixture(tmp_path, good)
    try:
        await peer.client.connect()
        before = peer.client.get_tools()
        bad = declaration("rejected")
        bad["inputSchema"]["properties"]["value"]["x-mcp-header"] = "private invalid-header-canary"
        peer.write({**state(declaration("replacement"), bad), "protocolVersion": "2026-07-28"})
        with pytest.raises(SchemaContractError) as error:
            await peer.client.discover_tools()
        assert "invalid-header-canary" not in str(error.value)
        assert peer.client.get_tools() == before
    finally:
        await peer.client.disconnect()


async def test_queued_request_behind_blocked_stdin_has_an_outer_deadline(tmp_path, monkeypatch):
    from henchman.mcp import protocol

    monkeypatch.setattr(protocol, "REQUEST_TIMEOUT_SECONDS", 0.1)
    client, transcript = fixture(tmp_path)
    client.config.args[3] = SERVER.replace(
        'print(json.dumps(response), flush=True)',
        '''print(json.dumps(response), flush=True)
    if method == "tools/list":
        import time
        time.sleep(10)''',
    )
    pending = []
    try:
        await client.connect()
        # SDK 2.3 spends at most five extra seconds attempting its shielded
        # courtesy cancellation. Join that cleanup; never detach the request.
        async with asyncio.timeout(7):
            pending.append(asyncio.create_task(client.call_tool("effect", {"padding": "x" * 262144})))
            await asyncio.sleep(0.03)
            pending.append(asyncio.create_task(client.call_tool("effect", {"padding": "y" * 262144})))
            results = await asyncio.gather(*pending, return_exceptions=True)
        assert all(isinstance(result, RuntimeError) for result in results)
        assert all("deadline" in str(result) or "no automatic replay" in str(result) for result in results)
        assert not [item for item in requests(transcript) if item["method"] == "tools/call"]
    finally:
        for task in pending:
            if not task.done():
                task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        await client.disconnect()
    assert client._owner_task is None
    assert not [task for task in asyncio.all_tasks() if task.get_name() == "henchman-mcp-stderr"]


async def test_negotiation_has_an_outer_deadline_and_cleans_up(tmp_path, monkeypatch):
    from henchman.mcp import protocol

    monkeypatch.setattr(protocol, "NEGOTIATION_TIMEOUT_SECONDS", 0.1, raising=False)
    client, transcript = fixture(tmp_path)
    client.config.args[3] = SERVER.replace(
        'if method == "server/discover":', 'if method == "server/discover":\n        continue',
    )
    async with asyncio.timeout(3):
        with pytest.raises(RuntimeError, match="negotiation deadline"):
            await client.connect()
    assert not client.is_connected
    assert client._owner_task is None
    assert transcript.with_suffix(".jsonl.closed").exists()


async def test_slow_catalog_pages_share_a_total_deadline_and_keep_previous_catalog(tmp_path, monkeypatch):
    from henchman.mcp import protocol
    from tests.mcp.test_catalog_fidelity import SERVER as CATALOG_SERVER
    from tests.mcp.test_catalog_fidelity import Fixture, declaration, state

    monkeypatch.setattr(protocol, "CATALOG_TIMEOUT_SECONDS", 0.1, raising=False)
    monkeypatch.setattr(protocol, "REQUEST_TIMEOUT_SECONDS", 1)
    peer = Fixture(tmp_path, state(declaration("kept")))
    peer.config.args[3] = CATALOG_SERVER.replace(
        "result=state['pages'][cursor]",
        "import time\n        time.sleep(state.get('page_delay',0))\n        result=state['pages'][cursor]",
    )
    try:
        await peer.client.connect()
        before = peer.client.get_tools()
        peer.write({"page_delay": 0.06, "pages": {
            "": {"tools": [declaration("new-one")], "nextCursor": "two"},
            "two": {"tools": [declaration("new-two")], "nextCursor": "three"},
            "three": {"tools": [declaration("new-three")]},
        }})
        async with asyncio.timeout(3):
            with pytest.raises(RuntimeError, match="catalog discovery deadline"):
                await peer.client.discover_tools()
        assert peer.client.get_tools() == before
    finally:
        await peer.client.disconnect()
