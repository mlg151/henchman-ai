"""Actual execution contracts for the interruption/recovery evaluation (case 12)."""

from collections.abc import AsyncGenerator
from typing import Any

import pytest
from evals.helpers import EvalTestRig, MockProvider
from evals.models import EvalResult
from evals.test_interruption_recovery import (
    REPAIRED_SOURCE,
    TEST_SOURCE,
    run_interruption_recovery_scenario,
)

from henchman.core.agent_config import AgentConfig
from henchman.providers.base import Message, StreamChunk, ToolCall, ToolDeclaration


def _provider(responses: list[str | list[ToolCall]]) -> MockProvider:
    return MockProvider(responses)


def _happy_path_responses() -> list[str | list[ToolCall]]:
    # Turn 1 (one tool round): inspect the workspace, then the bounded loop
    # interrupts before the second response's tool call can execute; that call
    # is cancelled and never runs.
    turn_one: list[str | list[ToolCall]] = [
        [ToolCall(id="t1-read", name="read_file", arguments={"path": "orders.py"})],
        [
            ToolCall(
                id="t1-ghost",
                name="write_file",
                arguments={"path": "orders.py", "content": REPAIRED_SOURCE},
            )
        ],
    ]
    # Turn 2 (recovery): resume from the persisted workspace and deliver the fix.
    turn_two: list[str | list[ToolCall]] = [
        [
            ToolCall(
                id="t2-write",
                name="write_file",
                arguments={"path": "orders.py", "content": REPAIRED_SOURCE},
            )
        ],
        "Resumed and fixed the module.",
    ]
    return [*turn_one, *turn_two]


@pytest.mark.asyncio
async def test_interruption_recovery_scenario() -> None:
    rig = EvalTestRig(
        _provider(_happy_path_responses()),
        profile="engineer",
        config=AgentConfig(max_tokens=20000),
    )
    try:
        rig.setup("interruption-recovery")
        result = await run_interruption_recovery_scenario(rig)
        assert result.success
        assert rig.read_file("orders.py") == REPAIRED_SOURCE
        assert rig.read_file("test_orders.py") == TEST_SOURCE
    finally:
        rig.cleanup()


@pytest.mark.asyncio
async def test_interruption_recovery_scenario_requires_observed_interruption() -> None:
    """A first attempt that completes normally is not an interruption: reject it."""
    # The scripted first turn makes no tool calls, so it ends with a normal
    # stop instead of the bounded interruption the scenario requires.
    responses: list[str | list[ToolCall]] = [
        "I will start by inspecting the workspace.",
        [
            ToolCall(
                id="t2-write",
                name="write_file",
                arguments={"path": "orders.py", "content": REPAIRED_SOURCE},
            )
        ],
        "Resumed and fixed the module.",
    ]
    rig = EvalTestRig(
        _provider(responses), profile="engineer", config=AgentConfig(max_tokens=20000)
    )
    try:
        rig.setup("interruption-recovery-no-interruption")
        with pytest.raises(AssertionError, match="Expected an interrupted turn"):
            await run_interruption_recovery_scenario(rig)
    finally:
        rig.cleanup()


@pytest.mark.asyncio
async def test_interruption_recovery_scenario_rejects_wrong_recovery() -> None:
    """Interruption plus a recovery that leaves the oracle failing must fail."""
    wrong = '"""Order pricing helpers."""\n\n\ndef order_total(prices):\n    return 0\n'
    responses: list[str | list[ToolCall]] = [
        [ToolCall(id="t1-read", name="read_file", arguments={"path": "orders.py"})],
        [
            ToolCall(
                id="t1-ghost",
                name="write_file",
                arguments={"path": "orders.py", "content": wrong},
            )
        ],
        [
            ToolCall(
                id="t2-write",
                name="write_file",
                arguments={"path": "orders.py", "content": wrong},
            )
        ],
        "Resumed and fixed the module.",
    ]
    rig = EvalTestRig(
        _provider(responses), profile="engineer", config=AgentConfig(max_tokens=20000)
    )
    try:
        rig.setup("interruption-recovery-wrong")
        with pytest.raises(AssertionError):
            await run_interruption_recovery_scenario(rig)
        assert rig.read_file("orders.py") == wrong
    finally:
        rig.cleanup()


