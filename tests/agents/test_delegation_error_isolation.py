"""Cached agents report current execution errors without reviving prior failures."""

from copy import deepcopy

import pytest
from tests.agents.test_active_agent_delegation import ScriptedProvider, response

from henchman.agents.config import AgentConfig
from henchman.agents.orchestrator import Orchestrator
from henchman.agents.orchestrator_types import DelegationParams
from henchman.config.schema import Settings
from henchman.core.events import EventType
from henchman.providers.base import FinishReason, StreamChunk, ToolCall
from henchman.tools.base import Tool, ToolKind, ToolResult


class DiagnosticTool(Tool):
    name, description, kind = "read_file", "Deterministic diagnostic fixture", ToolKind.READ
    parameters = {
        "type": "object",
        "properties": {"failure": {"type": "string"}},
    }

    async def execute(self, **params: object) -> ToolResult:
        failure = params.get("failure")
        if failure:
            return ToolResult(str(failure), success=False, error=str(failure))
        return ToolResult("Read succeeded")


def tool_response(failure: str | None) -> StreamChunk:
    return StreamChunk(
        tool_calls=[ToolCall("read", "read_file", {"failure": failure} if failure else {})],
        finish_reason=FinishReason.TOOL_CALLS,
    )


def make_orchestrator(provider: ScriptedProvider) -> Orchestrator:
    settings = Settings()
    settings.agents.agents["explorer"] = AgentConfig(
        name="Explorer",
        role="explorer",
        description="Diagnostic fixture specialist",
        tools=["read_file"],
        system_prompt="Inspect the assigned source and report the result.",
    )
    orch = Orchestrator(provider, settings=settings)
    orch.tool_registry.register(DiagnosticTool())
    return orch


@pytest.mark.parametrize("current_failure", [None, "CURRENT_FAILURE_SENTINEL"])
async def test_cached_specialist_summaries_isolate_each_delegations_tool_errors(
    current_failure: str | None,
) -> None:
    provider = ScriptedProvider(
        tool_response("OLD_FAILURE_SENTINEL"),
        response(),
        tool_response(current_failure),
        response(),
    )
    orch = make_orchestrator(provider)
    cached = orch.pool.get_agent("explorer")
    first = [
        event
        async for event in orch.delegation_runner.run_delegation(
            DelegationParams("explorer", "First inspection")
        )
    ]
    first_completion = next(
        event.data for event in first if event.type == EventType.AGENT_COMPLETED
    )
    first_snapshot = deepcopy(first_completion)
    assert "OLD_FAILURE_SENTINEL" in first_completion["summary"]

    second = [
        event
        async for event in orch.delegation_runner.run_delegation(
            DelegationParams("explorer", "Second inspection")
        )
    ]
    second_completion = next(
        event.data for event in second if event.type == EventType.AGENT_COMPLETED
    )

    assert orch.pool.get_agent("explorer") is cached
    assert "OLD_FAILURE_SENTINEL" not in second_completion["summary"]
    if current_failure:
        assert current_failure in second_completion["summary"]
        assert "TOOL ERRORS" in second_completion["summary"]
    else:
        assert second_completion["status"] == "completed"
        assert "TOOL ERRORS" not in second_completion["summary"]
        assert cached.get_delegation_errors() == []
    assert first_completion == first_snapshot


async def test_direct_run_resets_diagnostics_without_discarding_history() -> None:
    provider = ScriptedProvider(
        tool_response("OLD_FAILURE_SENTINEL"), response(), tool_response(None), response()
    )
    orch = make_orchestrator(provider)
    first = [event async for event in orch.run_direct("explorer", "First inspection")]
    cached = orch.pool.get_agent("explorer")
    assert cached.get_delegation_errors()
    first_snapshot = deepcopy(first)

    second = [event async for event in orch.run_direct("explorer", "Second inspection")]

    assert second[-1].data["status"] == "completed"
    assert cached.get_delegation_errors() == []
    assert any(message.content == "First inspection" for message in cached.messages)
    assert first == first_snapshot


async def test_continuation_keeps_current_errors_until_explicit_history_reset() -> None:
    orch = make_orchestrator(ScriptedProvider(response()))
    agent = orch.pool.get_agent("explorer")
    agent.record_delegation_errors(["current lint failure"])
    agent.record_delegation_errors(["current edit failure"])

    _ = [event async for event in agent.continue_with_tool_results()]

    assert agent.get_delegation_errors() == ["current lint failure", "current edit failure"]
    agent.clear_history()
    assert agent.get_delegation_errors() == []
