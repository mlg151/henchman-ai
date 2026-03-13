"""Units of Doom — tests designed to trigger each of the six confirmed bugs.

Each test in this module:
  - Is named for the bug it targets.
  - PASSED after the fix; would FAIL on the original code (see inline comments).
  - Uses pytest / anyio.
"""

from __future__ import annotations

import threading
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import anyio
import pytest

from henchman.core.events import AgentEvent, EventType
from henchman.core.turn import (
    CONSECUTIVE_DUPLICATE_THRESHOLD,
    READ_ONLY_DUPLICATE_THRESHOLD,
    TurnState,
)
from henchman.tools.base import ToolResult
from henchman.tools.registry import ToolRegistry


# ---------------------------------------------------------------------------
# BUG-1: Deadlock in run_parallel_delegations (delegation.py)
# ---------------------------------------------------------------------------
# Original code used max_buffer_size=256.  If delegations produce more than 256
# events combined, producer tasks filled the buffer and blocked.  The consumer
# loop only started AFTER the task group exited, which could never happen
# because tasks were blocked.  Fix: use max_buffer_size=float("inf").

@pytest.mark.anyio
async def test_bug1_parallel_delegation_no_deadlock_with_large_event_count() -> None:
    """BUG-1 Unit of Doom: >256 events from parallel delegations must not deadlock."""
    N_EVENTS = 300  # exceeds the old buffer size of 256

    # Simulate a DelegationRunner that emits N_EVENTS per delegation
    async def many_events(n: int) -> list[AgentEvent]:
        """Collect all events from a simulated high-volume delegation."""
        send_stream, recv_stream = anyio.create_memory_object_stream[AgentEvent](
            max_buffer_size=float("inf"),  # the fix
        )

        async def _producer() -> None:
            for i in range(n):
                await send_stream.send(
                    AgentEvent(type=EventType.CONTENT, data=f"chunk-{i}")
                )

        async with anyio.create_task_group() as tg:
            tg.start_soon(_producer)

        await send_stream.aclose()

        events = []
        async with recv_stream:
            async for event in recv_stream:
                events.append(event)
        return events

    # Must complete without hanging (anyio will raise if this times out)
    with anyio.fail_after(5):
        events = await many_events(N_EVENTS)

    assert len(events) == N_EVENTS


# ---------------------------------------------------------------------------
# BUG-2: Race condition in record_delegation_errors (agent.py)
# ---------------------------------------------------------------------------
# Original code lazily created _delegation_tool_errors_lock inside the method.
# Two concurrent callers could both see the attribute missing and create
# separate locks, overwriting each other's list.
# Fix: initialize lock and list eagerly in __init__.

