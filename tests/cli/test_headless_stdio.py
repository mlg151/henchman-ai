"""Real POSIX pipe transport over the shared runtime; no model requests."""

import asyncio
import json
import os
import sys
from contextlib import suppress

import pytest

from tests.cli import test_headless_runtime as shared
from tests.cli.test_headless_runtime import until

context = shared.context

pytestmark = pytest.mark.skipif(os.name != "posix", reason="Initial stdio transport is POSIX only")


@pytest.fixture
def pipes():
    from henchman.cli.headless_stdio import PipeChannel

    input_fd, client_write = os.pipe()
    client_read, output_fd = os.pipe()
    os.set_blocking(client_read, False)
    channel = PipeChannel(input_fd, output_fd)
    yield channel, client_write, client_read
    channel.close()
    for fd in (client_write, client_read):
        with suppress(OSError):
            os.close(fd)


async def read_frame(fd, buffer):
    async with asyncio.timeout(10):
        while b"\n" not in buffer:
            try:
                value = os.read(fd, 65536)
            except BlockingIOError:
                await asyncio.sleep(0.001)
            else:
                assert value, "pipe closed before a complete frame"
                buffer.extend(value)
        line, _, tail = buffer.partition(b"\n")
        buffer[:] = tail
        return json.loads(line)


def send(fd, value):
    os.write(fd, json.dumps(value).encode() + b"\n")


def initialize_frame():
    return {"v": 1, "id": 1, "method": "initialize", "params": {
        "session": {"mode": "new"}, "interactive": {"permissions": True, "questions": True}}}


def run_frame(initial):
    return {"v": 1, "id": 2, "method": "run", "connection_id": initial["payload"]["connection_id"],
            "params": {"session_id": initial["session_id"], "prompt": "work", "agent": None}}


async def test_editor_selection_binds_before_runtime_and_retires_after_join(context, pipes):
    from pathlib import Path

    from henchman.cli.headless_stdio import serve_context
    from henchman.integrations.neovim import EditorSelection
    from henchman.tools.builtins.file_read import ReadFileTool

    Path("selected.py").write_text("value = 1\n")
    selection = EditorSelection(Path.cwd(), ("selected.py",))
    prior = context.tool_registry._execution_guard
    channel, client_write, client_read = pipes
    worker = asyncio.create_task(serve_context(context, channel, selection=selection))
    send(client_write, initialize_frame())
    initial = await read_frame(client_read, bytearray())
    assert context.tool_registry._execution_guard is not prior
    send(client_write, run_frame(initial))
    buffer = bytearray()
    while (await read_frame(client_read, buffer))["kind"] != "result":
        pass
    assert await asyncio.wait_for(worker, 5) == 0
    assert context.tool_registry._execution_guard is prior
    assert selection.guard(ReadFileTool(), {"path": "selected.py"}) is not None


async def test_busy_editor_context_does_not_change_guard_or_policy_generation(context, pipes):
    from pathlib import Path

    from henchman.cli.headless_runtime import HeadlessRuntimeError
    from henchman.cli.headless_stdio import serve_context
    from henchman.integrations.neovim import EditorSelection

    Path("selected.py").write_text("value = 1\n")
    selection = EditorSelection(Path.cwd(), ("selected.py",))
    registry = context.tool_registry
    prior, generation = registry._execution_guard, registry._policy_generation
    context.orchestrator._public_run_active = True
    try:
        with pytest.raises(HeadlessRuntimeError, match="runtime_busy"):
            await serve_context(context, pipes[0], selection=selection)
        assert registry._execution_guard is prior
        assert registry._policy_generation == generation
    finally:
        context.orchestrator._public_run_active = False


async def test_constructor_failure_after_selection_hook_restores_owned_guard(context, pipes, monkeypatch):
    from pathlib import Path

    from henchman.cli.headless_stdio import serve_context
    from henchman.integrations.neovim import EditorSelection
    from henchman.tools.registry import ToolRegistry

    Path("selected.py").write_text("value = 1\n")
    selection = EditorSelection(Path.cwd(), ("selected.py",))
    registry = context.tool_registry
    prior = registry._execution_guard
    original = ToolRegistry.__getattribute__
    observed = []
    def fail_after_hook(instance, name):
        if instance is registry and name == "_local_confirmation_handler":
            observed.append(original(instance, "_execution_guard") is not prior)
            raise ValueError("constructor fault")
        return original(instance, name)
    monkeypatch.setattr(ToolRegistry, "__getattribute__", fail_after_hook)
    with pytest.raises(ValueError, match="constructor fault"):
        await serve_context(context, pipes[0], selection=selection)
    assert observed == [True]
    assert registry._execution_guard is prior


