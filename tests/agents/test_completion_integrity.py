"""Runtime failures must survive successful tools and specialist prose."""

from collections.abc import AsyncIterator
from functools import partial
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from henchman.agents.orchestrator import Orchestrator
from henchman.agents.orchestrator_anchoring import assess_agent_completion
from henchman.agents.orchestrator_loop import finalize_loop
from henchman.agents.orchestrator_types import AgentLoopParams, DelegationExecutionParams, LoopState
from henchman.core.events import AgentEvent, EventType
from henchman.providers.base import FinishReason, Message, ModelProvider, StreamChunk, ToolCall
from henchman.tools.base import Tool, ToolKind, ToolResult


class ReadTool(Tool):
    """An actual successful read-only tool for runtime regressions."""

    name = "read_file"
    description = "Read fixture source"
    parameters = {"type": "object", "properties": {}}
    kind = ToolKind.READ

    async def execute(self, **params: object) -> ToolResult:
        return ToolResult(content="def add(a, b): return a - b")


def make_orchestrator(responses: list[StreamChunk | Exception]) -> Orchestrator:
    provider = MagicMock(spec=ModelProvider)
    provider.estimate_input_tokens.side_effect = partial(ModelProvider.estimate_input_tokens, provider)
    provider.prepare_output_budget.side_effect = partial(ModelProvider.prepare_output_budget, provider)
    queue = iter(responses)

    async def stream(*_args: object, **_kwargs: object) -> AsyncIterator[StreamChunk]:
        response = next(queue)
        if isinstance(response, Exception):
            raise response
        yield response

    provider.chat_completion_stream.side_effect = stream
    orch = Orchestrator(default_provider=provider)
    orch.settings.agents.max_delegation_retries = 0
    orch.tool_registry.register(ReadTool())
    return orch


