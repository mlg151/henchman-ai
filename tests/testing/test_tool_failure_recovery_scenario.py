"""Actual tool execution contracts for recovery evaluation."""

from collections.abc import AsyncGenerator
from typing import Any

import pytest
from evals.helpers import EvalTestRig, MockProvider, verify_python
from evals.models import EvalResult
from evals.test_tool_failure_recovery import run_tool_failure_recovery_scenario

from henchman.core.agent_config import AgentConfig
from henchman.providers.base import Message, StreamChunk, ToolCall, ToolDeclaration


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


class FailureAfterRecoveryProvider(MockProvider):
    async def chat_completion_stream(
        self,
        messages: list[Message],
        tools: list[ToolDeclaration] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[StreamChunk, None]:
        if len(self.calls) >= 3:
            raise RuntimeError("provider failed after recovery")
        async for chunk in super().chat_completion_stream(
            messages, tools, temperature, max_tokens, **kwargs,
        ):
            yield chunk


@pytest.mark.parametrize("fail", [False, True])
async def test_tool_failure_recovery_scenario_actual_caller_contract(
    monkeypatch: pytest.MonkeyPatch, fail: bool,
) -> None:
    check = (
        'from pathlib import Path; ns = {}; exec(Path("pricing.py").read_text(), ns); '
        'assert ns["total_price"](7, 3) == 21'
    )
    source = "def total_price(unit_price, quantity):\n    return unit_price * quantity\n"
    provider_type = FailureAfterRecoveryProvider if fail else MockProvider
    provider = provider_type([
        [ToolCall(id="before", name="python_exec", arguments={"code": check, "background": False})],
        [ToolCall(id="repair", name="write_file", arguments={"path": "pricing.py", "content": source})],
        [ToolCall(id="after", name="python_exec", arguments={"code": check, "background": False})],
        "Repaired and verified.",
    ])
    rig = EvalTestRig(provider=provider, profile="engineer", config=AgentConfig(max_tokens=20000))
    captured: list[EvalResult] = []
    original_run = rig.run

    async def wrapped_run(*args: Any, **kwargs: Any) -> EvalResult:
        result = await original_run(*args, **kwargs)
        captured.append(result)
        return result

    monkeypatch.setattr(rig, "run", wrapped_run)
    try:
        rig.setup("tool-failure-recovery-caller")
        if fail:
            with pytest.raises(AssertionError, match="provider failed after recovery"):
                await run_tool_failure_recovery_scenario(rig)
            assert len(captured) == 1
            assert not captured[0].success
            assert "provider failed after recovery" in (captured[0].error or "")
        else:
            returned = await run_tool_failure_recovery_scenario(rig)
            assert len(captured) == 1
            assert returned is captured[0]
            assert returned.success
        assert rig.read_file("pricing.py") == source
        assert [
            log.success for log in captured[0].tool_logs if log.tool_name == "python_exec"
        ] == [False, True]
        await verify_python(
            rig.test_dir,
            "from pricing import total_price; assert total_price(7, 3) == 21; assert total_price(2, 0) == 0",
        )
    finally:
        rig.cleanup()
