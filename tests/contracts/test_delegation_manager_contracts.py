"""Contract tests for the delegation manager task surface."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

from henchman.agents.delegation_manager import DelegationTask
from tests.contracts.helpers import assert_contract_matches


def _task_contract_payload(task: DelegationTask) -> dict[str, object]:
    """Project a DelegationTask to its stable public state."""
    return {
        "id": task.id,
        "target_role": task.target_role,
        "task": task.task,
        "tool_call_id": task.tool_call_id,
        "depth": task.depth,
        "completed": task.completed,
        "error": task.error,
        "output_buffer": list(task.output_buffer),
        "start_time": task.start_time,
    }


def test_delegation_task_state_matches_contract(contract_suite: object) -> None:
    """DelegationTask public state should satisfy its contract."""
    loop = asyncio.new_event_loop()
    try:
        task_future: asyncio.Future[tuple[str, bool]] = loop.create_future()
        task = DelegationTask(
            id="delegation_1",
            target_role="coder",
            task="Write parser tests",
            tool_call_id="tool_123",
            source_agent=MagicMock(),
            depth=2,
            task_future=task_future,
        )
        task.output_buffer.append("stream chunk")

        assert_contract_matches(
            contract_suite=contract_suite,  # type: ignore[arg-type]
            payload=_task_contract_payload(task),
            schema_name="runtime/delegation_task_state",
        )
    finally:
        loop.close()