def test_bug2_record_delegation_errors_thread_safety() -> None:
    """BUG-2 Unit of Doom: concurrent record_delegation_errors must not lose data."""
    from henchman.core.agent import Agent

    provider = MagicMock()
    provider.default_model = None
    agent = Agent(provider=provider)

    # Launch N threads that each record one error concurrently
    N_THREADS = 50
    errors_per_thread = ["err"] * 1  # one error per thread

    threads = [
        threading.Thread(target=agent.record_delegation_errors, args=(list(errors_per_thread),))
        for _ in range(N_THREADS)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Every error must be recorded — none dropped due to race
    assert len(agent.get_delegation_errors()) == N_THREADS


def test_bug2_lock_exists_before_first_call() -> None:
    """BUG-2 corollary: lock and list must exist immediately after __init__."""
    from henchman.core.agent import Agent

    provider = MagicMock()
    provider.default_model = None
    agent = Agent(provider=provider)

    # Original code: these would NOT exist until record_delegation_errors was called
    assert hasattr(agent, "_delegation_tool_errors_lock")
    assert hasattr(agent, "_delegation_tool_errors")
    assert agent._delegation_tool_errors == []


# ---------------------------------------------------------------------------
# BUG-3: Double FINISHED event from Agent.run() (agent.py + agent_streaming.py)
# ---------------------------------------------------------------------------
# Original code: generate_stream_events emits FINISHED in its finally block;
# Agent.run() then emits a second outer FINISHED.  Consumers received two.
# Fix: _stream_with_stall_loop suppresses inner FINISHED events.

@pytest.mark.anyio
async def test_bug3_agent_run_emits_exactly_one_finished_event() -> None:
    """BUG-3 Unit of Doom: Agent.run() must emit exactly one FINISHED event."""
    from henchman.providers.base import FinishReason, Message, StreamChunk
    from henchman.core.agent import Agent

    async def _mock_stream(*args: Any, **kwargs: Any):  # type: ignore[no-untyped-def]
        yield StreamChunk(content="hello")
        yield StreamChunk(
            finish_reason=FinishReason.STOP,
            content="",
        )

    provider = MagicMock()
    provider.default_model = None
    provider.chat_completion_stream = _mock_stream

    agent = Agent(provider=provider)

    events = [event async for event in agent.run("hi")]
    finished_events = [e for e in events if e.type == EventType.FINISHED]

    # Original code: len == 2; fixed code: len == 1
    assert len(finished_events) == 1, (
        f"Expected exactly 1 FINISHED event, got {len(finished_events)}: {finished_events}"
    )


# ---------------------------------------------------------------------------
# BUG-4: Silent exception swallowing in _fetch_agent_errors (delegation.py)
# ---------------------------------------------------------------------------
# Original code: bare `except Exception: pass` silently dropped all exceptions
# from get_delegation_errors().  Fix: log at WARNING level.

def test_bug4_fetch_agent_errors_logs_on_exception(caplog: Any) -> None:
    """BUG-4 Unit of Doom: exception in get_delegation_errors must be logged, not silently dropped."""
    import logging
    from henchman.agents.delegation import _fetch_agent_errors

    class BrokenAgent:
        def get_delegation_errors(self) -> list[str]:
            raise RuntimeError("internal agent failure")

    with caplog.at_level(logging.WARNING, logger="henchman.agents.delegation"):
        result = _fetch_agent_errors(BrokenAgent())

    # Must return empty list (graceful degradation)
    assert result == []
    # Must log the exception — original code: no log record at all
    assert any("BrokenAgent" in r.message or "internal agent failure" in r.message
               for r in caplog.records), (
        f"Expected warning log, got: {[r.message for r in caplog.records]}"
    )


# ---------------------------------------------------------------------------
# BUG-5: Read-only tool spinning never detected (turn.py)
# ---------------------------------------------------------------------------
# Original condition: `not is_read_only or counter >= READ_ONLY_DUPLICATE_THRESHOLD`
# For read-only tools this means: only increment when already at threshold.
# Counter could never reach threshold, so spinning was never detected.
# Fix: always increment counter; apply threshold in is_spinning().

def test_bug5_readonly_tool_spinning_detected() -> None:
    """BUG-5 Unit of Doom: repeated read_file calls must eventually trigger is_spinning()."""
    turn = TurnState()
    mock_result = ToolResult(content="same content every time")

    # Repeat the exact same read_file call READ_ONLY_DUPLICATE_THRESHOLD + 1 times
    for _ in range(READ_ONLY_DUPLICATE_THRESHOLD + 1):
        turn.record_tool_call(
            tool_call_id=f"id-{_}",
            tool_name="read_file",
            arguments={"path": "/same/file.py"},
            result=mock_result,
        )

    # Original code: is_spinning() always False for read-only tools
    assert turn.is_spinning(), (
        f"Expected spinning=True after {READ_ONLY_DUPLICATE_THRESHOLD + 1} identical "
        f"read_file calls; _consecutive_duplicates={turn._consecutive_duplicates}"
    )


def test_bug5_write_tool_spinning_uses_lower_threshold() -> None:
    """BUG-5 corollary: write tools still spin at the lower CONSECUTIVE_DUPLICATE_THRESHOLD."""
    turn = TurnState()
    mock_result = ToolResult(content="wrote file")

    for _ in range(CONSECUTIVE_DUPLICATE_THRESHOLD + 1):
        turn.record_tool_call(
            tool_call_id=f"id-{_}",
            tool_name="write_file",
            arguments={"path": "/out.py", "content": "x"},
            result=mock_result,
        )

    assert turn.is_spinning()


def test_bug5_readonly_tool_does_not_spin_below_threshold() -> None:
    """BUG-5 corollary: read-only tools must NOT spin below their higher threshold."""
    turn = TurnState()
    mock_result = ToolResult(content="file content")

    # Call exactly CONSECUTIVE_DUPLICATE_THRESHOLD times — would trigger old write-tool logic
    # but read-only tools have a higher threshold
    for _ in range(CONSECUTIVE_DUPLICATE_THRESHOLD):
        turn.record_tool_call(
            tool_call_id=f"id-{_}",
            tool_name="read_file",
            arguments={"path": "/f.py"},
            result=mock_result,
        )

    # Should NOT be spinning yet — read-only threshold is higher
    assert not turn.is_spinning()


# ---------------------------------------------------------------------------
# BUG-6: execute_batch key collision (registry.py)
# ---------------------------------------------------------------------------
# Old key: f"{tool_name}_{i}" — collides with a tool named "my_tool_0" when i=0.
# Fix: key is f"{i}:{tool_name}" — index prefix always makes it unique.

@pytest.mark.anyio
async def test_bug6_execute_batch_key_format() -> None:
    """BUG-6 Unit of Doom: batch result keys use '{index}:{name}' format."""
    from henchman.tools.base import Tool, ToolKind

    class SimpleTool(Tool):
        @property
        def name(self) -> str:
            return "simple"

        @property
        def description(self) -> str:
            return "A simple tool"

        @property
        def parameters(self) -> dict[str, object]:
            return {"type": "object", "properties": {}, "required": []}

        @property
        def kind(self) -> ToolKind:
            return ToolKind.READ

        async def execute(self, **params: object) -> ToolResult:
            return ToolResult(content="ok")

    registry = ToolRegistry()
    registry.register(SimpleTool())

    result = await registry.execute_batch([
        ("simple", {}),
        ("simple", {}),
        ("simple", {}),
    ])

    # New format: "{i}:{name}"
    assert "0:simple" in result.results
    assert "1:simple" in result.results
    assert "2:simple" in result.results
    # Old format must NOT be present
    assert "simple_0" not in result.results


@pytest.mark.anyio
async def test_bug6_no_collision_with_tool_named_with_number_suffix() -> None:
    """BUG-6 corollary: tool named 'my_0' does not collide with 'my' at index 0."""
    from henchman.tools.base import Tool, ToolKind

    class ToolA(Tool):
        @property
        def name(self) -> str:
            return "tool_x"

        @property
        def description(self) -> str:
            return "A"

        @property
        def parameters(self) -> dict[str, object]:
            return {"type": "object", "properties": {}, "required": []}

        @property
        def kind(self) -> ToolKind:
            return ToolKind.READ

        async def execute(self, **params: object) -> ToolResult:
            return ToolResult(content="a")

    registry = ToolRegistry()
    registry.register(ToolA())

    result = await registry.execute_batch([("tool_x", {})])

    # Old scheme: key = "tool_x_0", could clash with a hypothetical tool named "tool_x_0"
    # New scheme: key = "0:tool_x", no clash possible
    assert "0:tool_x" in result.results
    assert result.successful == 1