@pytest.mark.asyncio
async def test_interruption_recovery_scenario_rejects_tampered_provided_tests() -> None:
    """The provided test file must not be rewritten to pass."""
    responses: list[str | list[ToolCall]] = [
        [ToolCall(id="t1-read", name="read_file", arguments={"path": "orders.py"})],
        [
            ToolCall(
                id="t1-ghost",
                name="write_file",
                arguments={"path": "orders.py", "content": REPAIRED_SOURCE},
            )
        ],
        [
            ToolCall(
                id="t2-tamper",
                name="write_file",
                arguments={"path": "test_orders.py", "content": "def test_noop():\n    assert True\n"},
            )
        ],
        [
            ToolCall(
                id="t2-write",
                name="write_file",
                arguments={"path": "orders.py", "content": REPAIRED_SOURCE},
            )
        ],
        "Resumed and fixed the module.",
    ]
    rig = EvalTestRig(
        _provider(responses), profile="engineer", config=AgentConfig(max_tokens=20000)
    )
    try:
        rig.setup("interruption-recovery-tamper")
        with pytest.raises(AssertionError, match="provided tests"):
            await run_interruption_recovery_scenario(rig)
    finally:
        rig.cleanup()


class ProviderFailureAfterInterruption(MockProvider):
    """Fail the provider during the recovery turn, after the interruption happened."""

    def __init__(self, responses: list[str | list[ToolCall]], fail_at_call: int) -> None:
        super().__init__(responses)
        self._fail_at_call = fail_at_call

    async def chat_completion_stream(
        self,
        messages: list[Message],
        tools: list[ToolDeclaration] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[StreamChunk, None]:
        if len(self.calls) >= self._fail_at_call:
            raise RuntimeError("provider failed during recovery")
        async for chunk in super().chat_completion_stream(
            messages, tools, temperature, max_tokens, **kwargs
        ):
            yield chunk


@pytest.mark.asyncio
async def test_interruption_recovery_scenario_surfaces_provider_failure_in_recovery() -> None:
    """A real provider failure in the recovery turn must surface, not pass."""
    provider = ProviderFailureAfterInterruption(_happy_path_responses(), fail_at_call=3)
    rig = EvalTestRig(
        provider, profile="engineer", config=AgentConfig(max_tokens=20000)
    )
    captured: list[EvalResult] = []
    original_run = rig.run

    async def wrapped_run(*args: Any, **kwargs: Any) -> EvalResult:
        result = await original_run(*args, **kwargs)
        captured.append(result)
        return result

    try:
        rig.setup("interruption-recovery-provider-failure")
        rig.run = wrapped_run  # type: ignore[method-assign]
        with pytest.raises(AssertionError, match="provider failed during recovery"):
            await run_interruption_recovery_scenario(rig)
        assert len(captured) == 2
        assert not captured[1].success
        assert "provider failed during recovery" in (captured[1].error or "")
    finally:
        rig.cleanup()


@pytest.mark.asyncio
async def test_consume_expected_interruption_tracks_rig_state() -> None:
    """Consume rejects a missing turn, records evidence, and loosens the gate."""
    provider = MockProvider(
        [
            [ToolCall(id="t1-read", name="read_file", arguments={"path": "orders.py"})],
            [
                ToolCall(
                    id="t1-ghost",
                    name="write_file",
                    arguments={"path": "orders.py", "content": "x"},
                )
            ],
            "Done.",
        ]
    )
    rig = EvalTestRig(provider=provider, profile="basic")
    try:
        with pytest.raises(AssertionError, match="did not run an agent turn"):
            rig.consume_expected_interruption()
        rig.setup("interruption-consume")
        rig.create_file("orders.py", "x\n")
        first = await rig.run("Inspect orders.py.", max_iterations=1)
        assert not first.success
        consumed = rig.consume_expected_interruption()
        assert consumed == (first.success, first.error)
        assert rig.interruption_evidence == [consumed]
        # The strict success gate now only sees turns the scenario did not consume.
        await rig.run("Finish the job.", max_iterations=1)
        rig.assert_successful_runs()
    finally:
        rig.cleanup()


@pytest.mark.asyncio
async def test_consume_expected_interruption_rejects_successful_turn() -> None:
    provider = MockProvider(["All done, nothing to do."])
    rig = EvalTestRig(provider=provider, profile="basic")
    try:
        rig.setup("interruption-consume-success")
        await rig.run("Inspect the workspace.")
        with pytest.raises(AssertionError, match="Expected an interrupted turn"):
            rig.consume_expected_interruption()
    finally:
        rig.cleanup()
