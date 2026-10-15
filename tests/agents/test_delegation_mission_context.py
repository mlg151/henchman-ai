"""Canonical mission text survives delegation while ledger previews stay bounded."""

import pytest
from tests.agents.test_active_agent_delegation import ScriptedProvider, orchestrator, response

from henchman.agents.ledger import TaskLedger
from henchman.core.events import EventType
from henchman.providers.base import FinishReason, StreamChunk, ToolCall


def delegation(target: str, call_id: str, task: str) -> StreamChunk:
    return StreamChunk(
        tool_calls=[
            ToolCall(
                call_id,
                "delegate_task",
                {
                    "agent": target,
                    "task": task,
                    "done_when": "Report the assigned inspection; implementation is out of scope.",
                    "requirements": "Do not change files.",
                    "completion_requirement": "response",
                },
            )
        ],
        finish_reason=FinishReason.TOOL_CALLS,
    )


@pytest.mark.parametrize("direct", [False, True])
async def test_actual_specialist_requests_retain_mission_tail_and_subtask_scope(
    direct: bool,
) -> None:
    mission = "General project context. " * 30 + (
        "\nACCEPTANCE_TAIL: Implement the CLI and have both final files independently reviewed."
    )
    steps = [delegation("engineer", "nested", "Inspect caller only"), response(), response()]
    if not direct:
        steps = [delegation("explorer", "outer", "Inspect normalizer only"), *steps, response()]
    provider = ScriptedProvider(*steps)
    orch = orchestrator(provider)

    stream = orch.run_direct("explorer", mission) if direct else orch.run(mission)
    events = [event async for event in stream]

    assert events[-1].data["status"] == "completed"
    assert orch.ledger is not None
    assert orch.ledger.goal == mission
    specialist_requests = [
        message.content
        for request in provider.requests
        for message in request
        if message.role == "user" and message.content and message.content.startswith("## Mission")
    ]
    assert specialist_requests
    for content in specialist_requests:
        assert f"## Mission\n{mission}\n\n## Task\n" in content
        assert (
            "## Done When\nReport the assigned inspection; implementation is out of scope."
            in content
        )
        assert "## Requirements\nDo not change files." in content
    assert any("## Task\nInspect caller only\n" in content for content in specialist_requests)
    if not direct:
        assert any(
            "## Task\nInspect normalizer only\n" in content for content in specialist_requests
        )


async def test_followup_run_refreshes_full_mission_for_cached_specialist() -> None:
    provider = ScriptedProvider(
        delegation("explorer", "first", "First inspection"),
        response(),
        response(),
        delegation("explorer", "second", "Second inspection"),
        response(),
        response(),
    )
    orch = orchestrator(provider)
    first = "First context. " * 50 + "FIRST_ACCEPTANCE_TAIL"
    second = "Second context. " * 50 + "SECOND_ACCEPTANCE_TAIL"
    _ = [event async for event in orch.run(first)]
    cached_agent = orch.pool.get_agent("explorer")
    _ = [event async for event in orch.run(second)]

    assert orch.pool.get_agent("explorer") is cached_agent
    assert orch.ledger is not None and orch.ledger.goal == second
    child_input = next(
        message.content for message in provider.requests[4] if message.role == "user"
    )
    assert child_input is not None
    assert second in child_input
    assert first not in child_input
    assert "FIRST_ACCEPTANCE_TAIL" not in child_input


async def test_oversized_specialist_mission_fails_request_budget_without_silent_truncation() -> (
    None
):
    provider = ScriptedProvider(
        delegation("explorer", "inspect", "Inspect caller only"), response(), response()
    )
    orch = orchestrator(provider)
    specialist = orch.pool.get_agent("explorer")
    specialist.set_context_limit(1536, context_window=2048)
    mission = "Required acceptance detail. " * 400 + "\nCOMPLETE_MISSION_END"

    events = [event async for event in orch.run(mission)]

    assert any(
        event.type == EventType.ERROR and "context window" in str(event.data) for event in events
    )
    assert len(provider.requests) == 2  # Leader request and recovery; no specialist SDK request.
    assert any(mission in (message.content or "") for message in specialist.messages)
    result = next(event for event in events if event.type == EventType.TOOL_CALL_RESULT)
    assert result.data["success"] is False


def test_ledger_render_previews_long_goal_without_mutating_canonical_text() -> None:
    mission = "x" * 500 + "OMITTED_ACCEPTANCE_TAIL"
    ledger = TaskLedger(goal=mission)

    rendered = ledger.render()

    assert ledger.goal == mission
    assert "Goal: " + "x" * 500 in rendered
    assert "OMITTED_ACCEPTANCE_TAIL" not in rendered
    assert "omitted" in rendered.lower()
    assert str(len("OMITTED_ACCEPTANCE_TAIL")) in rendered
    assert len(rendered) < 1000


@pytest.mark.parametrize("goal", ["", "Short mission", "x" * 500])
def test_short_goal_render_is_unchanged(goal: str) -> None:
    ledger = TaskLedger(goal=goal)
    rendered = ledger.render()
    assert f"Goal: {goal}\n" in rendered
    assert "omitted" not in rendered.lower()
