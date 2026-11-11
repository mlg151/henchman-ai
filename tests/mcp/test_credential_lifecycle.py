"""Local stdio servers prove scoped injection and credential invalidation."""

import asyncio
import gc
import json
import sys
import weakref
from pathlib import Path

import pytest

from henchman.config.schema import McpServerConfig
from henchman.mcp.client import McpClient
from henchman.mcp.manager import McpManager

SERVER = r'''
import json, os, sys
from pathlib import Path
marker = Path(sys.argv[1])
marker.write_text("started")
if os.environ.get("ECHO_DIAGNOSTIC"):
    sys.stderr.write("WARNING: " + os.environ.get("PLAIN", "") + "\n")
    sys.stderr.flush()
for line in sys.stdin:
    request = json.loads(line)
    if "id" not in request:
        continue
    if request["method"] == "server/discover":
        print(json.dumps({"jsonrpc": "2.0", "id": request["id"],
                          "error": {"code": -32601, "message": "Method not found"}}), flush=True)
        continue
    if request["method"] == "initialize":
        if os.environ.get("STARTUP_STALL"):
            continue
        result = {"protocolVersion": os.environ.get("PROTOCOL", "2025-11-25"), "capabilities": {"tools": {}},
                  "serverInfo": {"name": "credential-fixture", "version": "1"}}
    elif request["method"] == "tools/list":
        result = {"tools": [{"name": "inspect", "description": "Inspect fixture environment",
                            "inputSchema": {"type": "object"}}]}
    else:
        with marker.with_suffix(".calls").open("a") as calls:
            calls.write("called\n")
        result = {"content": [{"type": "text", "text": json.dumps({
            key: os.environ.get(key) for key in ("GITHUB_TOKEN", "HMN_MCP_AUTH_TOKEN", "UNRELATED_TOKEN", "PLAIN")
        })}], "isError": False}
    print(json.dumps({"jsonrpc": "2.0", "id": request["id"], "result": result}), flush=True)
marker.with_suffix(".closed").write_text("closed")
'''


def server_config(tmp_path: Path, env: dict[str, str] | None = None) -> McpServerConfig:
    return McpServerConfig(command=sys.executable, args=["-I", "-u", "-c", SERVER, str(tmp_path / "server")],
                           env=env or {})


async def test_native_client_resolves_only_configured_references_without_mutation(tmp_path, monkeypatch):
    monkeypatch.setenv("ORDINARY_SOURCE", "native-reference-canary")
    monkeypatch.setenv("UNRELATED_TOKEN", "unrelated-private-canary")
    config = server_config(tmp_path, {"GITHUB_TOKEN": "${ORDINARY_SOURCE}", "PLAIN": "literal"})
    client = McpClient("fixture", config)
    try:
        await client.connect()
        result = json.loads((await client.call_tool("inspect", {})).content)
        assert result == {"GITHUB_TOKEN": "native-reference-canary", "HMN_MCP_AUTH_TOKEN": None,
                          "UNRELATED_TOKEN": None, "PLAIN": "literal"}
        assert config.env["GITHUB_TOKEN"] == "${ORDINARY_SOURCE}"
    finally:
        await client.disconnect()


@pytest.mark.parametrize("value", [None, ""])
async def test_missing_reference_fails_before_native_process_start(tmp_path, monkeypatch, value):
    if value is None:
        monkeypatch.delenv("MISSING_MCP_CREDENTIAL", raising=False)
    else:
        monkeypatch.setenv("MISSING_MCP_CREDENTIAL", value)
    client = McpClient("fixture", server_config(tmp_path, {"GITHUB_TOKEN": "${MISSING_MCP_CREDENTIAL}"}))
    try:
        with pytest.raises(ValueError, match="MISSING_MCP_CREDENTIAL"):
            await client.connect()
        assert not (tmp_path / "server").exists()
        assert not client.is_connected
    finally:
        await client.disconnect()


@pytest.mark.parametrize("reference", ["${BAD-NAME}", "${MISSING", "prefix-${TOKEN}", "${}"])
async def test_malformed_reference_fails_before_process_start(tmp_path, reference):
    client = McpClient("fixture", server_config(tmp_path, {"GITHUB_TOKEN": reference}))
    try:
        with pytest.raises(ValueError, match="reference"):
            await client.connect()
        assert not (tmp_path / "server").exists()
    finally:
        await client.disconnect()


