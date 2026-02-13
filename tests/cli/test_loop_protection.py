"""Tests for loop protection in REPL."""

from typing import Any
from unittest.mock import Mock

import pytest
from rich.console import Console

from henchman.cli.repl import Repl, ReplConfig
from henchman.core.turn import TurnState
from henchman.providers.base import FinishReason, Message, ModelProvider, StreamChunk, ToolCall


class MockToolCallProvider(ModelProvider):
    """Mock provider that returns tool calls for testing loop protection."""

    def __init__(self, num_tool_calls: int = 1):
        self.num_tool_calls = num_tool_calls
        self.call_count = 0

    @property
    def name(self) -> str:
        return "mock_tool_call"

    async def chat_completion_stream(
        self, messages: list[Message], tools: list[Any] | None = None, **kwargs: Any
    ):
        self.call_count += 1
        if self.call_count <= self.num_tool_calls:
            yield StreamChunk(
                content=None,
                tool_calls=[
                    ToolCall(
                        id=f"tc_{self.call_count}",
                        name="read_file",
                        arguments={"path": "/same/file.txt"},
                    )
                ],
                finish_reason=FinishReason.TOOL_CALLS,
            )
        else:
            yield StreamChunk(content="Done!", finish_reason=FinishReason.STOP)


class TestLoopProtectionConfig:
    """Tests for loop protection configuration."""

    def test_default_iteration_limits(self) -> None:
        """ReplConfig should have sensible iteration defaults."""
        config = ReplConfig()
        assert config.base_tool_iterations == 25
        assert config.max_tool_calls_per_turn == 100

    def test_custom_iteration_limits(self) -> None:
        """ReplConfig should accept custom iteration limits."""
        config = ReplConfig(base_tool_iterations=10, max_tool_calls_per_turn=50)
        assert config.base_tool_iterations == 10
        assert config.max_tool_calls_per_turn == 50


class TestTurnTrackingInRepl:
    """Tests for turn tracking integration in REPL."""

    def test_repl_has_turn_state(self) -> None:
        """Repl's agent should have TurnState."""
        console = Console(file=None, force_terminal=True)
        provider = Mock(spec=ModelProvider)
        provider.name = "mock"

        repl = Repl(provider=provider, console=console)

        assert hasattr(repl.agent, "turn")
        assert isinstance(repl.agent.turn, TurnState)

    def test_turn_resets_on_new_input(self) -> None:
        """Turn state should reset when processing new user input."""
        console = Console(file=None, force_terminal=True)
        provider = Mock(spec=ModelProvider)
        provider.name = "mock"

        repl = Repl(provider=provider, console=console)

        # Simulate some turn activity
        repl.agent.turn.tool_count = 5
        repl.agent.turn.iteration = 3

        # A new turn should reset these
        repl.agent.turn.reset(new_start_index=10)

        assert repl.agent.turn.tool_count == 0
        assert repl.agent.turn.iteration == 0
        assert repl.agent.turn.start_index == 10


class TestIterationLimitEnforcement:
    """Tests for iteration limit enforcement."""

    @pytest.mark.asyncio
    async def test_at_limit_detection(self) -> None:
        """Turn should correctly detect when at iteration limit."""
        state = TurnState()
        base_limit = 25

        # Not at limit initially
        assert not state.is_at_limit(base_limit)

        # Set iteration to limit
        state.iteration = 25
        assert state.is_at_limit(base_limit)

    @pytest.mark.asyncio
    async def test_approaching_limit_detection(self) -> None:
        """Turn should correctly detect when approaching limit."""
        state = TurnState()
        base_limit = 25

        # Not approaching initially
        assert not state.is_approaching_limit(base_limit)

        # At 75% threshold
        state.iteration = 19  # 19/25 = 76%
        assert state.is_approaching_limit(base_limit)


class TestSpinningDetection:
    """Tests for spinning (loop) detection."""

    def test_consecutive_duplicate_detection(self) -> None:
        """Should detect consecutive duplicate tool calls."""
        state = TurnState()

        # Use a write tool to ensure consecutive duplicates are counted
        for i in range(4):  # Needs to be 4 to reach _consecutive_duplicates >= 3
            state.record_tool_call(f"tc_{i}", "write_file", {"path": "/same.txt"})

        assert state.is_spinning()

    def test_no_spinning_with_varied_calls(self) -> None:
        """Should not detect spinning with varied tool calls."""
        state = TurnState()

        # Different tool calls
        state.record_tool_call("tc_1", "read_file", {"path": "/a.txt"})
        state.record_tool_call("tc_2", "write_file", {"path": "/b.txt"})
        state.record_tool_call("tc_3", "shell", {"command": "ls"})

        assert not state.is_spinning()


class TestAdaptiveLimits:
    """Tests for adaptive limit adjustments."""

    def test_progress_increases_limit(self) -> None:
        """Making progress should increase the iteration limit."""
        state = TurnState()
        base = 25

        # Add file modification (progress indicator)
        state.files_modified.add("/src/main.py")

        assert state.get_adaptive_limit(base) > base

    def test_spinning_decreases_limit(self) -> None:
        """Spinning should decrease the iteration limit."""
        state = TurnState()
        base = 25

        # Simulate spinning
        state._consecutive_duplicates = 3

        assert state.get_adaptive_limit(base) < base

    def test_minimum_limit(self) -> None:
        """Adaptive limit should never go below minimum."""
        state = TurnState()

        # Set extreme spinning
        state._consecutive_duplicates = 100

        # Should still have minimum of 5
        assert state.get_adaptive_limit(base_limit=25) >= 5


class TestUnlimitedMode:
    """Tests for /unlimited bypass mode."""

    def test_unlimited_mode_default_off(self) -> None:
        """Unlimited mode should be off by default."""
        console = Console(file=None, force_terminal=True)
        provider = Mock(spec=ModelProvider)
        provider.name = "mock"

        repl = Repl(provider=provider, console=console)

        assert repl.agent.unlimited_mode is False

    def test_unlimited_mode_toggle(self) -> None:
        """Unlimited mode should be toggleable."""
        console = Console(file=None, force_terminal=True)
        provider = Mock(spec=ModelProvider)
        provider.name = "mock"

        repl = Repl(provider=provider, console=console)

        repl.agent.unlimited_mode = True
        assert repl.agent.unlimited_mode is True

        repl.agent.unlimited_mode = False
        assert repl.agent.unlimited_mode is False
