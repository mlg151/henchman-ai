"""End-to-end tests for the delegate_task flow.

These tests verify the complete delegation chain:
  Tech Lead → delegate_task → Coder → tool calls → result back to Tech Lead
"""

from collections.abc import AsyncIterator
from typing import Any

import pytest

from henchman.agents.orchestrator import Orchestrator
from henchman.config.schema import Settings
from henchman.core.events import AgentEvent, EventType
from henchman.providers.base import (
    FinishReason,
    Message,
    ModelProvider,
    StreamChunk,
    ToolCall,
    ToolDeclaration,
)
from henchman.tools.base import Tool, ToolKind, ToolResult
from henchman.tools.registry import ToolRegistry

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class SequencedMockProvider(ModelProvider):
    """A mock provider that returns pre-scripted responses in order.

    Each call to chat_completion_stream pops the next response from the queue.
    Responses can be:
      - str  → emitted as STOP content
      - list[ToolCall] → emitted as TOOL_CALLS
    """

    def __init__(self, responses: list[str | list[ToolCall]]) -> None:
        self._responses = list(responses)
        self._call_index = 0
        self.call_log: list[list[Message]] = []

    @property
    def name(self) -> str:
        return "mock"

    @property
    def model(self) -> str:
        return "mock-model"

    async def chat_completion_stream(
        self,
        messages: list[Message],
        tools: list[ToolDeclaration] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[StreamChunk]:
        self.call_log.append(list(messages))
        if self._call_index >= len(self._responses):
            yield StreamChunk(
                content="(no more scripted responses)", finish_reason=FinishReason.STOP
            )
            return

        response = self._responses[self._call_index]
        self._call_index += 1

        if isinstance(response, str):
            yield StreamChunk(content=response, finish_reason=FinishReason.STOP)
        elif isinstance(response, list):
            yield StreamChunk(tool_calls=response, finish_reason=FinishReason.TOOL_CALLS)


class FakeReadFileTool(Tool):
    """A fake read_file tool that returns canned content."""

    def __init__(self, content: str = "Hello World") -> None:
        self._content = content

    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return "Read a file"

    @property
    def parameters(self) -> dict[str, object]:
        return {
            "type": "object",
            "properties": {"file_path": {"type": "string"}},
            "required": ["file_path"],
        }

    @property
    def kind(self) -> ToolKind:
        return ToolKind.READ

    async def execute(self, **kwargs: object) -> ToolResult:
        return ToolResult(content=self._content, success=True)


class FakeWriteFileTool(Tool):
    """A fake write_file tool that records writes."""

    def __init__(self) -> None:
        self.writes: list[dict[str, Any]] = []

    @property
    def name(self) -> str:
        return "write_file"

    @property
    def description(self) -> str:
        return "Write a file"

    @property
    def parameters(self) -> dict[str, object]:
        return {
            "type": "object",
            "properties": {
                "file_path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["file_path", "content"],
        }

    @property
    def kind(self) -> ToolKind:
        return ToolKind.WRITE

    async def execute(self, **kwargs: object) -> ToolResult:
        self.writes.append(dict(kwargs))
        return ToolResult(content="File written successfully", success=True)


def _collect_events(events: list[AgentEvent], event_type: EventType) -> list[AgentEvent]:
    """Filter events by type."""
    return [e for e in events if e.type == event_type]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDelegateTaskEndToEnd:
    """End-to-end tests for the full delegation lifecycle."""

    @pytest.fixture
    def tool_registry(self) -> ToolRegistry:
        """Create a tool registry with fake tools."""
        reg = ToolRegistry()
        reg.register(FakeReadFileTool("Hello World"))
        reg.register(FakeWriteFileTool())
        return reg

    @pytest.fixture
    def settings(self) -> Settings:
        return Settings()

    async def test_tech_lead_delegates_to_coder_who_uses_tools(
        self,
        tool_registry: ToolRegistry,
        settings: Settings,
    ) -> None:
        """Full flow: Tech Lead → delegate_task(coder) → coder reads file → result back."""
        provider = SequencedMockProvider(
            [
                # 1. Tech Lead: delegate to coder
                [
                    ToolCall(
                        id="tc_1",
                        name="delegate_task",
                        arguments={
                            "agent": "explorer",
                            "task": "Read hello.txt and report contents",
                        },
                    )
                ],
                # 2. Coder: call read_file
                [ToolCall(id="tc_2", name="read_file", arguments={"file_path": "hello.txt"})],
                # 3. Coder: respond after reading
                "The file says: Hello World",
                # 4. Tech Lead: synthesise after delegation result
                "Done. The file contains: Hello World.",
            ]
        )

        orchestrator = Orchestrator(
            default_provider=provider,
            tool_registry=tool_registry,
            settings=settings,
        )

        events: list[AgentEvent] = []
        async for event in orchestrator.run("What's in hello.txt?"):
            events.append(event)

        # --- Delegation should have happened ---
        delegated = _collect_events(events, EventType.AGENT_DELEGATED)
        assert len(delegated) >= 1
        assert delegated[0].data["to"] == "explorer"

        # --- Coder agent should have been started & completed ---
        started_agents = [e.data["agent"] for e in _collect_events(events, EventType.AGENT_STARTED)]
        assert "explorer" in started_agents

        completed_agents = [
            e.data["agent"] for e in _collect_events(events, EventType.AGENT_COMPLETED)
        ]
        assert "explorer" in completed_agents

        # --- There should be tool call events for read_file ---
        tool_requests = _collect_events(events, EventType.TOOL_CALL_REQUEST)
        tool_names = [e.data.name for e in tool_requests]
        assert "read_file" in tool_names

        # --- Tool results should have been yielded ---
        tool_results = _collect_events(events, EventType.TOOL_CALL_RESULT)
        assert len(tool_results) >= 1

        # --- Final Tech Lead content should reference the file ---
        content = _collect_events(events, EventType.CONTENT)
        full_text = "".join(e.data or "" for e in content)
        assert "Hello World" in full_text

        # --- Provider should have been called 4 times ---
        assert provider._call_index == 4

    async def test_coder_tool_result_is_in_coder_messages(
        self,
        tool_registry: ToolRegistry,
        settings: Settings,
    ) -> None:
        """Verify tool results from read_file go to the Coder's context, not Tech Lead's."""
        provider = SequencedMockProvider(
            [
                # 1. Tech Lead: delegate
                [
                    ToolCall(
                        id="tc_1",
                        name="delegate_task",
                        arguments={"agent": "explorer", "task": "Read the config"},
                    )
                ],
                # 2. Coder: read_file
                [ToolCall(id="tc_2", name="read_file", arguments={"file_path": "config.yaml"})],
                # 3. Coder: respond
                "Config loaded.",
                # 4. Tech Lead: respond
                "Done.",
            ]
        )

        orchestrator = Orchestrator(
            default_provider=provider,
            tool_registry=tool_registry,
            settings=settings,
        )

        events: list[AgentEvent] = []
        async for event in orchestrator.run("Load the config"):
            events.append(event)

        # The second provider call (index 1) should be the Coder's initial messages.
        # The third call (index 2) should be the Coder's messages INCLUDING the tool result.
        assert len(provider.call_log) >= 3, (
            f"Expected >= 3 provider calls, got {len(provider.call_log)}"
        )

        coder_continuation = provider.call_log[2]
        # Should have a tool message with the read_file result
        tool_messages = [m for m in coder_continuation if m.role == "tool"]
        assert len(tool_messages) >= 1, "Coder's continuation should contain tool result message"
        assert "Hello World" in (tool_messages[0].content or "")

    async def test_delegation_depth_limit(
        self,
        tool_registry: ToolRegistry,
        settings: Settings,
    ) -> None:
        """Delegation should stop if max depth is exceeded."""
        settings.agents.max_delegation_depth = 1

        provider = SequencedMockProvider(
            [
                # 1. Tech Lead delegates to coder
                [
                    ToolCall(
                        id="tc_1",
                        name="delegate_task",
                        arguments={"agent": "explorer", "task": "Implement feature"},
                    )
                ],
                # 2. Coder tries to sub-delegate to researcher (depth=2 > max=1)
                [
                    ToolCall(
                        id="tc_2",
                        name="delegate_task",
                        arguments={"agent": "explorer", "task": "Look up API docs"},
                    )
                ],
                # 3. Coder continues after depth error
                "Could not delegate, proceeding myself.",
                # 4. Tech Lead responds
                "Feature implemented.",
            ]
        )

        orchestrator = Orchestrator(
            default_provider=provider,
            tool_registry=tool_registry,
            settings=settings,
        )

        events: list[AgentEvent] = []
        async for event in orchestrator.run("Build a feature"):
            events.append(event)

        errors = _collect_events(events, EventType.ERROR)
        assert any("depth" in str(e.data).lower() for e in errors)

    async def test_delegation_to_unknown_agent(
        self,
        tool_registry: ToolRegistry,
        settings: Settings,
    ) -> None:
        """Delegating to a non-existent agent should produce an error."""
        provider = SequencedMockProvider(
            [
                [
                    ToolCall(
                        id="tc_1",
                        name="delegate_task",
                        arguments={"agent": "nonexistent", "task": "Do something"},
                    )
                ],
                "OK, that agent doesn't exist. Let me handle it.",
            ]
        )

        orchestrator = Orchestrator(
            default_provider=provider,
            tool_registry=tool_registry,
            settings=settings,
        )

        events: list[AgentEvent] = []
        async for event in orchestrator.run("Do something"):
            events.append(event)

        errors = _collect_events(events, EventType.ERROR)
        assert any("nonexistent" in str(e.data).lower() for e in errors)

    async def test_tech_lead_uses_own_tools_without_delegation(
        self,
        tool_registry: ToolRegistry,
        settings: Settings,
    ) -> None:
        """Tech Lead should be able to use tools directly without delegating."""
        provider = SequencedMockProvider(
            [
                # 1. Tech Lead calls read_file directly
                [ToolCall(id="tc_1", name="read_file", arguments={"file_path": "hello.txt"})],
                # 2. Tech Lead responds after reading
                "The file says Hello World.",
            ]
        )

        orchestrator = Orchestrator(
            default_provider=provider,
            tool_registry=tool_registry,
            settings=settings,
        )

        events: list[AgentEvent] = []
        async for event in orchestrator.run("Read hello.txt"):
            events.append(event)

        # Tool should have been executed
        tool_results = _collect_events(events, EventType.TOOL_CALL_RESULT)
        assert len(tool_results) >= 1

        # Content should reflect file contents
        content = "".join(e.data or "" for e in _collect_events(events, EventType.CONTENT))
        assert "Hello World" in content

    async def test_multiple_tool_calls_in_single_turn(
        self,
        tool_registry: ToolRegistry,
        settings: Settings,
    ) -> None:
        """Agent should handle multiple tool calls in same response."""
        provider = SequencedMockProvider(
            [
                # Tech Lead calls read_file twice in one turn
                [
                    ToolCall(id="tc_1", name="read_file", arguments={"file_path": "a.txt"}),
                    ToolCall(id="tc_2", name="read_file", arguments={"file_path": "b.txt"}),
                ],
                # Tech Lead responds after both reads
                "Both files say Hello World.",
            ]
        )

        orchestrator = Orchestrator(
            default_provider=provider,
            tool_registry=tool_registry,
            settings=settings,
        )

        events: list[AgentEvent] = []
        async for event in orchestrator.run("Read both files"):
            events.append(event)

        # Both tool calls executed
        tool_results = _collect_events(events, EventType.TOOL_CALL_RESULT)
        assert len(tool_results) == 2

    async def test_delegate_plus_tool_in_same_turn(
        self,
        tool_registry: ToolRegistry,
        settings: Settings,
    ) -> None:
        """Handle delegate_task alongside a regular tool call in same response."""
        provider = SequencedMockProvider(
            [
                # Tech Lead reads a file AND delegates simultaneously
                [
                    ToolCall(id="tc_1", name="read_file", arguments={"file_path": "plan.txt"}),
                    ToolCall(
                        id="tc_2",
                        name="delegate_task",
                        arguments={"agent": "explorer", "task": "Implement the plan"},
                    ),
                ],
                # Coder runs
                "Plan implemented.",
                # Tech Lead continues
                "All done. File was read and plan implemented.",
            ]
        )

        orchestrator = Orchestrator(
            default_provider=provider,
            tool_registry=tool_registry,
            settings=settings,
        )

        events: list[AgentEvent] = []
        async for event in orchestrator.run("Read plan and implement"):
            events.append(event)

        # Regular tool result
        tool_results = _collect_events(events, EventType.TOOL_CALL_RESULT)
        assert len(tool_results) >= 1

        # Delegation happened
        delegated = _collect_events(events, EventType.AGENT_DELEGATED)
        assert len(delegated) >= 1

    async def test_coder_multiple_tool_iterations(
        self,
        tool_registry: ToolRegistry,
        settings: Settings,
    ) -> None:
        """Coder should be able to read a file, then write, across multiple turns."""
        write_tool = FakeWriteFileTool()
        tool_registry.unregister("write_file")
        tool_registry.register(write_tool)

        provider = SequencedMockProvider(
            [
                # 1. Tech Lead delegates
                [
                    ToolCall(
                        id="tc_1",
                        name="delegate_task",
                        arguments={
                            "agent": "explorer",
                            "task": "Read hello.txt then write output.txt",
                        },
                    )
                ],
                # 2. Coder reads
                [ToolCall(id="tc_2", name="read_file", arguments={"file_path": "hello.txt"})],
                # 3. Coder writes after reading
                [
                    ToolCall(
                        id="tc_3",
                        name="write_file",
                        arguments={"file_path": "output.txt", "content": "Hello World"},
                    )
                ],
                # 4. Coder reports
                "Read hello.txt and wrote output.txt.",
                # 5. Tech Lead wraps up
                "Coder finished. Output written.",
            ]
        )

        orchestrator = Orchestrator(
            default_provider=provider,
            tool_registry=tool_registry,
            settings=settings,
        )

        events: list[AgentEvent] = []
        async for event in orchestrator.run("Process hello.txt"):
            events.append(event)

        # Write tool should have been called
        assert len(write_tool.writes) == 1
        assert write_tool.writes[0]["file_path"] == "output.txt"

        # Full chain completed
        assert provider._call_index == 5

    async def test_streaming_delegation_summary_not_doubled(
        self,
        tool_registry: ToolRegistry,
        settings: Settings,
    ) -> None:
        """Summary from a streaming sub-agent should not contain duplicated content.

        Real providers stream content in multiple chunks before sending STOP.
        The Agent yields each chunk *and* the accumulated content on STOP,
        but the delegation summary must only contain the text once.
        """

        class StreamingMockProvider(ModelProvider):
            """Mock that streams string responses in multiple chunks."""

            def __init__(self, responses: list[str | list[ToolCall]]) -> None:
                self._responses = list(responses)
                self._call_index = 0
                self.call_log: list[list[Message]] = []

            @property
            def name(self) -> str:
                return "mock-stream"

            @property
            def model(self) -> str:
                return "mock-stream-model"

            async def chat_completion_stream(
                self,
                messages: list[Message],
                tools: list[ToolDeclaration] | None = None,
                **kwargs: Any,
            ) -> AsyncIterator[StreamChunk]:
                self.call_log.append(list(messages))
                if self._call_index >= len(self._responses):
                    yield StreamChunk(
                        content="(exhausted)",
                        finish_reason=FinishReason.STOP,
                    )
                    return

                response = self._responses[self._call_index]
                self._call_index += 1

                if isinstance(response, list):
                    yield StreamChunk(
                        tool_calls=response,
                        finish_reason=FinishReason.TOOL_CALLS,
                    )
                else:
                    # Simulate real streaming: split into word-sized chunks
                    words = response.split(" ")
                    for word in words[:-1]:
                        yield StreamChunk(content=word + " ")
                    # Last word arrives with STOP
                    yield StreamChunk(
                        content=words[-1],
                        finish_reason=FinishReason.STOP,
                    )

        provider = StreamingMockProvider(
            [
                # 1. Tech Lead delegates
                [
                    ToolCall(
                        id="tc_1",
                        name="delegate_task",
                        arguments={
                            "agent": "explorer",
                            "task": "Fix the bug",
                        },
                    )
                ],
                # 2. Coder streams a response
                "I fixed the bug in main.py",
                # 3. Tech Lead continues
                "Bug is fixed.",
            ]
        )

        orchestrator = Orchestrator(
            default_provider=provider,
            tool_registry=tool_registry,
            settings=settings,
        )

        events: list[AgentEvent] = []
        async for event in orchestrator.run("Fix the bug"):
            events.append(event)

        # Shared context should contain the summary exactly once
        assert len(orchestrator.shared_context) == 1
        summary = orchestrator.shared_context[0]["summary"]
        assert summary == "I fixed the bug in main.py"

        # The TOOL_CALL_RESULT for the delegation should carry the real summary
        delegation_results = [
            e
            for e in events
            if e.type == EventType.TOOL_CALL_RESULT
            and isinstance(e.data, dict)
            and e.data.get("tool_name") == "delegate_task"
        ]
        assert len(delegation_results) == 1
        assert "I fixed the bug" in delegation_results[0].data["result"]
        assert delegation_results[0].data["success"] is True

    async def test_ledger_injected_into_tech_lead_context(
        self,
        tool_registry: ToolRegistry,
        settings: Settings,
    ) -> None:
        """Task ledger should be appended to the delegation tool result in Tech Lead's messages."""
        provider = SequencedMockProvider(
            [
                # 1. Tech Lead delegates to coder
                [
                    ToolCall(
                        id="tc_1",
                        name="delegate_task",
                        arguments={
                            "agent": "explorer",
                            "task": "Fix auth bug",
                        },
                    )
                ],
                # 2. Coder responds
                "Fixed the auth bug in auth.py",
                # 3. Tech Lead delegates to tester
                [
                    ToolCall(
                        id="tc_2",
                        name="delegate_task",
                        arguments={
                            "agent": "explorer",
                            "task": "Run auth tests",
                        },
                    )
                ],
                # 4. Tester responds
                "All 12 auth tests pass",
                # 5. Tech Lead synthesizes
                "Auth bug fixed and tested.",
            ]
        )

        orchestrator = Orchestrator(
            default_provider=provider,
            tool_registry=tool_registry,
            settings=settings,
        )

        events: list[AgentEvent] = []
        async for event in orchestrator.run("Fix the auth bug and test it"):
            events.append(event)

        # Ledger should exist and track both delegations
        assert orchestrator.ledger is not None
        assert orchestrator.ledger.goal == "Fix the auth bug and test it"
        assert len(orchestrator.ledger.delegations) == 2

        # Both should be completed
        from henchman.agents.ledger import DelegationStatus

        assert orchestrator.ledger.delegations[0].status == DelegationStatus.COMPLETED
        assert orchestrator.ledger.delegations[1].status == DelegationStatus.COMPLETED

        # Tech Lead's messages should contain the ledger text.
        # The 3rd provider call (index 2) is Tech Lead after first delegation.
        # Check that the tool result message contains the ledger.
        tl_messages_after_first = provider.call_log[2]
        tool_msgs = [m for m in tl_messages_after_first if m.role == "tool"]
        assert any("TASK LEDGER" in (m.content or "") for m in tool_msgs)
        # First ledger should show 1 done
        first_tool = next(m for m in tool_msgs if "TASK LEDGER" in (m.content or ""))
        assert "1 done" in first_tool.content

        # After second delegation (call_log[4] = Tech Lead final turn),
        # ledger should show 2 done. Use the LAST tool msg with a ledger.
        tl_messages_after_second = provider.call_log[4]
        tool_msgs_2 = [
            m
            for m in tl_messages_after_second
            if m.role == "tool" and "TASK LEDGER" in (m.content or "")
        ]
        assert len(tool_msgs_2) >= 2
        assert "2 done" in tool_msgs_2[-1].content

    async def test_ledger_tracks_failed_delegation(
        self,
        tool_registry: ToolRegistry,
        settings: Settings,
    ) -> None:
        """Ledger should record failures for unknown agents."""
        provider = SequencedMockProvider(
            [
                # Tech Lead delegates to nonexistent agent
                [
                    ToolCall(
                        id="tc_1",
                        name="delegate_task",
                        arguments={
                            "agent": "nonexistent",
                            "task": "Do something",
                        },
                    )
                ],
                # Tech Lead handles the failure
                "That agent doesn't exist. I'll handle it myself.",
            ]
        )

        orchestrator = Orchestrator(
            default_provider=provider,
            tool_registry=tool_registry,
            settings=settings,
        )

        events: list[AgentEvent] = []
        async for event in orchestrator.run("Do something"):
            events.append(event)

        assert orchestrator.ledger is not None
        assert len(orchestrator.ledger.delegations) == 1

        from henchman.agents.ledger import DelegationStatus

        assert orchestrator.ledger.delegations[0].status == DelegationStatus.FAILED
