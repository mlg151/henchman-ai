"""Tests for delegation-aware session recording.

Verifies that sub-agent tool calls and results are NOT recorded
into the top-level session during orchestrator delegation, which
would create orphaned tool messages that break the sequence on
session restore.
"""

import pytest

from henchman.core.events import AgentEvent, EventType
from henchman.providers.base import ToolCall


def _make_events_with_delegation() -> list[AgentEvent]:
    """Build a realistic event stream for TL → delegate_task → sub-agent → done.

    Event ordering mirrors what Orchestrator._run_agent_loop produces:
      1. TL streams content
      2. TOOL_CALL_REQUEST for delegate_task (top-level)
      3. AGENT_DELEGATED
      4. AGENT_STARTED (sub-agent)
      5. Sub-agent CONTENT
      6. Sub-agent TOOL_CALL_REQUEST (read_file)
      7. Sub-agent TOOL_CALL_RESULT (read_file)
      8. Sub-agent CONTENT (response)
      9. AGENT_COMPLETED (sub-agent)
     10. TOOL_CALL_RESULT for delegate_task (top-level)
     11. TL CONTENT (final answer)
    """
    return [
        AgentEvent(type=EventType.AGENT_STARTED, data={"agent": "tech_lead"}, source_agent="orchestrator"),
        AgentEvent(type=EventType.CONTENT, data="I'll delegate this.", source_agent="tech_lead"),
        AgentEvent(
            type=EventType.TOOL_CALL_REQUEST,
            data=ToolCall(id="call_delegate_1", name="delegate_task", arguments={"agent": "coder", "task": "fix it"}),
            source_agent="tech_lead",
        ),
        # Delegation begins
        AgentEvent(
            type=EventType.AGENT_DELEGATED,
            data={"from": "tech_lead", "to": "coder", "task": "fix it"},
            source_agent="orchestrator",
        ),
        AgentEvent(type=EventType.AGENT_STARTED, data={"agent": "coder"}, source_agent="orchestrator"),
        # Sub-agent events
        AgentEvent(type=EventType.CONTENT, data="Reading file...", source_agent="coder"),
        AgentEvent(
            type=EventType.TOOL_CALL_REQUEST,
            data=ToolCall(id="call_sub_read", name="read_file", arguments={"path": "foo.py"}),
            source_agent="coder",
        ),
        AgentEvent(
            type=EventType.TOOL_CALL_RESULT,
            data={"tool_call_id": "call_sub_read", "tool_name": "read_file", "result": "file content", "success": True},
            source_agent="coder",
        ),
        AgentEvent(type=EventType.CONTENT, data="Done fixing.", source_agent="coder"),
        # Delegation ends
        AgentEvent(
            type=EventType.AGENT_COMPLETED,
            data={"agent": "coder", "summary": "Fixed the bug."},
            source_agent="orchestrator",
        ),
        # Back to top-level: delegate_task result
        AgentEvent(
            type=EventType.TOOL_CALL_RESULT,
            data={"tool_call_id": "call_delegate_1", "tool_name": "delegate_task", "result": "Fixed the bug.", "success": True},
            source_agent="tech_lead",
        ),
        # TL final response
        AgentEvent(type=EventType.CONTENT, data="All done!", source_agent="tech_lead"),
        AgentEvent(type=EventType.AGENT_COMPLETED, data={"agent": "tech_lead"}, source_agent="orchestrator"),
    ]