def test_invalid_editor_selection_fails_before_provider_construction(tmp_path):
    import subprocess

    script = '''
from henchman import entrypoint
import henchman.cli.app as app
app._prepare_runtime_context = lambda **kwargs: (_ for _ in ()).throw(AssertionError("constructed provider"))
entrypoint.main()
'''
    result = subprocess.run([sys.executable, "-c", script, "headless", "--protocol-version", "1",
                             "--project", str(tmp_path), "--editor-path", "missing"],
                            input=b"", capture_output=True, timeout=20, check=False)
    assert result.returncode == 2 and result.stdout == b""
    assert b"Invalid headless arguments" in result.stderr and b"constructed provider" not in result.stderr


async def test_pipe_round_trip_preserves_unicode_long_frame_and_order(pipes):
    channel, client_write, client_read = pipes
    raw = (json.dumps({"text": "é🙂" * 20000}, ensure_ascii=False) + "\n").encode()
    writer = asyncio.create_task(channel.write(raw))
    frame = await read_frame(client_read, bytearray())
    await writer
    assert frame == {"text": "é🙂" * 20000}
    os.write(client_write, b"input")
    assert await channel.read() == b"input"


async def test_write_deadline_aborts_partial_frame_and_rejects_later_output(pipes):
    from henchman.cli.headless_stdio import StdioError

    channel, _, client_read = pipes
    channel.frame_timeout = 0.03
    with pytest.raises(StdioError, match="output_timeout"):
        await channel.write(b"x" * 200000 + b"\n")
    assert os.read(client_read, 65536).startswith(b"x")
    with pytest.raises(StdioError, match="output_closed"):
        await channel.write(b'{"later":true}\n')


async def test_real_runtime_finishes_only_after_delivered_terminal(context, pipes):
    from henchman.cli.headless_stdio import serve_context

    channel, client_write, client_read = pipes
    worker = asyncio.create_task(serve_context(context, channel))
    send(client_write, initialize_frame())
    buffer = bytearray()
    initial = await read_frame(client_read, buffer)
    send(client_write, run_frame(initial))
    frames = [initial]
    while frames[-1]["kind"] != "result":
        frames.append(await read_frame(client_read, buffer))
    assert await asyncio.wait_for(worker, 5) == 0
    assert frames[-1]["payload"]["status"] == "completed"
    assert frames[-1]["payload"]["task_verified"] is False
    assert [frame["seq"] for frame in frames] == list(range(1, len(frames) + 1))


async def test_active_malformed_input_is_value_free_and_incomplete(context, pipes):
    from henchman.cli.headless_stdio import serve_context

    entered, cleaned = asyncio.Event(), asyncio.Event()

    async def stream(*_args, **_kwargs):
        entered.set()
        try:
            await asyncio.Event().wait()
            yield
        finally:
            cleaned.set()

    context.provider.chat_completion_stream.side_effect = stream
    channel, client_write, client_read = pipes
    worker = asyncio.create_task(serve_context(context, channel))
    buffer = bytearray()
    send(client_write, initialize_frame())
    initial = await read_frame(client_read, buffer)
    send(client_write, run_frame(initial))
    await asyncio.wait_for(entered.wait(), 5)
    os.write(client_write, b'{"private":"canary-secret"\n')
    frames = []
    while not frames or frames[-1]["kind"] != "result":
        frames.append(await read_frame(client_read, buffer))
    assert await asyncio.wait_for(worker, 5) == 2
    assert cleaned.is_set()
    assert frames[-1]["payload"]["status"] == "incomplete"
    assert "canary-secret" not in json.dumps(frames)
    assert any(frame["kind"] == "error" and frame["payload"]["code"] == "invalid_json" for frame in frames)


