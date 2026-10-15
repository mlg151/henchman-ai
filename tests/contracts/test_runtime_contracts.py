"""Contract tests for core runtime and adapter payloads."""

from __future__ import annotations

import pytest

from henchman.api.endpoints.chat import ChatMessage, _convert_chat_message_to_internal
from henchman.core.event_payloads import (
    AgentCompletedPayload,
    FinishedPayload,
    ToolCallResultPayload,
)
from henchman.core.events import AgentEvent, EventType
from henchman.mcp.client import McpToolDefinition, McpToolResult
from henchman.mcp.tool import _build_tool_result
from henchman.providers.base import FinishReason, Message, StreamChunk, ToolCall, ToolDeclaration
from henchman.tools.base import Tool, ToolKind, ToolResult
from henchman.tools.registry import ToolRegistry
from tests.contracts.helpers import assert_contract_matches, serialize_contract_value


class _EchoReadTool(Tool):
    """Minimal read-only tool used for contract tests."""

    @property
    def name(self) -> str:
        return "echo_read"

    @property
    def description(self) -> str:
        return "Return the provided text"

    @property
    def parameters(self) -> dict[str, object]:
        return {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        }

    async def execute(self, **params: object) -> ToolResult:
        return ToolResult(content=str(params["text"]))


class _EchoWriteTool(_EchoReadTool):
    """Minimal write tool used to exercise plan-mode contracts."""

    @property
    def name(self) -> str:
        return "echo_write"

    @property
    def kind(self) -> ToolKind:
        return ToolKind.WRITE


def test_provider_runtime_payloads_match_contracts(contract_suite) -> None:
    """Serialized provider/runtime payloads should satisfy their contracts."""
    tool_call = ToolCall(id="call-1", name="read_file", arguments={"path": "README.md"})
    declaration = ToolDeclaration(
        name="read_file",
        description="Read a file",
        parameters={"type": "object", "properties": {"path": {"type": "string"}}},
    )
    message = Message(
        role="assistant",
        content="hello",
        tool_calls=[tool_call],
        tool_call_id=None,
        reasoning_content=None,
    )
    stream_chunk = StreamChunk(
        content="partial",
        tool_calls=[tool_call],
        finish_reason=FinishReason.STOP,
        thinking=None,
        usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    )
    event = AgentEvent(
        type=EventType.FINISHED,
        data=FinishedPayload(finish_reason="stop", usage={}),
        source_agent="agent-1",
    )
    tool_result = ToolResult(content="done", success=True, display=None, error=None)
    mcp_definition = McpToolDefinition(
        name="search",
        description="Search a repository",
        input_schema={"type": "object", "properties": {"query": {"type": "string"}}},
    )
    mcp_result = McpToolResult(content="ok", is_error=False)

    assert_contract_matches(
        payload=serialize_contract_value(tool_call),
        schema_name="runtime/tool_call",
        contract_suite=contract_suite,
    )
    assert_contract_matches(
        payload=serialize_contract_value(declaration),
        schema_name="runtime/tool_declaration",
        contract_suite=contract_suite,
    )
    assert_contract_matches(
        payload=serialize_contract_value(message),
        schema_name="runtime/message",
        contract_suite=contract_suite,
    )
    assert_contract_matches(
        payload=serialize_contract_value(stream_chunk),
        schema_name="runtime/stream_chunk",
        contract_suite=contract_suite,
    )
    assert_contract_matches(
        payload=serialize_contract_value(event),
        schema_name="runtime/agent_event",
        contract_suite=contract_suite,
    )
    assert_contract_matches(
        payload=serialize_contract_value(tool_result),
        schema_name="runtime/tool_result",
        contract_suite=contract_suite,
    )
    assert_contract_matches(
        payload=serialize_contract_value(mcp_definition),
        schema_name="runtime/mcp_tool_definition",
        contract_suite=contract_suite,
    )
    assert_contract_matches(
        payload=serialize_contract_value(mcp_result),
        schema_name="runtime/mcp_tool_result",
        contract_suite=contract_suite,
    )