@pytest.mark.parametrize("action", ["rotate", "clear"])
async def test_manager_invalidates_live_native_clients_and_captured_wrappers(tmp_path, action):
    manager = McpManager({"fixture": server_config(tmp_path)})
    manager.set_auth_token("fixture", "old-auth-canary")
    try:
        await manager.connect_server("fixture")
        old_client = manager.clients["fixture"]
        old_tool = manager.get_all_tools()[0]
        initial = json.loads((await old_tool.execute()).content)
        assert initial["HMN_MCP_AUTH_TOKEN"] == "old-auth-canary"
        if action == "rotate":
            manager.set_auth_token("fixture", "new-auth-canary")
        else:
            manager.clear_auth_token("fixture")
        for call in (lambda: manager.call_tool("fixture", "inspect", {}),
                     lambda: old_client.call_tool("inspect", {}), old_tool.execute):
            with pytest.raises(RuntimeError, match="reconnect") as caught:
                await call()
            assert "auth-canary" not in str(caught.value)
        assert not manager.list_servers()[0]["connected"]
        assert (tmp_path / "server.calls").read_text() == "called\n"
        await manager.connect_server("fixture")
        fresh = json.loads((await manager.call_tool("fixture", "inspect", {})).content)
        assert fresh["HMN_MCP_AUTH_TOKEN"] == ("new-auth-canary" if action == "rotate" else None)
        with pytest.raises(RuntimeError, match="reconnect"):
            await old_tool.execute()
    finally:
        await manager.disconnect_all()
    assert (tmp_path / "server.closed").exists()


@pytest.mark.parametrize("action", ["rotate", "remove"])
async def test_environment_reference_change_invalidates_direct_native_client(tmp_path, monkeypatch, action):
    monkeypatch.setenv("ORDINARY_SOURCE", "original-reference-canary")
    client = McpClient("fixture", server_config(tmp_path, {"GITHUB_TOKEN": "${ORDINARY_SOURCE}"}))
    try:
        await client.connect()
        if action == "rotate":
            monkeypatch.setenv("ORDINARY_SOURCE", "rotated-reference-canary")
        else:
            monkeypatch.delenv("ORDINARY_SOURCE")
        with pytest.raises((RuntimeError, ValueError)) as caught:
            await client.call_tool("inspect", {})
        assert "reference-canary" not in str(caught.value)
        assert not (tmp_path / "server.calls").exists()
    finally:
        await client.disconnect()


async def test_auth_token_reference_is_scoped_to_its_named_server(tmp_path, monkeypatch):
    monkeypatch.setenv("ORDINARY_SOURCE", "scoped-auth-reference-canary")
    other = tmp_path / "other"
    other.mkdir()
    manager = McpManager({"first": server_config(tmp_path), "other": server_config(other)})
    manager.set_auth_token("first", "${ORDINARY_SOURCE}")
    try:
        await manager.connect_all()
        first = json.loads((await manager.call_tool("first", "inspect", {})).content)
        second = json.loads((await manager.call_tool("other", "inspect", {})).content)
        assert first["HMN_MCP_AUTH_TOKEN"] == "scoped-auth-reference-canary"
        assert second["HMN_MCP_AUTH_TOKEN"] is None
        assert manager.configs["first"].env == {}
    finally:
        await manager.disconnect_all()


async def test_rotation_during_pending_native_startup_joins_and_rejects_client(tmp_path):
    manager = McpManager({"fixture": server_config(tmp_path, {"STARTUP_STALL": "1"})})
    task = asyncio.create_task(manager.connect_server("fixture"))
    try:
        async with asyncio.timeout(2):
            while not (tmp_path / "server").exists():
                await asyncio.sleep(.01)
        manager.set_auth_token("fixture", "changed-during-startup-canary")
        with pytest.raises(RuntimeError, match="reconnect"):
            await asyncio.wait_for(task, 1)
        assert "fixture" not in manager.clients
        assert (tmp_path / "server.closed").exists()
        assert not [worker for worker in asyncio.all_tasks() if worker.get_name() in {
            "henchman-mcp-session", "henchman-mcp-stderr"}]
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await manager.disconnect_all()


async def test_native_connect_and_disconnect_can_have_different_calling_tasks(tmp_path):
    client = McpClient("fixture", server_config(tmp_path))
    await asyncio.create_task(client.connect())
    assert client.is_connected
    await asyncio.create_task(client.disconnect())
    assert not client.is_connected
    assert (tmp_path / "server.closed").exists()
    assert not [worker for worker in asyncio.all_tasks() if worker.get_name() in {
        "henchman-mcp-session", "henchman-mcp-stderr"}]


async def test_cancelled_disconnect_waits_for_owner_cleanup_before_propagating(tmp_path, monkeypatch):
    client = McpClient("fixture", server_config(tmp_path))
    entered, release = asyncio.Event(), asyncio.Event()
    original = client._open_session

    async def delayed_cleanup():
        entered.set()
        await release.wait()

    async def open_session(stack):
        session = await original(stack)
        stack.push_async_callback(delayed_cleanup)
        return session

    monkeypatch.setattr(client, "_open_session", open_session)
    await client.connect()
    task = asyncio.create_task(client.disconnect())
    try:
        await asyncio.wait_for(entered.wait(), 2)
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert (tmp_path / "server.closed").exists()
        assert not [worker for worker in asyncio.all_tasks() if worker.get_name() in {
            "henchman-mcp-session", "henchman-mcp-stderr"}]
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)


