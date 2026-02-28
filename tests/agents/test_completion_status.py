"""Tests for CompletionStatus verification in the Orchestrator.

Verifies that agents which end without performing any tool calls are
correctly reported as NO_WORK_DONE instead of COMPLETED.
"""

from unittest.mock import MagicMock

import pytest

from henchman.agents.orchestrator import CompletionStatus, Orchestrator
from henchman.core.events import AgentEvent, EventType
from henchman.providers.base import FinishReason, ModelProvider, StreamChunk, ToolCall


@pytest.fixture
def mock_provider():
    """Create a mock model provider."""
    return MagicMock(spec=ModelProvider)


# ---------------------------------------------------------------------------
# CompletionStatus enum
# ---------------------------------------------------------------------------


class TestCompletionStatusEnum:
    """Tests for the CompletionStatus enum values."""

    def test_completed_value(self):
        assert CompletionStatus.COMPLETED.value == "completed"

    def test_no_work_done_value(self):
        assert CompletionStatus.NO_WORK_DONE.value == "no_work_done"

    def test_stalled_value(self):
        assert CompletionStatus.STALLED.value == "stalled"

    def test_timed_out_value(self):
        assert CompletionStatus.TIMED_OUT.value == "timed_out"

    def test_all_members(self):
        members = {m.name for m in CompletionStatus}
        assert members == {"COMPLETED", "NO_WORK_DONE", "STALLED", "TIMED_OUT"}


# ---------------------------------------------------------------------------
# _assess_completion
# ---------------------------------------------------------------------------


class TestAssessCompletion:
    """Tests for the Orchestrator._assess_completion method."""

    def test_no_tool_calls_returns_no_work_done(self, mock_provider):
        """Agent that made zero tool calls is flagged as NO_WORK_DONE."""
        orchestrator = Orchestrator(default_provider=mock_provider)
        orchestrator._last_loop_tool_call_count = 0

        agent = MagicMock()
        agent._stall = MagicMock(failure=False)

        assert orchestrator._assess_completion(agent) == CompletionStatus.NO_WORK_DONE

    def test_tool_calls_returns_completed(self, mock_provider):
        """Agent that made tool calls is flagged as COMPLETED."""
        orchestrator = Orchestrator(default_provider=mock_provider)
        orchestrator._last_loop_tool_call_count = 5

        agent = MagicMock()
        agent._stall = MagicMock(failure=False)

        assert orchestrator._assess_completion(agent) == CompletionStatus.COMPLETED

    def test_stall_failure_returns_stalled(self, mock_provider):
        """Agent that stalled after nudges is flagged as STALLED."""
        orchestrator = Orchestrator(default_provider=mock_provider)
        orchestrator._last_loop_tool_call_count = 0

        agent = MagicMock()
        agent._stall = MagicMock(failure=True)

        assert orchestrator._assess_completion(agent) == CompletionStatus.STALLED

    def test_stall_failure_overrides_tool_count(self, mock_provider):
        """Stall failure takes priority even if some tool calls were made."""
        orchestrator = Orchestrator(default_provider=mock_provider)
        orchestrator._last_loop_tool_call_count = 3

        agent = MagicMock()
        agent._stall = MagicMock(failure=True)

        assert orchestrator._assess_completion(agent) == CompletionStatus.STALLED

    def test_missing_stall_failure_attr(self, mock_provider):
        """Agent without _stall_failure attribute defaults to checking tool count."""
        orchestrator = Orchestrator(default_provider=mock_provider)
        orchestrator._last_loop_tool_call_count = 2

        agent = MagicMock(spec=[])  # Empty spec so getattr returns default

        assert orchestrator._assess_completion(agent) == CompletionStatus.COMPLETED

    def test_missing_stall_failure_no_tools(self, mock_provider):
        """Agent without _stall_failure attr and no tools → NO_WORK_DONE."""
        orchestrator = Orchestrator(default_provider=mock_provider)
        orchestrator._last_loop_tool_call_count = 0

        agent = MagicMock(spec=[])

        assert orchestrator._assess_completion(agent) == CompletionStatus.NO_WORK_DONE


# ---------------------------------------------------------------------------
# Orchestrator.run() integration with CompletionStatus
# ---------------------------------------------------------------------------