def test_agent_event_specific_types_match_contracts(contract_suite) -> None:
    """Detailed verification of different AgentEvent data payloads."""
    # 1. Valid AGENT_COMPLETED
    completed = AgentEvent(
        type=EventType.AGENT_COMPLETED,
        data=AgentCompletedPayload(agent="coder", status="completed", summary="done"),
        source_agent="orchestrator",
    )
    assert_contract_matches(
        payload=serialize_contract_value(completed),
        schema_name="runtime/agent_event",
        contract_suite=contract_suite,
    )

    # 2. Invalid AGENT_COMPLETED (missing summary)
    # Using raw instantiation here to test schema validation against invalid data
    invalid_completed = AgentEvent(
        type=EventType.AGENT_COMPLETED,
        data={"agent": "coder", "status": "completed"},
        source_agent="orchestrator",
    )
    with pytest.raises(AssertionError):
        assert_contract_matches(
            payload=serialize_contract_value(invalid_completed),
            schema_name="runtime/agent_event",
            contract_suite=contract_suite,
        )

    # 3. Valid TOOL_CALL_RESULT
    tc_result = AgentEvent(
        type=EventType.TOOL_CALL_RESULT,
        data=ToolCallResultPayload(
            tool_call_id="call-1",
            tool_name="read_file",
            result="preview",
            success=True,
        ),
        source_agent="agent-1",
    )
    assert_contract_matches(
        payload=serialize_contract_value(tc_result),
        schema_name="runtime/agent_event",
        contract_suite=contract_suite,
    )

    # 4. Valid ERROR
    error = AgentEvent(type=EventType.ERROR, data="Oops", source_agent="agent-1")
    assert_contract_matches(
        payload=serialize_contract_value(error),
        schema_name="runtime/agent_event",
        contract_suite=contract_suite,
    )

    # 5. Invalid ERROR (object instead of string)
    invalid_error = AgentEvent(type=EventType.ERROR, data={"msg": "Oops"}, source_agent="agent-1")
    with pytest.raises(AssertionError):
        assert_contract_matches(
            payload=serialize_contract_value(invalid_error),
            schema_name="runtime/agent_event",
            contract_suite=contract_suite,
        )


def test_tool_declaration_adapter_matches_contract(contract_suite) -> None:
    """Tool declarations emitted for model providers should satisfy the contract."""
    declaration = _EchoReadTool().to_declaration()

    assert_contract_matches(
        payload=serialize_contract_value(declaration),
        schema_name="runtime/tool_declaration",
        contract_suite=contract_suite,
    )


def test_chat_message_adapter_matches_message_contract(contract_suite) -> None:
    """ChatMessage to internal Message adaptation should preserve the message contract."""
    message = _convert_chat_message_to_internal(
        ChatMessage(
            role="assistant",
            content="hello",
            tool_calls=[{"id": "call-1", "name": "read_file", "arguments": {"path": "README.md"}}],
        ),
    )

    assert_contract_matches(
        payload=serialize_contract_value(message),
        schema_name="runtime/message",
        contract_suite=contract_suite,
    )


def test_mcp_tool_result_adapter_matches_tool_result_contract(contract_suite) -> None:
    """MCP tool-call results should normalize into the shared ToolResult contract."""
    tool_result = _build_tool_result(McpToolResult(content="missing", is_error=True))

    assert_contract_matches(
        payload=serialize_contract_value(tool_result),
        schema_name="runtime/tool_result",
        contract_suite=contract_suite,
    )


@pytest.mark.anyio
async def test_registry_missing_tool_result_matches_contract(contract_suite) -> None:
    """Missing tools should still surface a contract-compliant ToolResult."""
    registry = ToolRegistry()

    result = await registry.execute("missing_tool", {})

    assert_contract_matches(
        payload=serialize_contract_value(result),
        schema_name="runtime/tool_result",
        contract_suite=contract_suite,
    )


@pytest.mark.anyio
async def test_registry_plan_mode_denial_matches_contract(contract_suite) -> None:
    """Plan mode should deny write tools with a contract-compliant ToolResult."""
    registry = ToolRegistry()
    registry.register(_EchoWriteTool())
    registry.set_plan_mode(enabled=True)

    result = await registry.execute("echo_write", {"text": "hello"})

    assert_contract_matches(
        payload=serialize_contract_value(result),
        schema_name="runtime/tool_result",
        contract_suite=contract_suite,
    )
