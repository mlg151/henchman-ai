"""Independent JSON-RPC subprocesses qualify real SDK stdio negotiation."""

import asyncio
import io
import json
import os
import signal
import sys
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stderr, suppress

import pytest

from henchman.config.schema import McpServerConfig
from henchman.mcp.client import McpClient

SERVER = r'''
import json, os, sys
version, transcript, log = sys.argv[1:]
if log == "logs":
    sys.stderr.write("INFO: hidden startup\n")
    sys.stderr.write("WARNING: " + os.environ["FIXTURE_SECRET_TOKEN"] + "\n")
    sys.stderr.write("x" * 100000 + "\n")
    sys.stderr.flush()
for line in sys.stdin:
    request = json.loads(line)
    with open(transcript, "a", encoding="utf-8") as output:
        output.write(json.dumps(request) + "\n")
    if "id" not in request:
        continue
    method = request["method"]
    if method == "initialize":
        if log == "stall":
            continue
        result = {"protocolVersion": version, "capabilities": {"tools": {}},
                  "serverInfo": {"name": "independent-fixture", "version": "1"}}
    elif method == "tools/list":
        result = {"tools": [{"name": "echo", "description": "Echo a supplied value",
                             "inputSchema": {"type": "object"}}]}
    elif method == "tools/call":
        result = {"content": [{"type": "text", "text": request["params"]["arguments"]["value"]}],
                  "isError": False}
    else:
        raise RuntimeError(method)
    print(json.dumps({"jsonrpc": "2.0", "id": request["id"], "result": result}), flush=True)
with open(transcript + ".closed", "w", encoding="utf-8") as output:
    output.write("closed")
'''


def fixture_client(tmp_path, version, *, logs=False, verbose=False):
    transcript = tmp_path / "wire.jsonl"
    config = McpServerConfig(command=sys.executable, args=[
        "-I", "-u", "-c", SERVER, version, str(transcript), "logs" if logs else "quiet",
    ], env={"FIXTURE_SECRET_TOKEN": "stdio-private-canary"})
    return McpClient("fixture", config, verbose=verbose), transcript


@pytest.mark.parametrize("version", ["2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25"])
async def test_stdio_profiles_negotiate_discover_call_and_close(tmp_path, version):
    client, transcript = fixture_client(tmp_path, version)
    async with asyncio.timeout(10):
        try:
            await client.connect()
            assert client.is_connected
            assert client.protocol_version == version
            assert [tool.name for tool in client.get_tools()] == ["echo"]
            result = await client.call_tool("echo", {"value": "independent result"})
            assert result.content == "independent result"
            assert not result.is_error
        finally:
            await client.disconnect()
    assert not client.is_connected
    assert client.protocol_version is None
    assert not client.get_tools()
    requests = [json.loads(line) for line in transcript.read_text().splitlines()]
    assert [item["method"] for item in requests] == [
        "initialize", "notifications/initialized", "tools/list", "tools/call",
    ]


async def test_unknown_stdio_protocol_fails_without_discovery(tmp_path):
    client, transcript = fixture_client(tmp_path, "2099-01-01")
    async with asyncio.timeout(10):
        with pytest.raises(RuntimeError, match="Unsupported protocol version"):
            await client.connect()
    assert not client.is_connected
    assert client._exit_stack is None
    assert [json.loads(line)["method"] for line in transcript.read_text().splitlines()] == ["initialize"]


@pytest.mark.parametrize("verbose", [False, True])
async def test_stdio_stderr_is_drained_filtered_and_redacted(tmp_path, capsys, verbose):
    client, _ = fixture_client(tmp_path, "2025-11-25", logs=True, verbose=verbose)
    async with asyncio.timeout(10):
        try:
            await client.connect()
            assert client.is_connected
        finally:
            await client.disconnect()
    captured = capsys.readouterr().err
    assert "stdio-private-canary" not in captured
    assert "WARNING:" in captured
    assert ("hidden startup" in captured) == verbose
    assert "x" * 1000 in captured


async def test_cancelled_initialization_closes_process_and_error_drain(tmp_path):
    client, transcript = fixture_client(tmp_path, "2025-11-25")
    client.config.args[-1] = "stall"
    leaked = []

    async def connect():
        try:
            await client.connect()
        except asyncio.CancelledError:
            leaked.append(client._exit_stack is not None)
            # Cleanup the red implementation in its owning task too.
            if client._exit_stack is not None:
                await client.disconnect()
            raise

    async with asyncio.timeout(10):
        task = asyncio.create_task(connect())
        try:
            while not transcript.exists():
                await asyncio.sleep(0.01)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        finally:
            if not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
    assert leaked == [False]
    assert transcript.with_suffix(".jsonl.closed").read_text() == "closed"
    assert not client.is_connected
    assert not [task for task in asyncio.all_tasks() if task.get_name() == "henchman-mcp-stderr"]


async def test_failed_spawn_closes_error_drain(tmp_path):
    client = McpClient("missing", McpServerConfig(command=str(tmp_path / "not-an-executable")))
    async with asyncio.timeout(10):
        with pytest.raises(OSError):
            await client.connect()
    assert client._exit_stack is None
    assert not [task for task in asyncio.all_tasks() if task.get_name() == "henchman-mcp-stderr"]