async def test_eof_cancels_and_joins_provider_without_claiming_delivery(context, pipes):
    from henchman.cli.headless_stdio import serve_context

    entered, cleanup, release = asyncio.Event(), asyncio.Event(), asyncio.Event()

    async def stream(*_args, **_kwargs):
        entered.set()
        try:
            await asyncio.Event().wait()
            yield
        finally:
            cleanup.set()
            await release.wait()

    context.provider.chat_completion_stream.side_effect = stream
    channel, client_write, client_read = pipes
    worker = asyncio.create_task(serve_context(context, channel))
    buffer = bytearray()
    send(client_write, initialize_frame())
    initial = await read_frame(client_read, buffer)
    send(client_write, run_frame(initial))
    await asyncio.wait_for(entered.wait(), 5)
    os.close(client_write)
    await asyncio.wait_for(cleanup.wait(), 5)
    assert not worker.done()
    release.set()
    assert await asyncio.wait_for(worker, 5) == 1
    assert context.session_manager.workflow_runtime.report().state.inputs[0].state != "completed"


@pytest.mark.parametrize("args", [[], ["--protocol-version", "2"], ["--protocol-version", "x"]])
def test_invalid_opt_in_never_constructs_provider(tmp_path, args):
    import subprocess

    script = '''
import sys
from henchman import entrypoint
import henchman.cli.app as app
app._prepare_runtime_context = lambda: (_ for _ in ()).throw(AssertionError("constructed provider"))
entrypoint.main()
'''
    result = subprocess.run([sys.executable, "-c", script, "headless", *args, "--project", str(tmp_path)],
                            input=b"", capture_output=True, timeout=20, check=False)
    assert result.returncode == 2
    assert result.stdout == b""
    assert b"constructed provider" not in result.stderr


async def test_cancel_is_readable_while_real_output_pipe_is_full(context, pipes):
    from henchman.cli.headless_stdio import serve_context
    from henchman.providers.base import StreamChunk

    cleaned = asyncio.Event()
    async def stream(*_args, **_kwargs):
        try:
            yield StreamChunk(content="x" * 300000)
            await asyncio.Event().wait()
        finally:
            cleaned.set()
    context.provider.chat_completion_stream.side_effect = stream
    channel, client_write, client_read = pipes
    worker = asyncio.create_task(serve_context(context, channel))
    buffer = bytearray()
    send(client_write, initialize_frame())
    initial = await read_frame(client_read, buffer)
    send(client_write, run_frame(initial))
    await until(lambda: True in channel._waiters)
    send(client_write, {"v": 1, "id": 3, "method": "cancel", "connection_id": initial["payload"]["connection_id"],
                        "params": {"run_request_id": 2, "run_id": None}})
    await asyncio.wait_for(cleaned.wait(), 5)
    assert not worker.done()
    frames = []
    while not frames or frames[-1]["kind"] != "result":
        frames.append(await read_frame(client_read, buffer))
    assert await asyncio.wait_for(worker, 5) == 130
    assert frames[-1]["payload"]["status"] == "cancelled"
    assert sum(frame["kind"] == "result" for frame in frames) == 1


@pytest.mark.parametrize("stop", ["eof", "shutdown", "signal"])
async def test_startup_stop_joins_context_cleanup_before_return(pipes, monkeypatch, stop):
    from henchman.cli import headless_stdio

    entered, cleanup, release, interrupted = (asyncio.Event() for _ in range(4))
    async def build(_resources):
        try:
            entered.set()
            await asyncio.Event().wait()
        finally:
            cleanup.set()
            await release.wait()
    monkeypatch.setattr(headless_stdio, "_build_context", build)
    channel, client_write, _ = pipes
    worker = asyncio.create_task(headless_stdio.run_stdio(channel, interrupted=interrupted))
    send(client_write, initialize_frame())
    await asyncio.wait_for(entered.wait(), 5)
    if stop == "eof":
        os.close(client_write)
    elif stop == "shutdown":
        send(client_write, {"v": 1, "id": 2, "method": "shutdown", "connection_id": None, "params": {}})
    else:
        interrupted.set()
    await asyncio.wait_for(cleanup.wait(), 5)
    assert not worker.done()
    release.set()
    assert await asyncio.wait_for(worker, 5) == {"eof": 1, "shutdown": 0, "signal": 130}[stop]


async def test_partial_terminal_delivery_keeps_persisted_completed_outcome(context, pipes):
    from henchman.cli.headless_stdio import StdioError, serve_context

    channel, client_write, client_read = pipes
    original = channel.write
    async def fail_terminal(frame):
        if json.loads(frame)["kind"] == "result":
            os.write(channel.output_fd, frame[:10])
            raise StdioError("output_closed")
        await original(frame)
    channel.write = fail_terminal
    worker = asyncio.create_task(serve_context(context, channel))
    buffer = bytearray()
    send(client_write, initialize_frame())
    initial = await read_frame(client_read, buffer)
    send(client_write, run_frame(initial))
    assert await asyncio.wait_for(worker, 5) == 1
    assert context.session_manager.workflow_runtime.report().state.inputs[0].state == "completed"
    assert context.session_manager.current.messages[-1].content == "Done"


