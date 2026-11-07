"""Independent JSON-RPC fixtures exercise discovery and typed MCP contracts."""

from __future__ import annotations

import asyncio
import copy
import json
import sys
from pathlib import Path

import pytest

from henchman.config.schema import McpServerConfig
from henchman.mcp.client import McpClient
from henchman.mcp.manager import McpManager
from henchman.tools.contracts import SchemaContractError
from henchman.tools.registry import ToolRegistry
from henchman.tools.scoped_registry import ScopedToolRegistry

SERVER = r'''
import json,sys
state_path, transcript = sys.argv[1:]
for line in sys.stdin:
    request=json.loads(line)
    with open(transcript,'a',encoding='utf-8') as output:
        output.write(json.dumps(request)+'\n')
    if 'id' not in request:
        continue
    with open(state_path,encoding='utf-8') as source:
        state=json.load(source)
    method=request['method']
    if method=='initialize':
        result={'protocolVersion':'2025-11-25','capabilities':{'tools':{'listChanged':True}},
                'serverInfo':{'name':'independent-catalog-fixture','version':'1'}}
    elif method=='tools/list':
        cursor=request.get('params',{}).get('cursor','')
        if cursor in state.get('stall_cursors',[]):
            continue
        result=state['pages'][cursor]
    elif method=='tools/call':
        result=state.get('results',{}).get(request['params']['name'],
                {'content':[{'type':'text','text':'called'}],'isError':False})
    else:
        raise RuntimeError(method)
    print(json.dumps({'jsonrpc':'2.0','id':request['id'],'result':result}),flush=True)
'''


def declaration(name: str, *, description: str = "fixture", output_schema=None) -> dict:
    tool = {"name": name, "description": description,
            "inputSchema": {"type": "object", "properties": {"value": {"type": ["string", "null"]}},
                            "additionalProperties": False}}
    if output_schema is not None:
        tool["outputSchema"] = output_schema
    return tool


class Fixture:
    def __init__(self, path: Path, state: dict) -> None:
        self.state_path = path / "catalog-state.json"
        self.transcript = path / "catalog-wire.jsonl"
        self.write(state)
        self.config = McpServerConfig(command=sys.executable,
                                      args=["-I", "-u", "-c", SERVER, str(self.state_path), str(self.transcript)])
        self.client = McpClient("fixture", self.config)

    def write(self, state: dict) -> None:
        self.state_path.write_text(json.dumps(state))

    def requests(self, method: str) -> list[dict]:
        if not self.transcript.exists():
            return []
        return [item for line in self.transcript.read_text().splitlines()
                if (item := json.loads(line))["method"] == method]


def state(*tools: dict, results: dict | None = None) -> dict:
    return {"pages": {"": {"tools": list(tools)}}, "results": results or {}}


async def test_native_discovery_follows_pages_and_returns_detached_snapshots(tmp_path: Path) -> None:
    fixture = Fixture(tmp_path, {"pages": {
        "": {"tools": [declaration("one")], "nextCursor": "page-two"},
        "page-two": {"tools": [declaration("two")]},
    }})
    try:
        await fixture.client.connect()
        assert [tool.name for tool in fixture.client.get_tools()] == ["one", "two"]
        tools = fixture.client.get_tools()
        tools[0].input_schema["properties"]["value"]["type"] = "integer"
        tools.clear()
        assert len(fixture.client.get_tools()) == 2
        await fixture.client.call_tool("one", {"value": "preserved"})
        assert fixture.requests("tools/list")[1]["params"]["cursor"] == "page-two"
    finally:
        await fixture.client.disconnect()


@pytest.mark.parametrize("bad_pages", [
    {"": {"tools": [declaration("new")], "nextCursor": "again"},
     "again": {"tools": [declaration("other")], "nextCursor": "again"}},
    {"": {"tools": [declaration("same")], "nextCursor": "again"},
     "again": {"tools": [declaration("same")]}},
    {"": {"tools": [declaration("new")], "nextCursor": "again"}, "again": {"tools": [{"name": "bad"}]}},
    {"": {"tools": [{**declaration("bad"), "inputSchema": {"$ref": "https://invalid.example/schema"}}]}},
])
async def test_failed_discovery_preserves_complete_previous_catalog(tmp_path: Path, bad_pages: dict) -> None:
    fixture = Fixture(tmp_path, state(declaration("kept")))
    try:
        await fixture.client.connect()
        before = copy.deepcopy(fixture.client.get_tools())
        fixture.write({"pages": bad_pages})
        with pytest.raises(SchemaContractError):
            await fixture.client.discover_tools()
        assert fixture.client.get_tools() == before
    finally:
        await fixture.client.disconnect()