async def test_reference_in_noncredential_named_field_is_redacted_in_native_diagnostics(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("ORDINARY_SOURCE", "diagnostic-reference-private-canary")
    client = McpClient("fixture", server_config(tmp_path, {"PLAIN": "${ORDINARY_SOURCE}", "ECHO_DIAGNOSTIC": "1"}))
    try:
        await client.connect()
    finally:
        await client.disconnect()
    stderr = capsys.readouterr().err
    assert "WARNING:" in stderr
    assert "diagnostic-reference-private-canary" not in stderr


async def test_reference_values_are_injected_once_not_recursively_expanded(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("ORDINARY_SOURCE", "${SECOND_SOURCE}")
    monkeypatch.setenv("SECOND_SOURCE", "must-not-be-injected-canary")
    client = McpClient("fixture", server_config(tmp_path, {"PLAIN": "${ORDINARY_SOURCE}", "ECHO_DIAGNOSTIC": "1"}))
    try:
        await client.connect()
        result = json.loads((await client.call_tool("inspect", {})).content)
        assert result["PLAIN"] == "${SECOND_SOURCE}"
    finally:
        await client.disconnect()
    assert "${SECOND_SOURCE}" not in capsys.readouterr().err


async def test_cancelled_disconnect_waiting_for_startup_lock_still_joins_owner(tmp_path, monkeypatch):
    client = McpClient("fixture", server_config(tmp_path, {"STARTUP_STALL": "1"}))
    entered, release = asyncio.Event(), asyncio.Event()
    original = client._open_session

    async def delayed_cleanup():
        entered.set()
        await release.wait()

    async def open_session(stack):
        stack.push_async_callback(delayed_cleanup)
        return await original(stack)

    monkeypatch.setattr(client, "_open_session", open_session)
    startup = asyncio.create_task(client.connect())
    closing = None
    try:
        async with asyncio.timeout(2):
            while not (tmp_path / "server").exists():
                await asyncio.sleep(.01)
        closing = asyncio.create_task(client.disconnect())
        await asyncio.wait_for(entered.wait(), 2)
        closing.cancel()
        await asyncio.sleep(0)
        assert not closing.done()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await closing
        await asyncio.gather(startup, return_exceptions=True)
        assert not [worker for worker in asyncio.all_tasks() if worker.get_name() in {
            "henchman-mcp-session", "henchman-mcp-stderr"}]
    finally:
        release.set()
        startup.cancel()
        await asyncio.gather(startup, *((closing,) if closing is not None else ()), return_exceptions=True)
        await client.disconnect()


async def test_clear_does_not_restore_configured_auth_fallback_on_reconnect(tmp_path):
    config = server_config(tmp_path, {"HMN_MCP_AUTH_TOKEN": "configured-auth-canary"})
    manager = McpManager({"fixture": config})
    try:
        await manager.connect_server("fixture")
        manager.clear_auth_token("fixture")
        await manager.connect_server("fixture")
        result = json.loads((await manager.call_tool("fixture", "inspect", {})).content)
        assert result["HMN_MCP_AUTH_TOKEN"] is None
        assert config.env == {"HMN_MCP_AUTH_TOKEN": "configured-auth-canary"}
    finally:
        await manager.disconnect_all()


async def test_manager_shutdown_joins_other_servers_before_propagating_cancellation(tmp_path, monkeypatch):
    second = tmp_path / "second"
    second.mkdir()
    manager = McpManager({"first": server_config(tmp_path), "second": server_config(second)})
    await manager.connect_all()
    cancellation = asyncio.CancelledError("injected shutdown cancellation")
    closed = []
    for client in manager.clients.values():
        original = client.disconnect

        async def disconnect(original=original):
            await original()
            closed.append(True)
            if len(closed) == 1:
                raise cancellation

        monkeypatch.setattr(client, "disconnect", disconnect)
    try:
        with pytest.raises(asyncio.CancelledError) as caught:
            await manager.disconnect_all()
        assert caught.value is cancellation
        assert len(closed) == 2
        assert (tmp_path / "server.closed").exists()
        assert (second / "server.closed").exists()
        assert not [worker for worker in asyncio.all_tasks() if worker.get_name() in {
            "henchman-mcp-session", "henchman-mcp-stderr"}]
    finally:
        await manager.disconnect_all()


async def test_failed_connection_logs_do_not_echo_effective_reference_credentials(tmp_path, monkeypatch, caplog):
    monkeypatch.setenv("ORDINARY_SOURCE", "failure-protocol-private-canary")
    manager = McpManager({"fixture": server_config(tmp_path, {"PROTOCOL": "${ORDINARY_SOURCE}"})})
    await manager.connect_all()
    assert not manager.clients
    assert "Failed to connect" in caplog.text
    assert "failure-protocol-private-canary" not in caplog.text
    assert (tmp_path / "server.closed").exists()


async def test_caller_cancellation_remains_cancellation_when_credentials_change_too(tmp_path):
    manager = McpManager({"fixture": server_config(tmp_path, {"STARTUP_STALL": "1"})})
    task = asyncio.create_task(manager.connect_server("fixture"))
    try:
        async with asyncio.timeout(2):
            while not (tmp_path / "server").exists():
                await asyncio.sleep(.01)
        task.cancel("caller interruption")
        manager.set_auth_token("fixture", "simultaneous-rotation-canary")
        with pytest.raises(asyncio.CancelledError, match="caller interruption"):
            await task
        assert (tmp_path / "server.closed").exists()
        assert not manager.clients
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await manager.disconnect_all()


async def test_legacy_public_config_remains_usable_with_scoped_auth(tmp_path):
    from henchman.mcp import McpServerConfig as LegacyConfig

    config = LegacyConfig(**server_config(tmp_path).model_dump())
    manager = McpManager({"fixture": config})
    manager.set_auth_token("fixture", "legacy-scoped-auth-canary")
    try:
        await manager.connect_server("fixture")
        result = json.loads((await manager.call_tool("fixture", "inspect", {})).content)
        assert result["HMN_MCP_AUTH_TOKEN"] == "legacy-scoped-auth-canary"
        assert config.env == {}
    finally:
        await manager.disconnect_all()


@pytest.mark.parametrize("field", ["command", "args", "trusted"])
async def test_same_environment_connection_identity_changes_reject_retained_dispatch(tmp_path, field):
    manager = McpManager({"fixture": server_config(tmp_path)})
    try:
        await manager.connect_server("fixture")
        retained = manager.get_all_tools()[0]
        config = manager.configs["fixture"]
        if field == "command":
            config.command = "different-unlaunched-command"
        elif field == "args":
            config.args.append("different-unlaunched-argument")
        else:
            config.trusted = True
        with pytest.raises(RuntimeError, match="reconnect"):
            await retained.execute()
        with pytest.raises(RuntimeError, match="reconnect"):
            await manager.call_tool("fixture", "inspect", {})
        assert not (tmp_path / "server.calls").exists()
    finally:
        await manager.disconnect_all()


@pytest.mark.parametrize("failure", ["error", "cancel"])
async def test_post_start_owner_failure_never_emits_unretrieved_raw_diagnostics(tmp_path, failure):
    loop = asyncio.get_running_loop()
    previous = loop.get_exception_handler()
    unhandled = []
    loop.set_exception_handler(lambda _loop, context: unhandled.append(context))

    async def connect_and_release():
        client = McpClient("fixture", server_config(tmp_path))
        original_open = client._open_session

        async def open_session(stack):
            session = await original_open(stack)
            original_wait = client._stop.wait

            async def fail_after_stop():
                await original_wait()
                raise RuntimeError("late-owner-private-canary")

            if failure == "error":
                client._stop.wait = fail_after_stop
            return session

        client._open_session = open_session
        await client.connect()
        assert client._owner_task is not None
        if failure == "cancel":
            client._owner_task.cancel("cancelled native owner")
        else:
            client._stop.set()
        async with asyncio.timeout(2):
            while not client._owner_task.done():
                await asyncio.sleep(.01)
        return weakref.ref(client)

    try:
        reference = await connect_and_release()
        gc.collect()
        await asyncio.sleep(0)
        gc.collect()
        assert not unhandled
        assert reference() is None
        assert (tmp_path / "server.closed").exists()
    finally:
        loop.set_exception_handler(previous)


async def test_observed_post_start_owner_failure_still_propagates_on_disconnect(tmp_path):
    client = McpClient("fixture", server_config(tmp_path))
    original_run = client._run_session
    failure = RuntimeError("retained-owner-failure-canary")

    async def run(ready):
        await original_run(ready)
        raise failure

    client._run_session = run
    await client.connect()
    client._stop.set()
    assert client._owner_task is not None
    async with asyncio.timeout(2):
        while not client._owner_task.done():
            await asyncio.sleep(.01)
    await asyncio.sleep(0)
    with pytest.raises(RuntimeError) as caught:
        await client.disconnect()
    assert caught.value is failure
    assert (tmp_path / "server.closed").exists()
    assert client._owner_task is None
