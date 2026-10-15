"""Stall evidence belongs to one user turn, including its continuations."""

import pytest

from henchman.core.agent_stall import StallDetector
from henchman.providers.base import FinishReason, StreamChunk
from tests.agents.test_completion_integrity import make_orchestrator


@pytest.mark.asyncio
async def test_same_agent_recovers_after_stalled_turn() -> None:
    intent = StreamChunk(
        content="Let me start by inspecting the code.", finish_reason=FinishReason.STOP,
    )
    orch = make_orchestrator([
        intent, intent, intent, StreamChunk(content="Hello!", finish_reason=FinishReason.STOP),
    ])
    first = [event async for event in orch.run_direct("explorer", "Inspect the code")]
    assert first[-1].data["status"] == "stalled"
    agent = orch.pool.get_agent("explorer")
    assert agent is not None
    assert agent._stall.failure
    assert agent._stall.nudge_count == 3

    second = [event async for event in orch.run_direct("explorer", "Hello")]
    assert orch.pool.get_agent("explorer") is agent
    assert second[-1].data["status"] == "responded"
    assert agent._stall.failure is False
    assert agent._stall.nudge_count == 0


@pytest.mark.parametrize("enabled", [True, False])
def test_detector_reset_preserves_configuration(enabled: bool) -> None:
    detector = StallDetector(enabled=enabled, nudge_count=4, failure=True, _max_nudges=7)
    detector.reset()
    assert detector.nudge_count == 0
    assert detector.failure is False
    assert detector.enabled is enabled
    assert detector._max_nudges == 7


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["run", "clear_history"])
async def test_new_turn_boundary_resets_evidence_without_changing_settings(operation: str) -> None:
    orch = make_orchestrator([StreamChunk(content="Hello!", finish_reason=FinishReason.STOP)])
    agent = orch.tech_lead
    detector = agent._stall
    detector.enabled = False
    detector._max_nudges = 7
    detector.nudge_count = 4
    detector.failure = True
    if operation == "run":
        _ = [event async for event in agent.run("Hello")]
    else:
        agent.clear_history()
    assert agent._stall is detector
    assert detector.nudge_count == 0
    assert detector.failure is False
    assert detector.enabled is False
    assert detector._max_nudges == 7


@pytest.mark.asyncio
async def test_tool_continuation_preserves_current_turn_stall_evidence() -> None:
    orch = make_orchestrator([StreamChunk(content="Answer", finish_reason=FinishReason.STOP)])
    agent = orch.tech_lead
    agent._stall.nudge_count = 3
    agent._stall.failure = True
    _ = [event async for event in agent.continue_with_tool_results()]
    assert agent._stall.nudge_count == 3
    assert agent._stall.failure is True
