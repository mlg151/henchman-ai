"""Single-agent evidence reflects registry policy and final formatting results."""

import asyncio
from collections.abc import Iterator
from typing import Any

import pytest
from evals.helpers import EvalTestRig, LoggingToolWrapper, MockProvider
from evals.models import ToolLog

from henchman.core.agent_config import AgentConfig
from henchman.core.events import AgentEvent, EventType
from henchman.providers.base import ToolCall
from henchman.tools.base import ConfirmationRequest, Tool, ToolResult
from henchman.tools.builtins.lint_check import LintCheckTool
from henchman.tools.registry import ToolRegistry


@pytest.fixture
def make_rig() -> Iterator[Any]:
    rigs: list[EvalTestRig] = []

    def make(responses: list[Any], *, profile: str = "basic") -> EvalTestRig:
        rig = EvalTestRig(
            provider=MockProvider(responses),
            profile=profile,
            config=AgentConfig(max_tokens=20000),
        )
        rigs.append(rig)
        rig.setup("tool-observations")
        return rig

    yield make
    for rig in reversed(rigs):
        rig.cleanup()


@pytest.mark.parametrize("profile", ["basic", "engineer"])
@pytest.mark.parametrize("valid", [False, True], ids=["black-failure", "formatted"])
async def test_logs_contain_final_registry_result_and_event_coordinates(
    make_rig: Any,
    profile: str,
    valid: bool,
) -> None:
    content = "items= [1,2]\n" if valid else "def broken(:\n"
    rig = make_rig(
        [
            [ToolCall("write", "write_file", {"path": "source.py", "content": content})],
            "Finished the attempt.",
        ],
        profile=profile,
    )
    observed: list[AgentEvent] = []

    def observe(event: AgentEvent) -> None:
        assert rig._events[-1] is event
        assert len(rig._events) == len(observed) + 1
        if event.type == EventType.TOOL_CALL_RESULT:
            log = rig.get_tool_calls("write_file")[0]
            assert log.success is valid
            assert log.result_index == len(rig._events) - 1
        observed.append(event)

    result = await rig.run("Write source.py", observe_event=observe)
    assert result.events == observed
    assert len(result.tool_logs) == 1
    log = result.tool_logs[0]
    assert log.success is valid
    assert log.tool_call_id == "write"
    assert log.request_index is not None and log.result_index is not None
    assert log.request_index < log.result_index
    request = result.events[log.request_index]
    completed = result.events[log.result_index]
    assert request.type == EventType.TOOL_CALL_REQUEST
    assert completed.type == EventType.TOOL_CALL_RESULT
    assert log.source_agent == request.source_agent == completed.source_agent
    assert log.result == completed.data["result"]
    assert "Black" in log.result
    if valid:
        assert rig.read_file("source.py") == "items = [1, 2]\n"
        assert "Black formatted 1" in log.result
    else:
        assert "failed" in log.result.lower()


@pytest.mark.parametrize("plan_mode", [True, False], ids=["denied", "fixed"])
async def test_engineer_lint_fix_obeys_policy_and_observes_black(
    make_rig: Any,
    plan_mode: bool,
) -> None:
    rig = make_rig(
        [
            [ToolCall("lint", "lint_check", {"path": "source.py", "linter": "ruff", "fix": True})],
            "Finished the attempt.",
        ],
        profile="engineer",
    )
    original = "import os\nitems= [1,2]\n"
    rig.create_file("source.py", original)
    assert rig._agent is not None
    rig._agent.tool_registry.set_plan_mode(enabled=plan_mode)
    result = await rig.run("Fix source.py")
    assert len(result.tool_logs) == 1
    log = result.tool_logs[0]
    assert log.success is not plan_mode
    if plan_mode:
        assert "Plan Mode" in log.result
        assert rig.read_file("source.py") == original
    else:
        assert "Black formatted 1" in log.result
        assert rig.read_file("source.py") == "items = [1, 2]\n"


async def test_unexecuted_queued_calls_are_failed_and_next_run_is_isolated(make_rig: Any) -> None:
    rig = make_rig(
        [
            [ToolCall("same", "write_file", {"path": "never.txt", "content": "never"})],
            [ToolCall("same", "read_file", {"path": "source.txt"})],
            "Read.",
        ]
    )
    rig.create_file("source.txt", "current")
    first = await rig.run("Do not execute", max_iterations=0)
    assert not first.success
    assert not rig.file_exists("never.txt")
    assert len(first.tool_logs) == 1
    first_log = first.tool_logs[0]
    assert not first_log.success and first_log.result_index is not None
    second = await rig.run("Read source.txt")
    assert second.success
    assert len(second.tool_logs) == 1
    assert second.tool_logs[0].tool_name == "read_file"
    assert second.tool_logs[0].success
    assert first_log.tool_name == "write_file" and not first_log.success


class HeldTool(Tool):
    name = "held"
    description = "Wait until cancelled."

    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.closed = False

    async def execute(self, **kwargs: object) -> ToolResult:
        self.started.set()
        try:
            await asyncio.Event().wait()
            return ToolResult("unreachable")
        finally:
            self.closed = True


async def test_cancelled_execution_retains_unsuccessful_request_evidence(make_rig: Any) -> None:
    rig = make_rig([[ToolCall("held", "held", {})]])
    assert rig._agent is not None
    tool = HeldTool()
    rig._agent.tool_registry.register(tool)
    running = asyncio.create_task(rig.run("Wait", timeout=5))
    await asyncio.wait_for(tool.started.wait(), timeout=2)
    running.cancel()
    with pytest.raises(asyncio.CancelledError):
        await running
    assert tool.closed
    logs = rig.get_all_tool_calls()
    assert len(logs) == 1
    assert logs[0].tool_call_id == "held"
    assert not logs[0].success
    assert logs[0].request_index is not None


@pytest.mark.parametrize("plan_mode", [False, True], ids=["confirmation", "plan-mode"])
async def test_legacy_wrapper_preserves_invocation_authorization(
    tmp_path: Any,
    plan_mode: bool,
) -> None:
    source = tmp_path / "source.py"
    original = "import os\nitems= [1,2]\n"
    source.write_text(original)
    logs: list[ToolLog] = []
    registry = ToolRegistry()
    registry.register(LoggingToolWrapper(LintCheckTool(), logs))
    registry.set_plan_mode(enabled=plan_mode)
    requests: list[ConfirmationRequest] = []

    async def deny(request: ConfirmationRequest) -> bool:
        requests.append(request)
        return False

    registry.set_confirmation_handler(deny)
    result = await registry.execute(
        "lint_check",
        {"path": str(source), "fix": True, "linter": "ruff"},
    )
    assert not result.success
    assert source.read_text() == original
    assert not logs
    if not plan_mode:
        assert len(requests) == 1
        assert "Auto-fix lint issues" in requests[0].description
