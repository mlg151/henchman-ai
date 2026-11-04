"""Actual tool execution contracts for recovery evaluation."""

import pytest
from evals.helpers import EvalTestRig, MockProvider
from evals.test_tool_failure_recovery import run_tool_failure_recovery_scenario

from henchman.core.agent_config import AgentConfig
from henchman.providers.base import ToolCall


async def test_tool_failure_recovery_scenario() -> None:
    check = (
        'from pathlib import Path; ns = {}; exec(Path("pricing.py").read_text(), ns); '
        'assert ns["total_price"](7, 3) == 21'
    )
    source = "def total_price(unit_price, quantity):\n    return unit_price * quantity\n"
    provider = MockProvider(
        responses=[
            [ToolCall(id="before", name="python_exec", arguments={"code": check, "background": False})],
            [ToolCall(id="repair", name="write_file", arguments={"path": "pricing.py", "content": source})],
            [ToolCall(id="after", name="python_exec", arguments={"code": check, "background": False})],
            "Repaired and verified.",
        ],
    )
    rig = EvalTestRig(provider=provider, profile="engineer", config=AgentConfig(max_tokens=20000))
    try:
        rig.setup("tool-failure-recovery")
        result = await run_tool_failure_recovery_scenario(rig)
        assert result.success
        checks = [log for log in result.tool_logs if log.tool_name == "python_exec"]
        assert [log.success for log in checks] == [False, True]
        assert rig.read_file("pricing.py") == source
    finally:
        rig.cleanup()

@pytest.mark.parametrize("mode", ["skipped-failure", "wrong-constant"])
async def test_tool_failure_recovery_scenario_rejects_invalid_delivery(mode: str) -> None:
    check = (
        'from pathlib import Path; ns = {}; exec(Path("pricing.py").read_text(), ns); '
        'assert ns["total_price"](7, 3) == 21'
    )
    expression = "unit_price * quantity" if mode == "skipped-failure" else "21"
    source = f"def total_price(unit_price, quantity):\n    return {expression}\n"
    responses: list[str | list[ToolCall]] = []
    if mode == "wrong-constant":
        responses.append([
            ToolCall(id="before", name="python_exec", arguments={"code": check, "background": False}),
        ])
    responses.extend([
        [ToolCall(id="repair", name="write_file", arguments={"path": "pricing.py", "content": source})],
        [ToolCall(id="after", name="python_exec", arguments={"code": check, "background": False})],
        "Repaired and verified.",
    ])
    rig = EvalTestRig(
        provider=MockProvider(responses), profile="engineer", config=AgentConfig(max_tokens=20000),
    )
    try:
        rig.setup("tool-failure-recovery-negative")
        message = "Missing failed python_exec" if mode == "skipped-failure" else "AssertionError"
        with pytest.raises(AssertionError, match=message):
            await run_tool_failure_recovery_scenario(rig)
        assert rig.read_file("pricing.py") == source
    finally:
        rig.cleanup()