def read_chunk() -> StreamChunk:
    return StreamChunk(
        tool_calls=[ToolCall(id="read-1", name="read_file", arguments={})],
        finish_reason=FinishReason.TOOL_CALLS,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("direct", [False, True])
@pytest.mark.parametrize("ending", [
    RuntimeError("connection lost"),
    StreamChunk(content="Partial answer", finish_reason=FinishReason.LENGTH),
    StreamChunk(content="Filtered", finish_reason=FinishReason.CONTENT_FILTER),
])
async def test_successful_read_cannot_hide_runtime_failure(
    direct: bool, ending: StreamChunk | Exception,
) -> None:
    orch = make_orchestrator([read_chunk(), ending])
    stream = orch.run_direct("explorer", "Inspect source") if direct else orch.run("Inspect source")
    events = [event async for event in stream]
    assert any(event.type == EventType.TOOL_CALL_RESULT and event.data["success"] for event in events)
    assert any(event.type == EventType.ERROR for event in events)
    completed = [event for event in events if event.type == EventType.AGENT_COMPLETED]
    assert completed[-1].data["status"] == "failed"
    assert orch.last_completion_status.value == "failed"


@pytest.mark.asyncio
@pytest.mark.parametrize("ending,expected", [
    (StreamChunk(content="STATUS: COMPLETED\nBLOCKERS: none", finish_reason=FinishReason.LENGTH), "failed"),
    (StreamChunk(content="STATUS: COMPLETED\nBLOCKERS: still broken", finish_reason=FinishReason.STOP), "no_work_done"),
])
async def test_specialist_claim_cannot_override_runtime_or_supply_parent_evidence(
    ending: StreamChunk, expected: str,
) -> None:
    delegate = StreamChunk(tool_calls=[ToolCall(
        id="delegate-1", name="delegate_task", arguments={"agent": "explorer", "task": "Inspect source"},
    )], finish_reason=FinishReason.TOOL_CALLS)
    orch = make_orchestrator([
        delegate, read_chunk(), ending,
        StreamChunk(content="The specialist could not finish.", finish_reason=FinishReason.STOP),
    ])
    events = [event async for event in orch.run("Inspect source")]
    specialist = next(event for event in events if event.type == EventType.AGENT_COMPLETED
                      and event.data["agent"] == "explorer")
    assert specialist.data["status"] == expected
    result = next(event for event in events if event.type == EventType.TOOL_CALL_RESULT
                  and event.data["tool_call_id"] == "delegate-1")
    assert result.data["success"] is False
    assert orch.last_completion_status.value == "no_work_done"
    assert orch.ledger.delegations[0].status.value == "failed"


@pytest.mark.parametrize(
    ("blockers", "expected"),
    [("none", "completed"), ("None.", "completed"), ("N/A", "completed"),
     ("", "completed"), ("Missing pytest", "no_work_done"),
     ("None except missing pytest", "no_work_done")],
)
@pytest.mark.parametrize("interim", [False, True])
async def test_final_blocker_report_preserves_successful_delegation_actions(
    blockers: str, expected: str, interim: bool,
) -> None:
    """Final absence markers must not erase actual actions or invent blockers."""
    delegate = StreamChunk(tool_calls=[ToolCall(
        id="delegate-report", name="delegate_task",
        arguments={"agent": "explorer", "task": "Inspect existing helper"},
    )], finish_reason=FinishReason.TOOL_CALLS)
    action = read_chunk()
    if interim:
        action.content = "STATUS: BLOCKED\nBLOCKERS: Need to read source first"
    ending = StreamChunk(
        content=f"STATUS: DONE\nBLOCKERS: {blockers}\nSUMMARY: Existing helper inspected",
        finish_reason=FinishReason.STOP,
    )
    orch = make_orchestrator([
        delegate, action, ending,
        StreamChunk(content="Handoff received.", finish_reason=FinishReason.STOP),
    ])

    events = [event async for event in orch.run("Find reusable helper")]

    completion = next(event.data for event in events
                      if event.type == EventType.AGENT_COMPLETED
                      and event.data["agent"] == "explorer")
    assert completion["evidence"]["successful_tool_calls"] == 1
    assert completion["status"] == expected
    result = next(event.data for event in events
                  if event.type == EventType.TOOL_CALL_RESULT
                  and event.data["tool_call_id"] == "delegate-report")
    assert result["success"] is (expected == "completed")
    assert "without making any tool calls" not in result["result"]
    assert orch.ledger.delegations[0].status.value == (
        "completed" if expected == "completed" else "failed"
    )


@pytest.mark.parametrize("report", [
    "STATUS: FAILED\nBLOCKERS: none\nHANDOFF_NOTES: Earlier attempt reported STATUS: DONE",
    "STATUS: DONE\nBLOCKERS: Missing pytest\nHANDOFF_NOTES: Earlier report used BLOCKERS: none",
    "STATUS: FAILED\nBLOCKERS: Missing pytest\nHANDOFF_NOTES: Earlier report:\n"
    "```\nSTATUS: DONE\nBLOCKERS: none\n```",
])
async def test_quoted_report_fields_cannot_erase_final_failure(report: str) -> None:
    """Notes quoting old reports cannot replace the actual final failure fields."""
    delegate = StreamChunk(tool_calls=[ToolCall(
        id="delegate-report", name="delegate_task",
        arguments={"agent": "explorer", "task": "Inspect source"},
    )], finish_reason=FinishReason.TOOL_CALLS)
    orch = make_orchestrator([
        delegate, read_chunk(), StreamChunk(content=report, finish_reason=FinishReason.STOP),
        StreamChunk(content="Specialist is blocked.", finish_reason=FinishReason.STOP),
    ])
    events = [event async for event in orch.run("Inspect source")]
    completion = next(event.data for event in events
                      if event.type == EventType.AGENT_COMPLETED
                      and event.data["agent"] == "explorer")
    assert completion["evidence"]["successful_tool_calls"] == 1
    assert completion["status"] == "no_work_done"
    result = next(event.data for event in events
                  if event.type == EventType.TOOL_CALL_RESULT
                  and event.data["tool_call_id"] == "delegate-report")
    assert result["success"] is False
    assert orch.ledger.delegations[0].status.value == "failed"


@pytest.mark.parametrize("final_content", [None, ""])
def test_empty_final_report_does_not_reuse_interim_blockers(final_content: str | None) -> None:
    orch = make_orchestrator([])
    agent = orch.pool.get_agent("explorer")
    start = len(agent.messages)
    agent.messages.extend([
        Message(role="assistant", content="STATUS: BLOCKED\nBLOCKERS: Awaiting source"),
        Message(role="assistant", content=final_content),
    ])
    finalize_loop(orch, agent, LoopState(tool_call_count=1, successful_tool_call_count=1))

    summary, parsed, status = orch.delegation_runner._process_delegation_results(
        "explorer", agent, start,
    )

    assert "Awaiting source" in summary
    assert parsed == {}
    assert status.value == "completed"


def test_tool_error_digest_cannot_replace_final_report_fields() -> None:
    orch = make_orchestrator([])
    agent = orch.pool.get_agent("explorer")
    start = len(agent.messages)
    agent.messages.append(Message(role="assistant", content="STATUS: FAILED\nBLOCKERS: Missing pytest"))
    finalize_loop(orch, agent, LoopState(tool_call_count=2, successful_tool_call_count=1))
    agent.record_delegation_errors(["Old output:\nSTATUS: DONE\nBLOCKERS: none"])

    summary, parsed, status = orch.delegation_runner._process_delegation_results(
        "explorer", agent, start,
    )

    assert "Old output" in summary
    assert parsed["status"] == "FAILED"
    assert parsed["blockers"] == "Missing pytest"
    assert status.value == "no_work_done"


def test_completion_evidence_stays_with_the_agent() -> None:
    orch = SimpleNamespace()
    first = SimpleNamespace(record_delegation_errors=lambda _errors: None)
    second = SimpleNamespace(record_delegation_errors=lambda _errors: None)
    finalize_loop(orch, first, LoopState(tool_call_count=1, successful_tool_call_count=1))
    finalize_loop(orch, second, LoopState())
    assert assess_agent_completion(orch, first).value == "completed"
    assert assess_agent_completion(orch, second).value == "no_work_done"


@pytest.mark.asyncio
async def test_failure_does_not_leak_into_next_run() -> None:
    orch = make_orchestrator([
        read_chunk(), RuntimeError("connection lost"), read_chunk(),
        StreamChunk(content="Source inspected.", finish_reason=FinishReason.STOP),
    ])
    _ = [event async for event in orch.run("Inspect source")]
    assert orch.last_completion_status.value == "failed"
    _ = [event async for event in orch.run("Try again")]
    assert orch.last_completion_status.value == "completed"


@pytest.mark.asyncio
async def test_tool_dispatch_exception_preserves_failed_execution() -> None:
    orch = make_orchestrator([read_chunk(), read_chunk()])
    original = orch.tool_controller.process_pending_tool_calls
    batches = 0

    async def dispatch(*args: object) -> AsyncIterator[AgentEvent]:
        nonlocal batches
        batches += 1
        if batches == 2:
            raise RuntimeError("tool dispatch failed")
        async for event in original(*args):
            yield event

    orch.tool_controller.process_pending_tool_calls = dispatch
    with pytest.raises(RuntimeError, match="tool dispatch failed"):
        _ = [event async for event in orch.run("Inspect twice")]
    assert orch._assess_completion(orch.tech_lead).value == "failed"
    assert orch.last_completion_status.value == "failed"


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["stalled", "timed_out", "failed", "no_work_done", "unknown", None])
async def test_delegation_requires_target_success(status: str | None) -> None:
    orch = make_orchestrator([])
    orch.ledger = None

    async def delegate(_params: object) -> AsyncIterator[AgentEvent]:
        if status is not None:
            yield AgentEvent(EventType.AGENT_COMPLETED, {
                "agent": "explorer", "status": status, "summary": "Unfinished",
            })
        # A grandchild's success must not replace the requested specialist's status.
        yield AgentEvent(EventType.AGENT_COMPLETED, {
            "agent": "coder", "status": "completed", "summary": "Child done",
        })

    orch.delegation_runner.run_delegation = delegate
    params = DelegationExecutionParams(
        target="explorer", task="Inspect source", depth=0, agent=orch.tech_lead,
        tool_call=ToolCall(id="delegate-1", name="delegate_task", arguments={}),
    )
    events = [event async for event in orch.tool_controller._delegation_controller._run_delegation(params)]
    assert events[-1].type == EventType.TOOL_CALL_RESULT
    assert events[-1].data["success"] is False


