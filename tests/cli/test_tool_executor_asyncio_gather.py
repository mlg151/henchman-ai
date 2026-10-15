"""Test that async gather in execute_tool_calls handles failures gracefully.

BUG-005: asyncio.gather() without return_exceptions=True causes silent
cancellation of parallel tool calls when one raises.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from henchman.cli.tool_executor import ToolExecutor
from henchman.cli.tool_manager import ToolManager
from henchman.providers.base import ToolCall
from henchman.tools.base import Tool, ToolKind, ToolResult
from henchman.tools.registry import ToolRegistry

# ===========================================================================
# Test doubles
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

    async def continue_with_tool_results(self):
        if False:
            yield None  # Make this an async generator


# ===========================================================================
# Test tools that exercise the return_exceptions boundary
# ===========================================================================


class _EchoTool(Tool):
    """Simple test tool that completes successfully."""

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


class _DelayedSuccessTool(Tool):
    """Tool that takes a moment and then succeeds.

    Having a nonzero duration helps expose cancellation: if gather
    cancels pending futures when another task raises, this tool's
    result will be lost.
    """

    @property
    def name(self) -> str:
        return "delayed"

    @property
    def description(self) -> str:
        return "Slow success tool"

    @property
    def kind(self) -> ToolKind:
        return ToolKind.READ

    async def execute(self, **params) -> ToolResult:
        await asyncio.sleep(0.05)
        my_id = params.get("id", "unknown")
        return ToolResult(content=f"completed: {my_id}")


class _RaisingTool(Tool):
    """Tool that raises a BaseException during execution.

    Uses GeneratorExit (a BaseException, not Exception) so it passes
    through registry.execute's 'except Exception' handler and reaches
    asyncio.gather, triggering the cancellation bug.
    """

    @property
    def name(self) -> str:
        return "raise"

    @property
    def description(self) -> str:
        return "Raises on execute"

    @property
    def kind(self) -> ToolKind:
        return ToolKind.READ

    async def execute(self, **params) -> ToolResult:
        msg = params.get("msg", "unknown")
        raise RuntimeError(f"Tool raised: {msg}")


# ===========================================================================
# Tests for BUG-005
# ===========================================================================


class TestParallelToolCallFailureHandling:
    """Tests that parallel tool call failures don't cancel other calls."""

    def _make_executor(
        self,
        output_handler: _FakeOutputHandler | None = None,
        registry: ToolRegistry | None = None,
    ) -> ToolExecutor:
        output = output_handler or _FakeOutputHandler()
        if registry is None:
            registry = ToolRegistry()
            registry.register(_EchoTool())
        tool_manager = ToolManager(MagicMock())
        tool_manager.registry = registry
        provider = MagicMock()
        return ToolExecutor(
            output_handler=output,
            tool_manager=tool_manager,
            provider=provider,
            base_tool_iterations=25,
            max_tool_calls_per_turn=100,
        )

    @pytest.mark.asyncio
    async def test_parallel_failure_preserves_successful_result(self) -> None:
        """When one parallel tool raises, other tools must still complete.

        The asyncio.gather at line 269 calls *without* return_exceptions=True,
        so a single exception cancels all other pending coroutines. This test
        verifies that after the fix, the successful tool's result is preserved.
        """
        output = _FakeOutputHandler()

        registry = ToolRegistry()
        registry.register(_DelayedSuccessTool())
        registry.register(_RaisingTool())
        executor = self._make_executor(output_handler=output, registry=registry)
        agent = _FakeAgent(registry)

        # Mock registry.execute so the RuntimeError from _RaisingTool
        # propagates to asyncio.gather (bypassing registry's except Exception)
        original_execute = registry.execute

        async def mock_execute(name: str, params: dict) -> ToolResult:
            if name == "raise":
                # Raise a BaseException that is NOT caught by registry.execute's
                # "except Exception" handler, so it reaches asyncio.gather
                raise GeneratorExit("Tool execution failure")
            return await original_execute(name, params)

        registry.execute = mock_execute  # type: ignore[assignment]

        tool_calls = [
            ToolCall(id="tc-pass", name="delayed", arguments={"id": "pass_1"}),
            ToolCall(id="tc-fail", name="raise", arguments={"msg": "boom"}),
        ]

        # After the fix this should NOT raise
        await executor.execute_tool_calls(tool_calls, agent)

        # The successful tool must have its real result
        assert "tc-pass" in agent._tool_results, (
            "Successful tool result should be recorded"
        )
        result = agent._tool_results.get("tc-pass", "")
        assert "completed" in result, (
            f"Expected real result, got: {result}"
        )
        assert "interrupted" not in result.lower(), (
            "Successful tool should NOT get a cancellation message"
        )

        # The failed tool must have a response (from finally handler)
        assert "tc-fail" in agent._tool_results

    @pytest.mark.asyncio
    async def test_all_parallel_succeed_still_works(self) -> None:
        """When all parallel tools succeed, nothing changes."""
        output = _FakeOutputHandler()
        registry = ToolRegistry()
        registry.register(_DelayedSuccessTool())
        executor = self._make_executor(output_handler=output, registry=registry)
        agent = _FakeAgent(registry)

        tool_calls = [
            ToolCall(id="tc-1", name="delayed", arguments={"id": "first"}),
            ToolCall(id="tc-2", name="delayed", arguments={"id": "second"}),
        ]

        await executor.execute_tool_calls(tool_calls, agent)

        assert "tc-1" in agent._tool_results
        assert "tc-2" in agent._tool_results
        assert "interrupted" not in agent._tool_results.get("tc-1", "").lower()
        assert "interrupted" not in agent._tool_results.get("tc-2", "").lower()

    @pytest.mark.asyncio
    async def test_single_parallel_tool_still_works(self) -> None:
        """A single parallel tool (no gather needed) still works."""
        output = _FakeOutputHandler()
        registry = ToolRegistry()
        registry.register(_EchoTool())
        executor = self._make_executor(output_handler=output, registry=registry)
        agent = _FakeAgent(registry)

        tool_calls = [
            ToolCall(id="tc-1", name="echo", arguments={"msg": "hello"}),
        ]

        await executor.execute_tool_calls(tool_calls, agent)

        assert "tc-1" in agent._tool_results