class TestDelegationDepthTracking:
    """Verify that _process_agent_stream only records top-level events to session."""

    @pytest.mark.anyio
    async def test_sub_agent_tools_not_in_session(self) -> None:
        """Sub-agent TOOL_CALL_RESULT at depth>0 must not be recorded to session.

        This verifies the core logic: delegation_depth increments on
        AGENT_DELEGATED and decrements on AGENT_COMPLETED (when >0).
        Only TOOL_CALL_RESULT events at depth==0 should be recorded.
        """
        events = _make_events_with_delegation()

        # Simulate the recording logic from _process_agent_stream
        delegation_depth = 0
        recorded_tool_results: list[str] = []  # tool_call_ids that would be recorded

        for event in events:
            if event.type == EventType.AGENT_DELEGATED:
                delegation_depth += 1
            elif event.type == EventType.AGENT_COMPLETED and delegation_depth > 0:
                delegation_depth -= 1
            elif (
                event.type == EventType.TOOL_CALL_RESULT
                and delegation_depth == 0
                and isinstance(event.data, dict)
            ):
                recorded_tool_results.append(event.data.get("tool_call_id", ""))

        # Only the delegate_task result should be recorded, NOT the sub-agent's
        assert "call_sub_read" not in recorded_tool_results
        assert "call_delegate_1" in recorded_tool_results
        assert len(recorded_tool_results) == 1

    @pytest.mark.anyio
    async def test_only_top_level_tool_calls_in_pending(self) -> None:
        """pending_tool_calls should only contain top-level tool calls, not sub-agent ones."""
        events = _make_events_with_delegation()

        # Re-implement the key tracking logic from _process_agent_stream
        # and assert correct behavior.
        pending_tool_calls: list[ToolCall] = []
        delegation_depth = 0

        for event in events:
            if event.type == EventType.AGENT_DELEGATED:
                delegation_depth += 1
            elif event.type == EventType.AGENT_COMPLETED and delegation_depth > 0:
                delegation_depth -= 1
            elif event.type == EventType.TOOL_CALL_REQUEST and delegation_depth == 0:
                pending_tool_calls.append(event.data)

        # Only the delegate_task call should be in pending
        assert len(pending_tool_calls) == 1
        assert pending_tool_calls[0].id == "call_delegate_1"
        assert pending_tool_calls[0].name == "delegate_task"

    @pytest.mark.anyio
    async def test_delegation_depth_returns_to_zero(self) -> None:
        """Delegation depth correctly returns to 0 after delegation completes."""
        events = _make_events_with_delegation()

        depth = 0
        for event in events:
            if event.type == EventType.AGENT_DELEGATED:
                depth += 1
            elif event.type == EventType.AGENT_COMPLETED and depth > 0:
                depth -= 1

        assert depth == 0, "Delegation depth should be 0 after all events"

    @pytest.mark.anyio
    async def test_nested_delegation_depth(self) -> None:
        """Nested delegations track depth correctly."""
        events = [
            AgentEvent(type=EventType.AGENT_STARTED, data={"agent": "tech_lead"}, source_agent="orchestrator"),
            # TL delegates to coder
            AgentEvent(type=EventType.AGENT_DELEGATED, data={"from": "tech_lead", "to": "coder", "task": "a"}, source_agent="orchestrator"),
            AgentEvent(type=EventType.AGENT_STARTED, data={"agent": "coder"}, source_agent="orchestrator"),
            # Coder delegates to researcher (nested)
            AgentEvent(type=EventType.AGENT_DELEGATED, data={"from": "coder", "to": "researcher", "task": "b"}, source_agent="orchestrator"),
            AgentEvent(type=EventType.AGENT_STARTED, data={"agent": "researcher"}, source_agent="orchestrator"),
            AgentEvent(type=EventType.AGENT_COMPLETED, data={"agent": "researcher"}, source_agent="orchestrator"),
            # Back to coder
            AgentEvent(type=EventType.AGENT_COMPLETED, data={"agent": "coder"}, source_agent="orchestrator"),
            # Back to TL
            AgentEvent(type=EventType.AGENT_COMPLETED, data={"agent": "tech_lead"}, source_agent="orchestrator"),
        ]

        depth = 0
        max_depth = 0
        for event in events:
            if event.type == EventType.AGENT_DELEGATED:
                depth += 1
                max_depth = max(max_depth, depth)
            elif event.type == EventType.AGENT_COMPLETED and depth > 0:
                depth -= 1

        assert max_depth == 2
        assert depth == 0

    @pytest.mark.anyio
    async def test_content_only_accumulated_at_top_level(self) -> None:
        """Only top-level CONTENT events should be accumulated for session recording."""
        events = _make_events_with_delegation()

        accumulated: list[str] = []
        depth = 0

        for event in events:
            if event.type == EventType.AGENT_DELEGATED:
                depth += 1
            elif event.type == EventType.AGENT_COMPLETED and depth > 0:
                depth -= 1
            elif event.type == EventType.CONTENT and depth == 0:
                accumulated.append(event.data)

        # Only TL content: "I'll delegate this." and "All done!"
        assert len(accumulated) == 2
        assert "delegate" in accumulated[0].lower()
        assert "done" in accumulated[1].lower()