def test_idle_stderr_does_not_starve_another_pipe_with_one_executor_worker():
    """Idle MCP readers cannot monopolize the application's worker pool."""
    from henchman.mcp.client import _stdio_stderr

    async def run():
        asyncio.get_running_loop().set_default_executor(ThreadPoolExecutor(max_workers=1))
        capture = io.StringIO()
        config = McpServerConfig(command="fixture")
        with redirect_stderr(capture):
            async with _stdio_stderr(config, verbose=True) as first:
                # Let an idle first reader claim the sole worker in the red implementation.
                await asyncio.sleep(0.05)
                async with _stdio_stderr(config, verbose=True) as second:
                    try:
                        second.write(b"WARNING: independently-drained\n")
                        async with asyncio.timeout(0.5):
                            while "independently-drained" not in capture.getvalue():
                                await asyncio.sleep(0.01)
                    finally:
                        # Release the red implementation's first blocking read
                        # before second-context cleanup waits for the only worker.
                        first.close()
        assert "independently-drained" in capture.getvalue()

    asyncio.run(run())


async def test_long_quiet_log_line_remains_suppressed_after_chunk_boundary():
    """Filtering follows complete logical lines even when buffering is bounded."""
    from henchman.mcp.client import _stdio_stderr

    capture = io.StringIO()
    with redirect_stderr(capture):
        async with _stdio_stderr(McpServerConfig(command="fixture"), verbose=False) as pipe:
            for index in range(8):
                prefix = "INFO: " if index == 0 else ""
                pipe.write((prefix + "quiet-tail-marker-" * 180).encode())
                await asyncio.sleep(0.01)
            pipe.write(b"\nWARNING: visible diagnostic\n")
    assert "quiet-tail-marker-" not in capture.getvalue()
    assert "visible diagnostic" in capture.getvalue()


async def test_visible_long_line_does_not_reclassify_a_continuation_fragment():
    """A chunk boundary cannot turn the tail of a warning into an INFO line."""
    from henchman.mcp.client import _stdio_stderr

    capture = io.StringIO()
    prefix = "WARNING: " + "x" * (8192 - len("WARNING: "))
    with redirect_stderr(capture):
        async with _stdio_stderr(McpServerConfig(command="fixture"), verbose=False) as pipe:
            for index in range(0, len(prefix), 2048):
                pipe.write(prefix[index:index + 2048].encode())
                await asyncio.sleep(0.01)
            pipe.write(b"INFO: meaningful-warning-tail\n")
    assert "meaningful-warning-tail" in capture.getvalue()


async def test_inherited_stderr_writer_does_not_hold_disconnect_open(tmp_path):
    """A child retaining stderr after the server exits cannot own client teardown."""
    client, transcript = fixture_client(tmp_path, "2025-11-25")
    spawn = '''
import subprocess
child = subprocess.Popen([sys.executable, "-I", "-u", "-c", "import time; time.sleep(2)"],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
with open(transcript + ".child-pid", "w", encoding="utf-8") as child_record:
    child_record.write(str(child.pid))
'''
    client.config.args[3] = SERVER.replace(
        'version, transcript, log = sys.argv[1:]',
        'version, transcript, log = sys.argv[1:]\n' + spawn,
    )
    elapsed = None
    try:
        async with asyncio.timeout(8):
            await client.connect()
            started = asyncio.get_running_loop().time()
            await client.disconnect()
            elapsed = asyncio.get_running_loop().time() - started
    finally:
        await client.disconnect()
        pid_file = transcript.with_name(transcript.name + ".child-pid")
        if pid_file.exists():
            # The SDK may already have terminated this owned child (notably
            # Windows Job Objects). It also exits itself after two seconds.
            with suppress(OSError):
                os.kill(int(pid_file.read_text()), signal.SIGTERM)
    assert elapsed is not None and elapsed < 1.0
    assert not [task for task in asyncio.all_tasks() if task.get_name() == "henchman-mcp-stderr"]


async def test_malformed_stdout_redacts_sdk_formatted_logs_and_exception_records(tmp_path, caplog):
    """An SDK parse failure must not echo configured credentials into logs."""
    import logging

    client, _ = fixture_client(tmp_path, "2025-11-25")
    client.config.args[3] = SERVER.replace(
        "version, transcript, log = sys.argv[1:]",
        "print(os.environ['FIXTURE_SECRET_TOKEN'], flush=True)\nversion, transcript, log = sys.argv[1:]",
    )
    with caplog.at_level(logging.ERROR, logger="mcp.client.stdio"):
        async with asyncio.timeout(10):
            try:
                await client.connect()
            finally:
                await client.disconnect()
    records = [record for record in caplog.records if record.name == "mcp.client.stdio"]
    assert records, "The independent server must exercise the real SDK parse-error logger"
    assert "stdio-private-canary" not in caplog.text
    formatter = logging.Formatter("%(name)s %(levelname)s %(message)s")
    for record in records:
        assert "stdio-private-canary" not in formatter.format(record)
        assert record.exc_info is None
    assert "ValidationError" in caplog.text and "Traceback" in caplog.text