async def test_native_args_rejected_before_dispatch_and_sdk_validator_is_replaced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import jsonschema

    schema = {"type": "object", "properties": {"answer": {"type": "integer"}}, "required": ["answer"]}
    fixture = Fixture(tmp_path, state(declaration("checked", output_schema=schema), results={
        "checked": {"content": [{"type": "text", "text": "ok"}], "structuredContent": {"answer": 42}},
    }))

    def unsafe_validation(*_args, **_kwargs):
        raise AssertionError("SDK bare jsonschema validation must never execute")

    monkeypatch.setattr(jsonschema, "validate", unsafe_validation)
    try:
        await fixture.client.connect()
        with pytest.raises(SchemaContractError) as error:
            await fixture.client.call_tool("checked", {"unknown": "rejected-input-canary"})
        assert "rejected-input-canary" not in str(error.value)
        assert not fixture.requests("tools/call")
        result = await fixture.client.call_tool("checked", {"value": None})
        assert result.structured_content == {"answer": 42}
        assert result.structured_content_present is True
        assert fixture.requests("tools/call")[0]["params"]["arguments"] == {"value": None}
    finally:
        await fixture.client.disconnect()


@pytest.mark.parametrize("structured", ["missing", None, {"answer": 42}])
async def test_native_typed_results_preserve_content_and_structured_presence(tmp_path: Path, structured) -> None:
    blocks = [{"type": "text", "text": "readable"},
              {"type": "image", "data": "aGVsbG8=", "mimeType": "image/png"},
              {"type": "audio", "data": "aGVsbG8=", "mimeType": "audio/wav"},
              {"type": "resource", "resource": {"uri": "file:///fixture", "text": "embedded"}},
              {"type": "resource_link", "uri": "file:///linked", "name": "linked"}]
    result = {"content": blocks, "isError": False, "_meta": {"fixture": "retained"}}
    if structured != "missing":
        result["structuredContent"] = structured
    tool = declaration("typed")
    tool["annotations"] = {"readOnlyHint": True, "destructiveHint": False}
    fixture = Fixture(tmp_path, state(tool, results={"typed": result}))
    try:
        await fixture.client.connect()
        definition = fixture.client.get_tools()[0]
        assert definition.annotations == tool["annotations"]
        actual = await fixture.client.call_tool("typed", {})
        assert [block["type"] for block in actual.content_blocks] == [block["type"] for block in blocks]
        assert actual.structured_content_present is (structured != "missing")
        assert actual.structured_content == (None if structured == "missing" else structured)
        assert actual.metadata == {"fixture": "retained"}
        assert "readable" in actual.content
    finally:
        await fixture.client.disconnect()


@pytest.mark.parametrize("result", [
    {"content": [], "structuredContent": {"answer": "rejected-output-canary"}},
    {"content": []},
    {"content": [], "structuredContent": ["unsupported-scalar-canary"]},
])
async def test_native_output_contract_failures_are_value_free(tmp_path: Path, result: dict) -> None:
    fixture = Fixture(tmp_path, state(declaration("checked", output_schema={
        "type": "object", "properties": {"answer": {"type": "integer"}}, "required": ["answer"],
    }), results={"checked": result}))
    try:
        await fixture.client.connect()
        with pytest.raises(SchemaContractError) as caught:
            await fixture.client.call_tool("checked", {})
        assert "rejected-output-canary" not in str(caught.value)
        assert "unsupported-scalar-canary" not in str(caught.value)
    finally:
        await fixture.client.disconnect()


async def test_refresh_updates_parent_catalog_without_widening_scope_or_reviving_wrappers(tmp_path: Path) -> None:
    fixture = Fixture(tmp_path, state(declaration("allowed"), declaration("removed")))
    manager = McpManager({"fixture": fixture.config})
    parent = ToolRegistry()
    try:
        await manager.connect_server("fixture")
        manager.bind_registry(parent)
        scoped = ScopedToolRegistry(parent, ["mcp_fixture_allowed", "mcp_fixture_removed"])
        stale = parent.get("mcp_fixture_allowed")
        registration = parent._tool_registrations["mcp_fixture_allowed"]
        fixture.write(state(declaration("allowed", description="replacement"), declaration("new")))
        await manager.refresh_server("fixture")
        assert set(parent.list_tools()) == {"mcp_fixture_allowed", "mcp_fixture_new"}
        assert scoped.list_tools() == ["mcp_fixture_allowed"]
        assert "replacement" in scoped.get("mcp_fixture_allowed").description
        assert parent._tool_registrations["mcp_fixture_allowed"] != registration
        with pytest.raises(RuntimeError, match="catalog"):
            await stale.execute()
        assert not fixture.requests("tools/call")
    finally:
        await manager.disconnect_all()


