"""Whole-run completion must be distinguishable from specialist completion."""

from tests.agents.test_completion_integrity import make_orchestrator, read_chunk

from henchman.core.events import EventType
from henchman.providers.base import FinishReason, StreamChunk, ToolCall


async def test_only_outer_completion_has_run_scope() -> None:
    orch = make_orchestrator([
        StreamChunk(tool_calls=[ToolCall("delegation", "delegate_task", {
            "agent": "explorer", "task": "Inspect source",
        })], finish_reason=FinishReason.TOOL_CALLS),
        read_chunk(), StreamChunk(content="Inspected", finish_reason=FinishReason.STOP),
        StreamChunk(content="Review complete", finish_reason=FinishReason.STOP),
    ])
    events = [event async for event in orch.run("Inspect source")]
    completions = [event.data for event in events if event.type == EventType.AGENT_COMPLETED]
    assert len(completions) == 2
    assert completions[-1]["scope"] == "run"
    assert completions[0].get("scope") != "run"


async def test_direct_run_starts_new_ledger_and_resets_metrics() -> None:
    orch = make_orchestrator([
        StreamChunk(content="First", finish_reason=FinishReason.STOP),
        StreamChunk(content="Second", finish_reason=FinishReason.STOP),
    ])
    _ = [event async for event in orch.run("First goal")]
    previous = orch.ledger
    orch.metrics.delegation_count = 9
    events = [event async for event in orch.run_direct("explorer", "Second goal")]
    assert orch.ledger is not previous
    assert orch.ledger.goal == "Second goal"
    assert orch.metrics.delegation_count == 0
    assert events[-1].data["scope"] == "run"