async def test_eof_after_startup_finished_still_closes_untransferred_context(context, pipes, monkeypatch):
    from henchman.cli import headless_stdio

    entered, release = asyncio.Event(), asyncio.Event()
    released = []
    async def build(_resources):
        entered.set()
        await release.wait()
        return context
    async def close(value):
        released.append(value)
    monkeypatch.setattr(headless_stdio, "_build_context", build)
    monkeypatch.setattr(headless_stdio, "_release_context", close)
    channel, client_write, _ = pipes
    worker = asyncio.create_task(headless_stdio.run_stdio(channel))
    send(client_write, initialize_frame())
    await asyncio.wait_for(entered.wait(), 5)
    os.close(client_write)
    release.set()
    assert await asyncio.wait_for(worker, 5) == 1
    assert released == [context]


async def test_cancelled_transport_owner_still_joins_cleanup_and_keeps_first_cancel(context, pipes):
    from henchman.cli.headless_stdio import serve_context

    entered, cleanup, release = (asyncio.Event() for _ in range(3))
    async def stream(*_args, **_kwargs):
        entered.set()
        try:
            await asyncio.Event().wait()
            yield
        finally:
            cleanup.set()
            await release.wait()
    context.provider.chat_completion_stream.side_effect = stream
    channel, client_write, client_read = pipes
    worker = asyncio.create_task(serve_context(context, channel))
    buffer = bytearray()
    send(client_write, initialize_frame())
    initial = await read_frame(client_read, buffer)
    send(client_write, run_frame(initial))
    await asyncio.wait_for(entered.wait(), 5)
    worker.cancel("first owner interruption")
    await asyncio.wait_for(cleanup.wait(), 5)
    worker.cancel("second owner interruption")
    await asyncio.sleep(0)
    assert not worker.done()
    release.set()
    with pytest.raises(asyncio.CancelledError) as caught:
        await asyncio.wait_for(worker, 5)
    assert caught.value.args == ("first owner interruption",)


async def test_startup_shutdown_cleanup_failure_cannot_exit_success(pipes, monkeypatch):
    from henchman.cli import headless_stdio

    entered = asyncio.Event()
    async def build(_resources):
        try:
            entered.set()
            await asyncio.Event().wait()
        finally:
            raise RuntimeError("startup cleanup fault")
    monkeypatch.setattr(headless_stdio, "_build_context", build)
    channel, client_write, _ = pipes
    worker = asyncio.create_task(headless_stdio.run_stdio(channel))
    send(client_write, initialize_frame())
    await asyncio.wait_for(entered.wait(), 5)
    send(client_write, {"v": 1, "id": 2, "method": "shutdown", "connection_id": None, "params": {}})
    assert await asyncio.wait_for(worker, 5) == 1


