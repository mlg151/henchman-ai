"""Orchestration-generated messages remain in the uncompacted turn transcript."""

from collections.abc import AsyncIterator
from types import SimpleNamespace

import pytest

from henchman.agents.identity import AgentIdentity
from henchman.agents.orchestrator_anchoring import inject_role_anchor
from henchman.agents.orchestrator_loop import check_colon_stall
from henchman.agents.orchestrator_turns import TurnEnforcementParams
from henchman.agents.orchestrator_validation import check_stall_failure
from henchman.core.agent import Agent
from henchman.providers.base import FinishReason, Message, ModelProvider, StreamChunk


class TurnProvider(ModelProvider):
    name = "turn-archive-test"

    async def chat_completion_stream(self, messages, tools=None, **kwargs) -> AsyncIterator[StreamChunk]:
        yield StreamChunk(content="Investigation results for this request:", finish_reason=FinishReason.STOP)


@pytest.mark.asyncio
@pytest.mark.parametrize("generated", [
    "stall_failure", "colon_nudge", "wrapup_warning", "timeout", "role_anchor",
])
async def test_generated_messages_are_archived_without_copying_previous_turn(generated):
    agent = Agent(
        TurnProvider(), system_prompt="System instructions", max_tokens=10000,
        identity=AgentIdentity("explorer", "Explorer", "explorer", "Investigate"),
    )
    agent.stall_detection_enabled = False
    agent.messages.extend([
        Message(role="user", content="Previous request"),
        Message(role="assistant", content="Previous answer"),
    ])
    _ = [event async for event in agent.run("Current request")]
    before = list(agent.current_turn_messages)

    if generated == "stall_failure":
        agent._stall.failure = True
        check_stall_failure(SimpleNamespace(tech_lead=None), agent)
    elif generated == "colon_nudge":
        continuation = check_colon_stall(agent, 0)
        assert continuation is not None
        await continuation[0].aclose()
    elif generated in {"wrapup_warning", "timeout"}:
        TurnEnforcementParams(
            agent=agent, max_turns=4,
            tool_call_count=4 if generated == "timeout" else 2,
            msg_start_index=3, wrapup_warned=False,
        ).enforce_limits()
    else:
        inject_role_anchor(SimpleNamespace(ledger=None), agent, 8)

    generated_message = agent.messages[-1]
    assert agent.current_turn_messages == [*before, generated_message]
    assert agent.current_turn_messages[-1] is not generated_message
    assert [message.content for message in agent.current_turn_messages[:2]] == [
        "Current request", "Investigation results for this request:",
    ]
    original = generated_message.content
    generated_message.content = "Context compacted"
    assert agent.current_turn_messages[-1].content == original

    _ = [event async for event in agent.run("Next request")]
    assert [message.content for message in agent.current_turn_messages] == [
        "Next request", "Investigation results for this request:",
    ]