class TestRunCompletionStatus:
    """Tests for completion status in Orchestrator.run()."""

    @pytest.mark.asyncio
    async def test_no_tool_calls_emits_error_and_no_work_done(self, mock_provider):
        """When the tech lead makes no tool calls, run() emits ERROR + NO_WORK_DONE status."""
        # Agent just says something and stops — no tool calls
        chunk = StreamChunk(
            content="Let me refactor this...", finish_reason=FinishReason.STOP
        )

        async def async_gen(*_args, **_kwargs):
            yield chunk

        mock_provider.chat_completion_stream.return_value = async_gen()

        orchestrator = Orchestrator(default_provider=mock_provider)

        events = []
        async for event in orchestrator.run("Improve something"):
            events.append(event)

        # Should have an ERROR event about no actions
        error_events = [e for e in events if e.type == EventType.ERROR]
        assert any("without performing any actions" in str(e.data) for e in error_events)

        # The AGENT_COMPLETED event should have status=no_work_done
        completed_events = [
            e for e in events if e.type == EventType.AGENT_COMPLETED
        ]
        assert len(completed_events) == 1
        assert completed_events[0].data["status"] == "no_work_done"
        assert completed_events[0].data["agent"] == "tech_lead"

        # Orchestrator should track the status
        assert orchestrator.last_completion_status == CompletionStatus.NO_WORK_DONE

    @pytest.mark.asyncio
    async def test_with_tool_calls_emits_completed(self, mock_provider):
        """When the tech lead makes tool calls, run() emits COMPLETED status."""
        # 1. Tech Lead calls a tool
        tc = ToolCall(id="call_1", name="ls", arguments={"path": "."})
        chunk1 = StreamChunk(tool_calls=[tc], finish_reason=FinishReason.TOOL_CALLS)

        # 2. Tech Lead finishes
        chunk2 = StreamChunk(content="Done.", finish_reason=FinishReason.STOP)

        call_count = 0

        async def side_effect(*_args, **_kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                yield chunk1
            else:
                yield chunk2

        mock_provider.chat_completion_stream.side_effect = side_effect

        orchestrator = Orchestrator(default_provider=mock_provider)
        # Register a mock tool so ls doesn't fail
        from henchman.tools.base import Tool, ToolKind, ToolResult

        class MockLsTool(Tool):
            @property
            def name(self) -> str:
                return "ls"

            @property
            def description(self) -> str:
                return "List files"

            @property
            def parameters(self) -> dict[str, object]:
                return {"type": "object", "properties": {"path": {"type": "string"}}}

            @property
            def kind(self) -> ToolKind:
                return ToolKind.READ

            async def execute(self, **params: object) -> ToolResult:
                return ToolResult(content="file.txt")

        orchestrator.tool_registry.register(MockLsTool())

        events = []
        async for event in orchestrator.run("List files"):
            events.append(event)

        # Should NOT have an ERROR about no actions
        error_events = [e for e in events if e.type == EventType.ERROR]
        assert not any("without performing any actions" in str(e.data) for e in error_events)

        # The AGENT_COMPLETED event should have status=completed
        completed_events = [
            e for e in events if e.type == EventType.AGENT_COMPLETED
        ]
        assert len(completed_events) == 1
        assert completed_events[0].data["status"] == "completed"

        assert orchestrator.last_completion_status == CompletionStatus.COMPLETED


# ---------------------------------------------------------------------------
# Orchestrator.run_direct() integration with CompletionStatus
# ---------------------------------------------------------------------------


class TestRunDirectCompletionStatus:
    """Tests for completion status in Orchestrator.run_direct()."""

    @pytest.mark.asyncio
    async def test_run_direct_no_work_done(self, mock_provider):
        """run_direct() emits NO_WORK_DONE when specialist makes no tool calls."""
        chunk = StreamChunk(
            content="I would do the work...", finish_reason=FinishReason.STOP
        )

        async def async_gen(*_args, **_kwargs):
            yield chunk

        mock_provider.chat_completion_stream.return_value = async_gen()

        orchestrator = Orchestrator(default_provider=mock_provider)

        events = []
        async for event in orchestrator.run_direct("explorer", "Find files"):
            events.append(event)

        # Should have an ERROR event
        error_events = [e for e in events if e.type == EventType.ERROR]
        assert any("without performing any actions" in str(e.data) for e in error_events)

        # The AGENT_COMPLETED should report no_work_done
        completed_events = [
            e for e in events if e.type == EventType.AGENT_COMPLETED
        ]
        assert len(completed_events) == 1
        assert completed_events[0].data["status"] == "no_work_done"
        assert completed_events[0].data["agent"] == "explorer"

        assert orchestrator.last_completion_status == CompletionStatus.NO_WORK_DONE


# ---------------------------------------------------------------------------
# Delegation completion status
# ---------------------------------------------------------------------------


class TestDelegationCompletionStatus:
    """Tests for completion status in delegated agent runs."""

    @pytest.mark.asyncio
    async def test_delegation_no_work_includes_status(self, mock_provider):
        """When a delegated agent does no work, AGENT_COMPLETED includes no_work_done."""
        # 1. Tech Lead delegates
        tc = ToolCall(
            id="call_1",
            name="delegate_task",
            arguments={"agent": "explorer", "task": "Find bugs"},
        )
        chunk_tl_1 = StreamChunk(tool_calls=[tc], finish_reason=FinishReason.TOOL_CALLS)
        chunk_tl_2 = StreamChunk(content="Ok.", finish_reason=FinishReason.STOP)

        # 2. Explorer just narrates without tool calls
        chunk_explorer = StreamChunk(
            content="I would search for bugs...", finish_reason=FinishReason.STOP
        )

        call_count = 0

        async def side_effect(*_args, **_kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                yield chunk_tl_1
            elif call_count == 2:
                yield chunk_explorer
            else:
                yield chunk_tl_2

        mock_provider.chat_completion_stream.side_effect = side_effect

        orchestrator = Orchestrator(default_provider=mock_provider)

        events = []
        async for event in orchestrator.run("Find bugs"):
            events.append(event)

        # Find the explorer's AGENT_COMPLETED event
        explorer_completed = [
            e
            for e in events
            if e.type == EventType.AGENT_COMPLETED
            and isinstance(e.data, dict)
            and e.data.get("agent") == "explorer"
        ]
        assert len(explorer_completed) == 1
        assert explorer_completed[0].data["status"] == "no_work_done"


# ---------------------------------------------------------------------------
# Orchestrator init
# ---------------------------------------------------------------------------


class TestOrchestratorInit:
    """Tests for CompletionStatus-related initialization."""

    def test_initial_completion_status(self, mock_provider):
        """Orchestrator starts with COMPLETED as default status."""
        orchestrator = Orchestrator(default_provider=mock_provider)
        assert orchestrator.last_completion_status == CompletionStatus.COMPLETED

    def test_initial_loop_tool_call_count(self, mock_provider):
        """Orchestrator starts with 0 loop tool call count."""
        orchestrator = Orchestrator(default_provider=mock_provider)
        assert orchestrator._last_loop_tool_call_count == 0


# ---------------------------------------------------------------------------
# Tool executor rendering
# ---------------------------------------------------------------------------


class TestToolExecutorCompletionRendering:
    """Tests for ToolExecutor rendering different completion statuses."""

    def _make_executor(self):
        """Create a ToolExecutor with mocked dependencies."""
        from henchman.cli.output_handler import OutputHandler
        from henchman.cli.tool_executor import ToolExecutor
        from henchman.cli.tool_manager import ToolManager

        output_handler = MagicMock(spec=OutputHandler)
        tool_manager = MagicMock(spec=ToolManager)
        tool_manager.registry = MagicMock()
        provider = MagicMock(spec=ModelProvider)

        executor = ToolExecutor(
            output_handler=output_handler,
            tool_manager=tool_manager,
            provider=provider,
        )
        return executor, output_handler

    def test_completed_renders_muted(self):
        """Status 'completed' renders the standard muted message."""
        executor, output_handler = self._make_executor()
        event = AgentEvent(
            type=EventType.AGENT_COMPLETED,
            data={"agent": "tech_lead", "status": "completed"},
        )
        executor._handle_agent_completed_event(event)
        output_handler.muted.assert_called_once()
        assert "completed work" in output_handler.muted.call_args[0][0]

    def test_no_work_done_renders_warning(self):
        """Status 'no_work_done' renders a warning message."""
        executor, output_handler = self._make_executor()
        event = AgentEvent(
            type=EventType.AGENT_COMPLETED,
            data={"agent": "tech_lead", "status": "no_work_done"},
        )
        executor._handle_agent_completed_event(event)
        output_handler.warning.assert_called_once()
        assert "without making changes" in output_handler.warning.call_args[0][0]

    def test_stalled_renders_error(self):
        """Status 'stalled' renders an error message."""
        executor, output_handler = self._make_executor()
        event = AgentEvent(
            type=EventType.AGENT_COMPLETED,
            data={"agent": "explorer", "status": "stalled"},
        )
        executor._handle_agent_completed_event(event)
        output_handler.error.assert_called_once()
        assert "stalled" in output_handler.error.call_args[0][0]

    def test_timed_out_renders_warning(self):
        """Status 'timed_out' renders a warning message."""
        executor, output_handler = self._make_executor()
        event = AgentEvent(
            type=EventType.AGENT_COMPLETED,
            data={"agent": "engineer", "status": "timed_out"},
        )
        executor._handle_agent_completed_event(event)
        output_handler.warning.assert_called_once()
        assert "turn limit" in output_handler.warning.call_args[0][0]

    def test_missing_status_defaults_to_completed(self):
        """Events without a status field render as completed (backward compat)."""
        executor, output_handler = self._make_executor()
        event = AgentEvent(
            type=EventType.AGENT_COMPLETED,
            data={"agent": "tech_lead"},
        )
        executor._handle_agent_completed_event(event)
        output_handler.muted.assert_called_once()
        assert "completed work" in output_handler.muted.call_args[0][0]

    def test_unknown_status_defaults_to_completed(self):
        """Unknown status values fall through to the completed message."""
        executor, output_handler = self._make_executor()
        event = AgentEvent(
            type=EventType.AGENT_COMPLETED,
            data={"agent": "tech_lead", "status": "some_future_value"},
        )
        executor._handle_agent_completed_event(event)
        output_handler.muted.assert_called_once()
        assert "completed work" in output_handler.muted.call_args[0][0]