@pytest.mark.parametrize("launcher", ["module", "henchman", "mlg"])
async def test_actual_entrypoint_scripted_run_and_startup_plugin_isolation(tmp_path, launcher):
    from pathlib import Path

    # The plugin executes real startup code but never contacts any provider.
    # SDK traffic is replaced by a deterministic stream inside this subprocess.
    plugin_dir = tmp_path / ".henchman" / "plugins"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "noise.py").write_text('import os, sys\nprint("plugin Python output")\nos.write(1, b"plugin native output\\n")\nassert os.read(0, 1) == b""\nassert sys.stdin.read() == ""\n')
    hook = tmp_path / "hooks"
    hook.mkdir()
    (hook / "sitecustomize.py").write_text('''
import asyncio, os
from henchman.providers.openai_compat import OpenAICompatibleProvider
from henchman.providers.base import StreamChunk, FinishReason
async def stream(self, **kwargs):
    yield StreamChunk(content="Unicode é🙂 " + "x" * 20000)
    yield StreamChunk(finish_reason=FinishReason.STOP, usage={"input_tokens":1,"output_tokens":1}, usage_source="reported")
OpenAICompatibleProvider.chat_completion_stream = stream
''')
    settings = tmp_path / ".henchman" / "settings.yaml"
    settings.write_text('providers:\n  default: openai_compat\n  openai_compat:\n    model: scripted\n    base_url: http://127.0.0.1:1/v1\n    api_key: fixture-key\n')
    env = dict(os.environ)
    env["PYTHONPATH"] = str(hook) + os.pathsep + env.get("PYTHONPATH", "")
    command = [sys.executable, "-m", "henchman"] if launcher == "module" else [str(Path(sys.executable).parent / launcher)]
    proc = await asyncio.create_subprocess_exec(*command, "headless", "--protocol-version", "1", "--project", str(tmp_path),
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env=env)
    try:
        proc.stdin.write(json.dumps(initialize_frame()).encode() + b"\n")
        await proc.stdin.drain()
        initial = json.loads(await asyncio.wait_for(proc.stdout.readline(), 15))
        assert initial["kind"] == "response", initial
        proc.stdin.write(json.dumps(run_frame(initial)).encode() + b"\n")
        await proc.stdin.drain()
        frames = [initial]
        async with asyncio.timeout(20):
            while frames[-1]["kind"] != "result":
                frames.append(json.loads(await proc.stdout.readline()))
            assert await proc.wait() == 0
        diagnostics = await proc.stderr.read()
        assert b"plugin Python output" in diagnostics and b"plugin native output" in diagnostics
        assert frames[-1]["payload"]["status"] == "completed"
        assert frames[-1]["payload"]["task_verified"] is False
        assert "Unicode é🙂" in json.dumps(frames, ensure_ascii=False)
        assert all(frame["v"] == 1 for frame in frames)
    finally:
        if proc.returncode is None:
            proc.kill()
            await proc.wait()


async def test_actual_sigint_joins_delayed_provider_cleanup(tmp_path):
    import signal

    hook = tmp_path / "hooks"
    hook.mkdir()
    entered, cleanup, release = (tmp_path / name for name in ("entered", "cleanup", "release"))
    (hook / "sitecustomize.py").write_text('''
import asyncio, os
from pathlib import Path
from henchman.providers.openai_compat import OpenAICompatibleProvider
from henchman.providers.base import StreamChunk
async def stream(self, **kwargs):
    Path(os.environ["ENTERED"]).touch()
    try:
        await asyncio.Event().wait()
        yield StreamChunk()
    finally:
        Path(os.environ["CLEANUP"]).touch()
        while not Path(os.environ["RELEASE"]).exists():
            await asyncio.sleep(.01)
OpenAICompatibleProvider.chat_completion_stream = stream
''')
    config = tmp_path / ".henchman"
    config.mkdir()
    (config / "settings.yaml").write_text('providers:\n  default: openai_compat\n  openai_compat:\n    model: scripted\n    base_url: http://127.0.0.1:1/v1\n    api_key: fixture-key\n')
    env = {**os.environ, "PYTHONPATH": str(hook) + os.pathsep + os.environ.get("PYTHONPATH", ""),
           "ENTERED": str(entered), "CLEANUP": str(cleanup), "RELEASE": str(release)}
    proc = await asyncio.create_subprocess_exec(sys.executable, "-m", "henchman", "headless", "--protocol-version", "1", "--project", str(tmp_path),
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env=env)
    try:
        proc.stdin.write(json.dumps(initialize_frame()).encode() + b"\n")
        await proc.stdin.drain()
        initial = json.loads(await asyncio.wait_for(proc.stdout.readline(), 15))
        proc.stdin.write(json.dumps(run_frame(initial)).encode() + b"\n")
        await proc.stdin.drain()
        async with asyncio.timeout(15):
            while not entered.exists():
                await asyncio.sleep(.01)
        proc.send_signal(signal.SIGINT)
        async with asyncio.timeout(10):
            while not cleanup.exists():
                await asyncio.sleep(.01)
        proc.send_signal(signal.SIGINT)
        await asyncio.sleep(.05)
        assert proc.returncode is None
        release.touch()
        frames = []
        async with asyncio.timeout(15):
            while not frames or frames[-1]["kind"] != "result":
                frames.append(json.loads(await proc.stdout.readline()))
            assert await proc.wait() == 130
        assert frames[-1]["payload"]["status"] == "cancelled"
        assert sum(frame["kind"] == "result" for frame in frames) == 1
    finally:
        release.touch()
        if proc.returncode is None:
            proc.kill()
            await proc.wait()