async def test_cancelled_pagination_keeps_previous_catalog(tmp_path: Path) -> None:
    fixture = Fixture(tmp_path, state(declaration("kept")))
    try:
        await fixture.client.connect()
        fixture.write({"pages": {"": {"tools": [declaration("new")], "nextCursor": "stall"}},
                       "stall_cursors": ["stall"]})
        refresh = asyncio.create_task(fixture.client.discover_tools())
        async with asyncio.timeout(5):
            while len(fixture.requests("tools/list")) < 3:
                await asyncio.sleep(0.01)
        refresh.cancel()
        with pytest.raises(asyncio.CancelledError):
            await refresh
        assert [tool.name for tool in fixture.client.get_tools()] == ["kept"]
    finally:
        await fixture.client.disconnect()


@pytest.mark.parametrize("limit", ["pages", "tools", "bytes"])
async def test_discovery_limits_fail_without_partial_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, limit: str,
) -> None:
    from henchman.mcp import client as client_module

    fixture = Fixture(tmp_path, state(declaration("kept")))
    try:
        await fixture.client.connect()
        if limit == "pages":
            monkeypatch.setattr(client_module, "MAX_DISCOVERY_PAGES", 1)
            new = {"pages": {"": {"tools": [declaration("new")], "nextCursor": "more"},
                             "more": {"tools": []}}}
        elif limit == "tools":
            monkeypatch.setattr(client_module, "MAX_DISCOVERY_TOOLS", 1)
            new = state(declaration("new"), declaration("second"))
        else:
            monkeypatch.setattr(client_module, "MAX_CATALOG_BYTES", 256)
            new = state(declaration("new", description="x" * 512))
        fixture.write(new)
        with pytest.raises(SchemaContractError):
            await fixture.client.discover_tools()
        assert [tool.name for tool in fixture.client.get_tools()] == ["kept"]
    finally:
        await fixture.client.disconnect()


@pytest.mark.parametrize("payload", [
    {"content": [{"type": "text", "text": "x" * (1024 * 1024 + 1)}]},
    {"content": [{"type": "text", "text": "x"}] * 257},
])
async def test_result_bounds_reject_oversized_payloads(tmp_path: Path, payload: dict) -> None:
    fixture = Fixture(tmp_path, state(declaration("bounded"), results={"bounded": payload}))
    try:
        await fixture.client.connect()
        with pytest.raises(SchemaContractError):
            await fixture.client.call_tool("bounded", {})
    finally:
        await fixture.client.disconnect()


async def test_nested_local_contract_null_output_and_error_fidelity(tmp_path: Path) -> None:
    from henchman.mcp.tool import McpTool
    from henchman.tools.base import ToolKind

    tool = declaration("typed", output_schema={"type": ["object", "null"]})
    tool["inputSchema"] = {"type": "object", "$defs": {"item": {"anyOf": [{"type": "string"}, {"type": "null"}]}},
                           "properties": {"values": {"type": "array", "items": {"$ref": "#/$defs/item"}}},
                           "required": ["values"]}
    tool["annotations"] = {"readOnlyHint": True}
    fixture = Fixture(tmp_path, state(tool, results={"typed": {"content": [], "structuredContent": None}}))
    try:
        await fixture.client.connect()
        wrapper = McpTool(fixture.client.get_tools()[0], fixture.client, "fixture")
        assert wrapper.execution_kind({}) is ToolKind.NETWORK
        result = await wrapper.execute(values=["kept", None])
        assert result.structured_content_present and result.structured_content is None
        with pytest.raises(SchemaContractError):
            await wrapper.execute(values=[123])
        assert len(fixture.requests("tools/call")) == 1
        fixture.write(state(tool, results={"typed": {"content": [{"type": "text", "text": "server failed"}],
                                                      "structuredContent": {"diagnostic": True}, "isError": True}}))
        result = await wrapper.execute(values=[])
        assert not result.success and result.error == "server failed"
        assert result.content_blocks[0] == {"type": "text", "text": "server failed"}
        assert result.structured_content == {"diagnostic": True}
    finally:
        await fixture.client.disconnect()


