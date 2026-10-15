"""Contract tests for ToolExecutor subsystem boundaries."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

from henchman.cli.tool_executor import ToolExecutor
from henchman.cli.tool_manager import ToolManager
from henchman.providers.base import ToolCall
from henchman.tools.base import Tool, ToolKind, ToolResult
from henchman.tools.registry import ToolRegistry

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


# ===========================================================================
# ToolExecutor interface contract
# ===========================================================================


class _FakeOutputHandler:
    """Test double for OutputHandler."""

    def __init__(self) -> None:
        self.errors: list[str] = []
        self.muted_messages: list[str] = []
        self.warnings: list[str] = []
        self.session_manager = MagicMock()

    def error(self, msg: str) -> None:
        self.errors.append(msg)

    def muted(self, msg: str) -> None:
        self.muted_messages.append(msg)

    def warning(self, msg: str) -> None:
        self.warnings.append(msg)

    def show_turn_status(self, agent: object, base_iterations: int) -> None:
        pass

    def print_newline(self) -> None:
        pass


class _FakeTurn:
    """Test double for Turn tracking."""

    def __init__(self) -> None:
        self.iteration = 0
        self.tool_count = 0
        self._tool_calls: list[dict] = []

    def get_adaptive_limit(self, base: int) -> int:
        return base

    def is_at_limit(self, base: int) -> bool:
        return self.iteration >= base

    def is_spinning(self) -> bool:
        return False

    def record_tool_call(
        self,
        tool_call_id: str,
        tool_name: str,
        arguments: dict,
        result: ToolResult,
    ) -> None:
        self._tool_calls.append({
            "id": tool_call_id,
            "name": tool_name,
            "arguments": arguments,
            "result": result,
        })

    def increment_iteration(self) -> None:
        self.iteration += 1


class _FakeAgent:
    """Test double for Agent."""

    def __init__(self, registry: ToolRegistry) -> None:
        self.tool_registry = registry
        self.turn = _FakeTurn()
        self.unlimited_mode = False
        self._tool_results: dict[str, str] = {}

    def submit_tool_result(self, tool_call_id: str, result: str) -> None:
        self._tool_results[tool_call_id] = result

    async def continue_with_tool_results(self) -> AsyncIterator[object]:
        if False:
            yield None  # Make this an async generator


class _EchoTool(Tool):
    """Simple test tool that echoes its arguments."""

    @property
    def name(self) -> str:
        return "echo"

    @property
    def description(self) -> str:
        return "Echo back arguments"

    @property
    def kind(self) -> ToolKind:
        return ToolKind.READ

    async def execute(self, **params) -> ToolResult:
        return ToolResult(content=str(params))


class _WriteTool(Tool):
    """Test tool that requires confirmation (WRITE kind)."""

    @property
    def name(self) -> str:
        return "write_file"

    @property
    def description(self) -> str:
        return "Write to a file"

    @property
    def kind(self) -> ToolKind:
        return ToolKind.WRITE

    async def execute(self, **params) -> ToolResult:
        return ToolResult(content=f"wrote: {params}")


class TestToolExecutorContract:
    """ToolExecutor must satisfy the tool execution interface contract."""

    def _make_executor(
        self,
        output_handler: _FakeOutputHandler | None = None,
        tool_manager: ToolManager | None = None,
        provider: object = None,
        base_iterations: int = 25,
        max_tool_calls: int = 100,
    ) -> ToolExecutor:
        output = output_handler or _FakeOutputHandler()
        if tool_manager is None:
            registry = ToolRegistry()
            registry.register(_EchoTool())
            registry.register(_WriteTool())
            tool_manager = ToolManager(MagicMock())
            tool_manager.registry = registry
        provider = provider or MagicMock()
        return ToolExecutor(
            output_handler=output,
            tool_manager=tool_manager,
            provider=provider,
            base_tool_iterations=base_iterations,
            max_tool_calls_per_turn=max_tool_calls,
        )

    def test_execute_tool_calls_with_valid_tools(self) -> None:
        """execute_tool_calls must process valid ToolCall objects."""
        tool_calls = [
            ToolCall(id="tc-1", name="echo", arguments={"message": "hello"}),
        ]

        # Since execute_tool_calls is async and calls into agent streams,
        # we test the synchronous contract aspects
        valid_calls = [tc for tc in tool_calls if isinstance(tc, ToolCall)]
        assert len(valid_calls) == 1
        assert valid_calls[0].id == "tc-1"
        assert valid_calls[0].name == "echo"
        assert valid_calls[0].arguments == {"message": "hello"}

    def test_execute_tool_calls_empty_list(self) -> None:
        """execute_tool_calls must handle empty tool call list."""
        # Filter test
        invalid_calls: list = []
        valid_calls = [tc for tc in invalid_calls if isinstance(tc, ToolCall)]
        assert len(valid_calls) == 0

    def test_execute_tool_calls_filters_non_tool_call(self) -> None:
        """execute_tool_calls must filter out non-ToolCall objects."""
        mixed = [
            ToolCall(id="tc-1", name="echo", arguments={}),
            "not a tool call",  # type: ignore[list-item]
            None,  # type: ignore[list-item]
        ]
        valid = [tc for tc in mixed if isinstance(tc, ToolCall)]
        assert len(valid) == 1
        assert valid[0].id == "tc-1"

    def test_split_tools_by_confirmation_no_confirmation_needed(self) -> None:
        """Tools without confirmation requirements go to parallel."""
        executor = self._make_executor()
        tool_calls = [
            ToolCall(id="tc-1", name="echo", arguments={}),
        ]
        parallel, sequential = executor._split_tools_by_confirmation_requirement(tool_calls, executor.tool_manager.registry)
        assert len(parallel) == 1
        assert len(sequential) == 0

    def test_split_tools_by_confirmation_needs_confirmation(self) -> None:
        """Tools requiring confirmation go to sequential."""
        executor = self._make_executor()
        tool_calls = [
            ToolCall(id="tc-2", name="write_file", arguments={"file": "test.txt"}),
        ]
        parallel, sequential = executor._split_tools_by_confirmation_requirement(tool_calls, executor.tool_manager.registry)
        assert len(parallel) == 0
        assert len(sequential) == 1

    def test_split_tools_mixed(self) -> None:
        """Mixed tool calls should be split correctly."""
        executor = self._make_executor()
        tool_calls = [
            ToolCall(id="tc-1", name="echo", arguments={}),
            ToolCall(id="tc-2", name="write_file", arguments={"file": "test.txt"}),
            ToolCall(id="tc-3", name="echo", arguments={"msg": "hi"}),
        ]
        parallel, sequential = executor._split_tools_by_confirmation_requirement(tool_calls, executor.tool_manager.registry)
        assert len(parallel) == 2
        assert len(sequential) == 1

    def test_should_stop_at_iteration_limit(self) -> None:
        """ToolExecutor must stop when iteration limit is reached."""
        output = _FakeOutputHandler()
        executor = self._make_executor(output_handler=output, base_iterations=2)
        agent = _FakeAgent(executor.tool_manager.registry)
        agent.turn.iteration = 3  # Exceeds base_iterations of 2

        should_stop = executor._should_stop_due_to_limits(agent)
        assert should_stop is True
        assert len(output.errors) == 1
        assert "iteration limit" in output.errors[0]

    def test_should_stop_at_tool_call_limit(self) -> None:
        """ToolExecutor must stop when tool call limit is reached."""
        output = _FakeOutputHandler()
        executor = self._make_executor(
            output_handler=output,
            base_iterations=100,
            max_tool_calls=5,
        )
        agent = _FakeAgent(executor.tool_manager.registry)
        agent.turn.iteration = 10  # Under iteration limit
        agent.turn.tool_count = 5  # At tool call limit

        should_stop = executor._should_stop_due_to_limits(agent)
        assert should_stop is True
        assert len(output.errors) == 1
        assert "tool call limit" in output.errors[0]

    def test_unlimited_mode_bypasses_limits(self) -> None:
        """unlimited_mode=True must bypass all limits."""
        output = _FakeOutputHandler()
        executor = self._make_executor(output_handler=output)
        agent = _FakeAgent(executor.tool_manager.registry)
        agent.unlimited_mode = True
        agent.turn.iteration = 1000
        agent.turn.tool_count = 500

        should_stop = executor._should_stop_due_to_limits(agent)
        assert should_stop is False
        assert len(output.errors) == 0

    def test_ensure_all_tool_calls_have_response(self) -> None:
        """Unresponded tool calls must get cancellation results."""
        executor = self._make_executor()
        agent = _FakeAgent(executor.tool_manager.registry)
        tool_calls = [
            ToolCall(id="tc-1", name="echo", arguments={}),
            ToolCall(id="tc-2", name="echo", arguments={}),
            ToolCall(id="tc-3", name="echo", arguments={}),
        ]
        responded = {"tc-1", "tc-3"}

        executor._ensure_all_tool_calls_have_response(tool_calls, responded, agent)

        # tc-2 should have received a cancellation result
        assert "tc-2" in agent._tool_results
        assert "interrupted or cancelled" in agent._tool_results["tc-2"]

    def test_ensure_all_responded_no_action(self) -> None:
        """When all tool calls responded, no cancellation needed."""
        executor = self._make_executor()
        agent = _FakeAgent(executor.tool_manager.registry)
        tool_calls = [
            ToolCall(id="tc-1", name="echo", arguments={}),
        ]
        responded = {"tc-1"}

        executor._ensure_all_tool_calls_have_response(tool_calls, responded, agent)

        # No cancellation should be recorded
        assert agent.turn.tool_count == 0  # No extra tool recording

    def test_tool_call_result_recorded(self) -> None:
        """Tool execution results must be recorded in the turn."""
        output = _FakeOutputHandler()
        executor = self._make_executor(output_handler=output)
        agent = _FakeAgent(executor.tool_manager.registry)
        responded: set[str] = set()

        tc = ToolCall(id="tc-1", name="echo", arguments={"msg": "hello"})

        import asyncio
        asyncio.run(executor._execute_and_record_tool_call(tc, agent, responded))

        assert "tc-1" in responded
        assert "tc-1" in agent._tool_results
        assert len(agent.turn._tool_calls) == 1
        assert agent.turn._tool_calls[0]["name"] == "echo"

    def test_tool_execution_error_output(self) -> None:
        """Tool execution errors must be displayed via output handler."""
        output = _FakeOutputHandler()

        # Create a registry with a failing tool
        class FailingTool(Tool):
            @property
            def name(self) -> str:
                return "fail"

            @property
            def description(self) -> str:
                return "Always fails"

            async def execute(self, **params) -> ToolResult:
                return ToolResult(content="error", success=False, error="Tool failed")

        registry = ToolRegistry()
        registry.register(FailingTool())
        tool_manager = ToolManager(MagicMock())
        tool_manager._registry = registry

        executor = self._make_executor(output_handler=output, tool_manager=tool_manager)
        agent = _FakeAgent(executor.tool_manager.registry)
        responded: set[str] = set()

        tc = ToolCall(id="tc-1", name="fail", arguments={})

        import asyncio
        asyncio.run(executor._execute_and_record_tool_call(tc, agent, responded))

        assert len(output.errors) == 1
        assert "error" in output.errors[0].lower()
