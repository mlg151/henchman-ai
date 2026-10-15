"""Tests for Tier 6 LSP and scheduling builtin tools."""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from henchman.cli.tool_manager import ToolManager


def _write_fake_lsp_server(path: Path) -> None:
    """Write a minimal stdio JSON-RPC server that behaves like an LSP server."""

    path.write_text(
        """
import json
import sys


def read_message():
    headers = {}
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            return None
        if line in (b"\\r\\n", b"\\n"):
            break
        name, value = line.decode("utf-8").split(":", 1)
        headers[name.strip().lower()] = value.strip()
    length = int(headers.get("content-length", "0"))
    body = sys.stdin.buffer.read(length)
    return json.loads(body.decode("utf-8"))


def send_message(payload):
    body = json.dumps(payload).encode("utf-8")
    sys.stdout.buffer.write(f"Content-Length: {len(body)}\\r\\n\\r\\n".encode("utf-8"))
    sys.stdout.buffer.write(body)
    sys.stdout.buffer.flush()


while True:
    message = read_message()
    if message is None:
        break
    method = message.get("method")
    message_id = message.get("id")
    params = message.get("params", {})

    if method == "initialize":
        send_message({"jsonrpc": "2.0", "id": message_id, "result": {"capabilities": {}}})
    elif method == "initialized":
        continue
    elif method == "workspace/symbol":
        send_message(
            {
                "jsonrpc": "2.0",
                "id": message_id,
                "result": [{"name": params.get("query", "unknown"), "kind": 12}],
            }
        )
    elif method == "shutdown":
        send_message({"jsonrpc": "2.0", "id": message_id, "result": None})
    elif method == "exit":
        break
    else:
        send_message({"jsonrpc": "2.0", "id": message_id, "result": {"echo": params}})
        """.strip()
        + "\n",
        encoding="utf-8",
    )


def test_builtin_surface_includes_tier6_lsp_and_schedule_tools() -> None:
    """The builtin surface should expose Tier 6 LSP and scheduling tools."""

    import henchman.tools.builtins as builtins_mod

    assert {"LSPTool", "ScheduleCronTool"} <= set(builtins_mod.__all__)

    def _instantiate(tool_class: object) -> object:
        if tool_class is builtins_mod.ShellTool:
            return builtins_mod.ShellTool(default_timeout=60)
        if tool_class is builtins_mod.RagSearchTool:
            from unittest.mock import MagicMock

            return builtins_mod.RagSearchTool(store=MagicMock())
        return tool_class()

    names = {_instantiate(tool_class).name for tool_class in builtins_mod.iter_available_builtin_tool_classes()}

    assert {"lsp", "schedule_cron"} <= names

    schedule_tool = builtins_mod.ScheduleCronTool()
    assert "metadata" in schedule_tool.description.lower()
    assert "no background runner" in schedule_tool.description.lower()


@pytest.mark.anyio
async def test_lsp_tool_registers_starts_requests_and_stops_servers(tmp_path: Path) -> None:
    """LSPTool should manage a generic stdio language server lifecycle."""

    from henchman.lsp import LspService

    server_script = tmp_path / "fake_lsp_server.py"
    _write_fake_lsp_server(server_script)

    manager = ToolManager()
    manager.bind_runtime(project_root=tmp_path)
    manager.register_builtin_tools()

    registered = await manager.registry.execute(
        "lsp",
        {
            "action": "register",
            "server": "fake",
            "command": sys.executable,
            "args": [str(server_script)],
            "language": "python",
        },
    )
    started = await manager.registry.execute("lsp", {"action": "start", "server": "fake"})
    requested = await manager.registry.execute(
        "lsp",
        {
            "action": "request",
            "server": "fake",
            "method": "workspace/symbol",
            "params": {"query": "Widget"},
        },
    )
    listed = await manager.registry.execute("lsp", {"action": "list"})
    stopped = await manager.registry.execute("lsp", {"action": "stop", "server": "fake"})

    service = LspService(project_root=tmp_path)

    assert registered.success is True
    assert started.success is True
    assert requested.success is True
    assert listed.success is True
    assert stopped.success is True
    assert "Widget" in requested.content
    assert "fake" in listed.content
    assert service.list_servers()[0].server == "fake"
    assert (tmp_path / ".henchman" / "lsp" / "servers.json").exists()


@pytest.mark.anyio
async def test_schedule_cron_tool_persists_and_updates_schedules(tmp_path: Path) -> None:
    """ScheduleCronTool should persist cron schedules and update enabled state."""

    from henchman.advanced import CronScheduleService

    manager = ToolManager()
    manager.bind_runtime(project_root=tmp_path)
    manager.register_builtin_tools()

    created = await manager.registry.execute(
        "schedule_cron",
        {
            "action": "create",
            "title": "quarter-hour",
            "cron": "*/15 * * * *",
            "argv": [sys.executable, "-c", "print('ok')"],
        },
    )

    assert created.success is True

    service = CronScheduleService(project_root=tmp_path)
    schedule = service.list_schedules()[0]

    paused = await manager.registry.execute(
        "schedule_cron",
        {"action": "pause", "schedule_id": schedule.schedule_id},
    )
    resumed = await manager.registry.execute(
        "schedule_cron",
        {"action": "resume", "schedule_id": schedule.schedule_id},
    )
    listed = await manager.registry.execute("schedule_cron", {"action": "list"})

    next_run = service.next_run_for(
        "*/15 * * * *",
        after=datetime(2026, 1, 1, 12, 7, tzinfo=UTC),
    )

    assert paused.success is True
    assert resumed.success is True
    assert listed.success is True
    assert "metadata only" in created.content.lower()
    assert "quarter-hour" in listed.content
    assert "metadata only" in listed.content.lower()
    assert next_run == datetime(2026, 1, 1, 12, 15, tzinfo=UTC)
    assert (tmp_path / ".henchman" / "schedules" / "index.json").exists()