async def test_owned_sdk_clients_are_deduplicated_and_closed_before_result(context, pipes):
    from unittest.mock import AsyncMock

    from henchman.cli.headless_stdio import serve_context
    from henchman.providers.openai_compat import OpenAICompatibleProvider

    provider = OpenAICompatibleProvider(api_key="fixture-key", base_url="http://127.0.0.1:1/v1", default_model="scripted")
    await provider._client.close()
    provider._client = type("OwnedClient", (), {"close": AsyncMock()})()
    context.provider = provider
    # Keep the scripted runtime stream but expose the same owned SDK through
    # multiple real provider instances/roles to exercise identity deduplication.
    from types import SimpleNamespace
    context.orchestrator.pool._agents["unused_provider"] = SimpleNamespace(provider=provider, tool_registry=context.tool_registry)
    channel, client_write, client_read = pipes
    worker = asyncio.create_task(serve_context(context, channel))
    buffer = bytearray()
    send(client_write, initialize_frame())
    initial = await read_frame(client_read, buffer)
    send(client_write, run_frame(initial))
    frames = []
    while not frames or frames[-1]["kind"] != "result":
        frames.append(await read_frame(client_read, buffer))
    assert await asyncio.wait_for(worker, 5) == 0
    provider._client.close.assert_awaited_once()


@pytest.mark.parametrize("cancel", [False, True])
async def test_mcp_startup_failure_closes_owned_sdk_and_preserves_primary(context, monkeypatch, cancel):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from henchman.cli import app, headless_stdio
    from henchman.providers.openai_compat import OpenAICompatibleProvider

    provider = OpenAICompatibleProvider(api_key="fixture-key", base_url="http://127.0.0.1:1/v1", default_model="scripted")
    await provider._client.close()
    provider._client = SimpleNamespace(close=AsyncMock(side_effect=RuntimeError("secondary SDK cleanup failure")))
    context.provider = provider
    entered, cleanup, release = (asyncio.Event() for _ in range(3))
    primary = asyncio.CancelledError("owned startup cancellation") if cancel else RuntimeError("primary MCP startup failure")
    async def connect():
        entered.set()
        raise primary
    async def disconnect():
        cleanup.set()
        await release.wait()
    context.mcp_manager = SimpleNamespace(connect_all=connect, disconnect_all=disconnect)
    monkeypatch.setattr(headless_stdio, "create_core_context", lambda *_args, **_kwargs: context)
    monkeypatch.setattr(app, "_prepare_runtime_context", lambda **_kwargs: SimpleNamespace(provider=provider,
        system_prompt="", env_block="", settings=context.settings, instruction_snapshot=None, settings_state=context.settings_state))
    resources = headless_stdio._StartupResources()
    worker = asyncio.create_task(headless_stdio._build_context(resources))
    await asyncio.wait_for(entered.wait(), 5)
    await asyncio.wait_for(cleanup.wait(), 5)
    assert not worker.done()
    release.set()
    with pytest.raises(type(primary)) as caught:
        await worker
    assert caught.value is primary
    assert resources.failure is not None
    provider._client.close.assert_awaited_once()
    await resources.close()
    provider._client.close.assert_awaited_once()


async def test_eof_retires_real_permission_without_writing(context, pipes, tmp_path):
    from henchman.cli.headless_stdio import serve_context
    from henchman.providers.base import FinishReason, StreamChunk, ToolCall

    target = tmp_path / "denied.txt"
    context.provider.responses.clear()
    context.provider.responses.append([StreamChunk(tool_calls=[ToolCall(id="write1", name="write_file", arguments={"path": str(target), "content": "must not be written"})], finish_reason=FinishReason.TOOL_CALLS)])
    channel, client_write, client_read = pipes
    worker = asyncio.create_task(serve_context(context, channel))
    buffer = bytearray()
    send(client_write, initialize_frame())
    initial = await read_frame(client_read, buffer)
    send(client_write, run_frame(initial))
    while True:
        frame = await read_frame(client_read, buffer)
        if frame["kind"] == "event" and frame["payload"].get("type") == "permission":
            break
    assert frame["payload"]["state"] == "pending"
    os.close(client_write)
    assert await asyncio.wait_for(worker, 5) == 1
    assert not target.exists()


