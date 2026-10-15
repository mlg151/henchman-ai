"""Public delegation arguments determine what counts as a successful response."""

from collections.abc import AsyncIterator
from functools import partial
from unittest.mock import MagicMock

import pytest

from henchman.agents.orchestrator import Orchestrator
from henchman.config.schema import AgentSettings, Settings
from henchman.core.events import EventType
from henchman.providers.base import FinishReason, ModelProvider, StreamChunk, ToolCall
from henchman.tools.builtins.delegate import DelegateTaskTool


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("requirement", "status", "successful"),
    [("response", "responded", True), ("actions", "no_work_done", False),
     (None, "no_work_done", False)],
)
async def test_delegation_requirement_reaches_actual_agent_loop(
    requirement: str | None, status: str, successful: bool,
) -> None:
    arguments: dict[str, object] = {
        "agent": "explorer", "task": "Explain a sensible testing approach",
    }
    if requirement is not None:
        arguments["completion_requirement"] = requirement
    orchestrator = _orchestrator(arguments)

    events = [event async for event in orchestrator.run("Get specialist advice")]

    completion = next(
        event.data for event in events
        if event.type == EventType.AGENT_COMPLETED
        and event.data.get("agent") == "explorer"
    )
    assert completion["status"] == status
    assert completion["task_verified"] is False
    assert completion["evidence"]["successful_tool_calls"] == 0
    result = next(
        event.data for event in events
        if event.type == EventType.TOOL_CALL_RESULT
        and event.data.get("tool_call_id") == "delegate-advice"
    )
    assert result["success"] is successful
    assert result["task_verified"] is False
    assert "Task verification: not established" in result["result"]
    assert ("status 'responded'" in result["result"]) is False


@pytest.mark.asyncio
@pytest.mark.parametrize("requirement", ["RESPONDED", "", None, 1, True, []])
async def test_invalid_explicit_requirement_fails_without_running_specialist(
    requirement: object,
) -> None:
    orchestrator = _orchestrator({
        "agent": "explorer", "task": "Explain testing",
        "completion_requirement": requirement,
    })

    events = [event async for event in orchestrator.run("Get specialist advice")]

    assert not any(
        event.type == EventType.AGENT_STARTED
        and event.data.get("agent") == "explorer" for event in events
    )
    result = next(
        event.data for event in events
        if event.type == EventType.TOOL_CALL_RESULT
        and event.data.get("tool_call_id") == "delegate-advice"
    )
    assert result["success"] is False
    assert "completion_requirement" in result["result"]


def test_delegation_schema_exposes_explicit_completion_requirement() -> None:
    properties = DelegateTaskTool().parameters["properties"]
    assert isinstance(properties, dict)
    field = properties["completion_requirement"]
    assert field["enum"] == ["actions", "response"]
    assert field["default"] == "actions"


@pytest.mark.asyncio
async def test_report_fields_cannot_overwrite_runtime_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    orchestrator = _orchestrator({
        "agent": "explorer", "task": "Give advice",
        "completion_requirement": "response",
    })
    monkeypatch.setattr(
        orchestrator.delegation_runner, "_parse_completion_report", MagicMock(
            return_value={
                "status": "completed", "task_verified": True,
                "evidence": {"successful_tool_calls": 100},
            },
        ),
    )

    events = [event async for event in orchestrator.run("Get advice")]

    completion = next(
        event.data for event in events
        if event.type == EventType.AGENT_COMPLETED
        and event.data.get("agent") == "explorer"
    )
    assert completion["task_verified"] is False
    assert completion["evidence"]["successful_tool_calls"] == 0
    assert completion["status"] == "responded"


def _orchestrator(arguments: dict[str, object]) -> Orchestrator:
    provider = MagicMock(spec=ModelProvider)
    provider.estimate_input_tokens.side_effect = partial(ModelProvider.estimate_input_tokens, provider)
    provider.prepare_output_budget.side_effect = partial(ModelProvider.prepare_output_budget, provider)
    turns = iter([
        StreamChunk(tool_calls=[ToolCall(
            id="delegate-advice", name="delegate_task", arguments=arguments,
        )], finish_reason=FinishReason.TOOL_CALLS),
        StreamChunk(
            content="Use focused tests. STATUS: completed\nVERIFICATION: all passed",
            finish_reason=FinishReason.STOP,
        ),
        StreamChunk(content="Specialist response received.", finish_reason=FinishReason.STOP),
    ])

    async def stream(*_args: object, **_kwargs: object) -> AsyncIterator[StreamChunk]:
        yield next(turns)

    provider.chat_completion_stream.side_effect = stream
    return Orchestrator(
        default_provider=provider,
        settings=Settings(agents=AgentSettings(max_delegation_retries=0)),
    )