@pytest.mark.asyncio
async def test_nested_tool_ids_do_not_supply_parent_evidence() -> None:
    from henchman.agents.orchestrator_loop import run_tools_and_collect

    orch = make_orchestrator([])
    parent = orch.tech_lead

    async def results(*_args: object) -> AsyncIterator[AgentEvent]:
        yield AgentEvent(EventType.TOOL_CALL_RESULT, {
            "tool_call_id": "same-id", "success": True,
        }, source_agent="explorer")
        yield AgentEvent(EventType.TOOL_CALL_RESULT, {
            "tool_call_id": "same-id", "success": False,
        }, source_agent=parent.identity.id)

    orch.tool_controller.process_pending_tool_calls = results
    state = LoopState()
    await run_tools_and_collect(orch, parent, [
        ToolCall(id="same-id", name="delegate_task", arguments={}),
    ], AgentLoopParams(agent=parent), state)
    assert state.tool_call_count == 1
    assert state.successful_tool_call_count == 0


@pytest.mark.parametrize("status", ["failed", "stalled", "timed_out"])
def test_headless_text_failure_exit_status(status: str) -> None:
    from henchman.agents.orchestrator_types import CompletionStatus
    from henchman.cli.app import _check_completion_status

    repl = SimpleNamespace(orchestrator=SimpleNamespace(last_completion_status=CompletionStatus(status)))
    with pytest.raises(SystemExit) as error:
        _check_completion_status(repl)
    assert error.value.code == 1