@pytest.mark.parametrize("raw,code", [(b'{"v":2}\n', "unsupported_version"), (b'{"secret":"private-canary"\n', "invalid_json"), (b'{"partial":', "unterminated_frame")])
async def test_bad_input_before_startup_never_builds_context(pipes, monkeypatch, raw, code):
    from henchman.cli import headless_stdio

    async def build(_resources):
        pytest.fail("invalid input constructed runtime")
    monkeypatch.setattr(headless_stdio, "_build_context", build)
    channel, client_write, client_read = pipes
    worker = asyncio.create_task(headless_stdio.run_stdio(channel))
    os.write(client_write, raw)
    if not raw.endswith(b"\n"):
        os.close(client_write)
    frame = await read_frame(client_read, bytearray())
    assert await asyncio.wait_for(worker, 5) == 2
    assert frame["kind"] == "error" and frame["payload"]["code"] == code
    assert "private-canary" not in json.dumps(frame)


async def test_absolute_write_deadline_does_not_reset_when_reader_trickles(pipes):
    from henchman.cli.headless_stdio import StdioError

    channel, _, client_read = pipes
    channel.frame_timeout = .05
    consumed = []
    async def trickle():
        for _ in range(100):
            await asyncio.sleep(.01)
            with suppress(BlockingIOError):
                consumed.append(os.read(client_read, 1024))
    reader = asyncio.create_task(trickle())
    try:
        async with asyncio.timeout(.3):
            with pytest.raises(StdioError, match="output_timeout"):
                await channel.write(b"x" * 1000000 + b"\n")
        assert consumed
    finally:
        reader.cancel()
        await asyncio.gather(reader, return_exceptions=True)


@pytest.mark.parametrize("initialize_first", [False, True])
async def test_explicit_shutdown_before_binding_never_constructs_context(pipes, monkeypatch, initialize_first):
    from henchman.cli import headless_stdio

    async def build(_resources):
        pytest.fail("pre-binding shutdown constructed runtime")
    monkeypatch.setattr(headless_stdio, "_build_context", build)
    channel, client_write, _ = pipes
    frames = [initialize_frame()] if initialize_first else []
    frames.append({"v": 1, "id": len(frames) + 1, "method": "shutdown", "connection_id": None, "params": {}})
    os.write(client_write, b"".join(json.dumps(frame).encode() + b"\n" for frame in frames))
    assert await asyncio.wait_for(headless_stdio.run_stdio(channel), 5) == 0


@pytest.mark.parametrize("close_fails", [False, True])
async def test_failure_after_provider_factory_still_closes_owned_client(context, pipes, monkeypatch, close_fails):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from henchman.cli import app, headless_stdio, provider_switch
    from henchman.providers.openai_compat import OpenAICompatibleProvider

    provider = OpenAICompatibleProvider(api_key="fixture-key", base_url="http://127.0.0.1:1/v1", default_model="scripted")
    await provider._client.close()
    provider._client = SimpleNamespace(close=AsyncMock(side_effect=RuntimeError("close failed") if close_fails else None))
    primary = RuntimeError("instruction snapshot failed after provider construction")
    class BrokenLoader:
        def load_snapshot(self):
            raise primary
    monkeypatch.setattr(app, "_import_attrs", lambda module, *_names: (BrokenLoader, lambda: None) if module == "henchman.config" else (lambda value: value, lambda: "environment"))
    monkeypatch.setattr(app, "RuntimeSettingsState", lambda _snapshot: context.settings_state)
    monkeypatch.setattr(app, "_get_provider", lambda **_kwargs: provider)
    monkeypatch.setattr(provider_switch, "capture_startup_provider_settings", lambda *_args, **_kwargs: None)
    seen = []
    original = headless_stdio._build_context
    async def build(resources):
        try:
            return await original(resources)
        except BaseException as error:
            seen.append((error, resources))
            raise
    monkeypatch.setattr(headless_stdio, "_build_context", build)
    channel, client_write, client_read = pipes
    worker = asyncio.create_task(headless_stdio.run_stdio(channel))
    send(client_write, initialize_frame())
    frame = await read_frame(client_read, bytearray())
    assert frame["kind"] == "error" and frame["payload"]["code"] == "startup_failed"
    assert await asyncio.wait_for(worker, 5) == (1 if close_fails else 2)
    assert len(seen) == 1 and seen[0][0] is primary
    resources = seen[0][1]
    assert resources.closed and resources.provider is provider
    assert (resources.failure is not None) == close_fails
    provider._client.close.assert_awaited_once()
    await resources.close()
    provider._client.close.assert_awaited_once()