async def test_failed_manager_refresh_retains_registered_wrappers_and_scope(tmp_path: Path) -> None:
    fixture = Fixture(tmp_path, state(declaration("kept")))
    manager = McpManager({"fixture": fixture.config})
    parent = ToolRegistry()
    try:
        await manager.connect_server("fixture")
        manager.bind_registry(parent)
        original = parent.get("mcp_fixture_kept")
        registration = parent._tool_registrations["mcp_fixture_kept"]
        fixture.write({"pages": {"": {"tools": [declaration("new")], "nextCursor": "bad"},
                                 "bad": {"tools": [{"name": "invalid"}]}}})
        with pytest.raises(SchemaContractError):
            await manager.refresh_server("fixture")
        assert parent.get("mcp_fixture_kept") is original
        assert parent._tool_registrations["mcp_fixture_kept"] == registration
        assert (await original.execute()).success
        with pytest.raises(ValueError, match="scoped"):
            manager.bind_registry(ScopedToolRegistry(parent, []))
    finally:
        await manager.disconnect_all()


@pytest.mark.parametrize("surface", ["tool", "command"])
async def test_public_refresh_surfaces_update_native_catalog(tmp_path: Path, surface: str) -> None:
    from io import StringIO

    from rich.console import Console

    from henchman.cli.commands import CommandContext
    from henchman.cli.commands.mcp import McpCommand
    from henchman.tools.base import ToolKind
    from henchman.tools.builtins.tier6_tools import MCPTool

    fixture = Fixture(tmp_path, state(declaration("old")))
    manager = McpManager({"fixture": fixture.config})
    registry = ToolRegistry()
    try:
        await manager.connect_server("fixture")
        manager.bind_registry(registry)
        fixture.write(state(declaration("new")))
        if surface == "tool":
            tool = MCPTool()
            tool.bind_runtime(project_root=tmp_path, mcp_manager=manager)
            assert tool.execution_kind({"action": "refresh"}) is ToolKind.NETWORK
            result = await tool.execute(action="refresh", server="fixture")
            assert result.success
            assert "refreshed" in result.content.lower()
        else:
            buffer = StringIO()
            context = CommandContext(console=Console(file=buffer), args=["refresh", "fixture"])
            context.mcp_manager = manager
            await McpCommand().execute(context)
            assert "refreshed" in buffer.getvalue().lower()
        assert registry.list_tools() == ["mcp_fixture_new"]
    finally:
        await manager.disconnect_all()


async def test_refresh_during_approval_cannot_dispatch_or_reuse_old_tool_grant(tmp_path: Path) -> None:
    fixture = Fixture(tmp_path, state(declaration("checked")))
    manager = McpManager({"fixture": fixture.config})
    registry = ToolRegistry()
    approvals = []

    async def approve(request):
        approvals.append(request)
        fixture.write(state(declaration("checked", description="changed during approval")))
        await manager.refresh_server("fixture")
        return True

    registry.set_confirmation_handler(approve)
    try:
        await manager.connect_server("fixture")
        manager.bind_registry(registry)
        result = await registry.execute("mcp_fixture_checked", {})
        assert not result.success
        assert len(approvals) == 1
        assert not fixture.requests("tools/call")
    finally:
        await manager.disconnect_all()


async def test_refresh_name_collision_leaves_prior_catalog_and_registrations_intact(tmp_path: Path) -> None:
    from henchman.tools.base import Tool, ToolResult

    class LocalTool(Tool):
        name = "mcp_fixture_new"
        description = "Local ownership"

        async def execute(self, **_params) -> ToolResult:
            return ToolResult("local")

    fixture = Fixture(tmp_path, state(declaration("kept")))
    manager = McpManager({"fixture": fixture.config})
    registry = ToolRegistry()
    local = LocalTool()
    registry.register(local)
    try:
        await manager.connect_server("fixture")
        manager.bind_registry(registry)
        previous = registry.get("mcp_fixture_kept")
        fixture.write(state(declaration("new")))
        with pytest.raises(ValueError, match="conflict"):
            await manager.refresh_server("fixture")
        assert registry.get("mcp_fixture_new") is local
        assert registry.get("mcp_fixture_kept") is previous
        assert [tool.name for tool in manager.discover_tools("fixture")] == ["kept"]
        assert (await previous.execute()).success
    finally:
        await manager.disconnect_all()


async def test_removed_wrapper_cannot_dispatch_after_refresh(tmp_path: Path) -> None:
    fixture = Fixture(tmp_path, state(declaration("removed")))
    manager = McpManager({"fixture": fixture.config})
    try:
        await manager.connect_server("fixture")
        stale = manager.get_all_tools()[0]
        fixture.write(state())
        await manager.refresh_server("fixture")
        with pytest.raises(RuntimeError, match="catalog"):
            await stale.execute()
        assert not fixture.requests("tools/call")
    finally:
        await manager.disconnect_all()
