"""Tests for the orchestration event leak fix in ToolExecutor."""

from typing import Any
from unittest.mock import MagicMock

import pytest
from rich.console import Console

from henchman.cli.output_handler import OutputHandler
from henchman.cli.session_manager import ReplSessionManager
from henchman.cli.tool_executor import ToolExecutor
from henchman.cli.tool_manager import ToolManager
from henchman.core.agent import Agent
from henchman.core.events import AgentEvent, EventType
from henchman.providers.base import Message, ModelProvider, ToolCall


class MockProvider(ModelProvider):
    @property
    def name(self) -> str:
        return "mock"

    async def chat_completion_stream(self, messages: list[Message], tools: list[Any] | None = None, **kwargs: Any):
        yield None


@pytest.mark.anyio
async def test_sub_agent_event_filtering() -> None:
    """Test that events from sub-agents are filtered and not recorded in the main agent's session."""
    # Setup mocks
    _console = MagicMock(spec=Console)  # noqa: F841
    provider = MockProvider()
    tool_manager = MagicMock(spec=ToolManager)
    tool_manager.registry = MagicMock()

    output_handler = MagicMock(spec=OutputHandler)
    session_manager = MagicMock(spec=ReplSessionManager)
    output_handler.session_manager = session_manager

    executor = ToolExecutor(
        output_handler=output_handler,
        tool_manager=tool_manager,
        provider=provider
    )

    # Setup agent with identity
    from henchman.agents.identity import AgentIdentity
    from henchman.core.turn import TurnState
    identity = AgentIdentity(
        id="tech_lead",
        name="Leader",
        role="tech_lead",
        description="Architect and coordinator"
    )
    agent = MagicMock(spec=Agent)
    agent.identity = identity
    # Use a real TurnState to avoid mock truthiness issues
    turn = TurnState()
    agent.turn = turn
    agent.unlimited_mode = False

    # Define an event stream with interleaved events
    async def event_generator():
        # 1. Tech Lead starts a response
        yield AgentEvent(type=EventType.CONTENT, data="I will delegate this. ", source_agent="tech_lead")

        # 2. Tech Lead makes a delegation call
        yield AgentEvent(
            type=EventType.TOOL_CALL_REQUEST,
            data=ToolCall(id="call_tl_1", name="delegate_task", arguments={"agent": "engineer", "task": "fix bug"}),
            source_agent="tech_lead"
        )

        # 3. Specialist starts work (should be displayed but not recorded in TL session)
        yield AgentEvent(type=EventType.AGENT_STARTED, data={"agent": "engineer"}, source_agent="orchestrator")

        # 4. Specialist produces content (should be displayed but not accumulated in TL response)
        yield AgentEvent(type=EventType.CONTENT, data="Engineer is working... ", source_agent="engineer")

        # 5. Specialist makes an internal tool call (should be displayed but not recorded for TL)
        yield AgentEvent(
            type=EventType.TOOL_CALL_REQUEST,
            data=ToolCall(id="call_eng_1", name="ls", arguments={"path": "."}),
            source_agent="engineer"
        )

        # 6. Specialist tool result (should be displayed but not flush TL's session message)
        yield AgentEvent(
            type=EventType.TOOL_CALL_RESULT,
            data={"tool_call_id": "call_eng_1", "tool_name": "ls", "result": "file.txt", "success": True},
            source_agent="engineer"
        )

        # 7. Specialist completes
        yield AgentEvent(type=EventType.AGENT_COMPLETED, data={"agent": "engineer", "summary": "Fixed."}, source_agent="engineer")

        # 8. Tech Lead's delegation tool finishes (yielded by orchestrator)
        yield AgentEvent(
            type=EventType.TOOL_CALL_RESULT,
            data={"tool_call_id": "call_tl_1", "tool_name": "delegate_task", "result": "Specialist finished: Fixed.", "success": True},
            source_agent="tech_lead"
        )

        # 9. Tech Lead finishes with some final text
        yield AgentEvent(type=EventType.CONTENT, data="Delegation complete.", source_agent="tech_lead")
        yield AgentEvent(type=EventType.FINISHED, source_agent="tech_lead")

    # Run the stream processing
    await executor.process_agent_stream(event_generator(), agent)

    # VERIFICATIONS

    # 1. Verify content accumulation: Only Tech Lead content should be recorded
    calls = session_manager.record_agent_message.call_args_list
    assert len(calls) == 2

    # First flush (after delegate_task result)
    # content should be "I will delegate this. "
    _, kwargs1 = calls[0]
    assert kwargs1["content"] == "I will delegate this. "
    assert len(kwargs1["tool_calls"]) == 1
    assert kwargs1["tool_calls"][0]["id"] == "call_tl_1"

    # Second flush (at end of stream)
    # content should be "Delegation complete."
    _, kwargs2 = calls[1]
    assert kwargs2["content"] == "Delegation complete."
    assert kwargs2.get("tool_calls") is None

    # 2. Verify tool results: Only Tech Lead's tool results should be recorded in session
    tool_result_calls = session_manager.record_tool_result.call_args_list
    assert len(tool_result_calls) == 1
    assert tool_result_calls[0][0][0] == "call_tl_1"

    # 3. Verify UI display: ALL events should still be displayed
    content_calls = [args[0] for args, kwargs in output_handler.print_agent_content.call_args_list]
    assert "I will delegate this. " in content_calls
    assert "Engineer is working... " in content_calls
    assert "Delegation complete." in content_calls

    muted_calls = [args[0] for args, kwargs in output_handler.muted.call_args_list]
    assert any("delegate_task" in c for c in muted_calls)
    assert any("ls" in c for c in muted_calls)
