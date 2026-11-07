"""Actual execution contracts for the interruption/recovery evaluation (case 12)."""

import asyncio
from collections.abc import AsyncGenerator
from typing import Any

import pytest
from evals.helpers import EvalTestRig, MockProvider
from evals.models import EvalResult
from evals.test_interruption_recovery import (
    BROKEN_SOURCE,
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
        result = await rig.run("Inspect the workspace.")
        with pytest.raises(AssertionError, match="Expected an interrupted turn"):
            rig.consume_expected_interruption()
        assert rig.last_run_outcome == (result.success, result.error)
        assert rig.interruption_evidence == []
        rig.assert_successful_runs()
    finally:
        rig.cleanup()


class FailOnceProvider(MockProvider):
    """Fail one scripted request while leaving a valid recovery response queued."""

    def __init__(
        self, responses: list[str | list[ToolCall]], fail_at: int, error: str,
    ) -> None:
        super().__init__(responses)
        self.fail_at = fail_at
        self.error = error
        self.requests = 0

    async def chat_completion_stream(
        self,
        messages: list[Message],
        tools: list[ToolDeclaration] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[StreamChunk, None]:
        request = self.requests
        self.requests += 1
        if request == self.fail_at:
            raise RuntimeError(self.error)
        async for chunk in super().chat_completion_stream(
            messages, tools, temperature, max_tokens, **kwargs,
        ):
            yield chunk


@pytest.mark.parametrize("fail_at", [0, 1])
@pytest.mark.parametrize(
    "error", ["provider authentication failed", "network connection lost", "Tool iteration limit (1) reached"],
)
@pytest.mark.asyncio
async def test_scenario_rejects_unrelated_failure_and_retains_failed_evidence(
    fail_at: int, error: str,
) -> None:
    """A recoverable provider failure is not the deliberate tool-limit stop."""
    responses: list[str | list[ToolCall]] = []
    if fail_at:
        responses.append(
            [ToolCall(id="first-read", name="read_file", arguments={"path": "orders.py"})],
        )
    responses.extend([
        [ToolCall(id="recovery-write", name="write_file", arguments={
            "path": "orders.py", "content": REPAIRED_SOURCE,
        })],
        "Recovered successfully.",
    ])
    provider = FailOnceProvider(responses, fail_at, error)
    rig = EvalTestRig(provider, profile="engineer", config=AgentConfig(max_tokens=20000))
    try:
        rig.setup("interruption-unrelated-failure")
        with pytest.raises(AssertionError, match="Expected an interrupted turn"):
            await run_interruption_recovery_scenario(rig)
        assert provider.requests == fail_at + 1
        assert rig.read_file("orders.py") == BROKEN_SOURCE
        assert rig.interruption_evidence == []
        outcome = rig.last_run_outcome
        assert outcome is not None and not outcome[0] and error in (outcome[1] or "")
        # Catching the rejection and subsequently succeeding cannot hide failure.
        assert (await rig.run("Recover the implementation.")).success
        with pytest.raises(AssertionError, match="Turn 1"):
            rig.assert_successful_runs()
    finally:
        rig.cleanup()


@pytest.mark.asyncio
async def test_scenario_requires_work_before_bounded_interruption(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An environment cap of zero cannot stand in for interrupted workspace work."""
    monkeypatch.setenv("EVAL_MAX_ITERATIONS", "0")
    rig = EvalTestRig(
        _provider(_happy_path_responses()), profile="engineer", config=AgentConfig(max_tokens=20000),
    )
    try:
        rig.setup("interruption-without-work")
        with pytest.raises(AssertionError, match="completed tool round"):
            await run_interruption_recovery_scenario(rig)
        assert rig.interruption_evidence == []
        assert rig.last_run_outcome is not None and not rig.last_run_outcome[0]
    finally:
        rig.cleanup()


class HeldProvider(MockProvider):
    """Keep a scripted request open until timeout or external task cancellation."""

    def __init__(self) -> None:
        super().__init__()
        self.entered = asyncio.Event()

    async def chat_completion_stream(
        self,
        messages: list[Message],
        tools: list[ToolDeclaration] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[StreamChunk, None]:
        self.entered.set()
        await asyncio.Event().wait()
        yield StreamChunk(content="Unreachable")


@pytest.mark.parametrize("external_cancel", [False, True])
@pytest.mark.asyncio
async def test_timeout_or_external_cancellation_is_not_a_bounded_tool_stop(
    external_cancel: bool,
) -> None:
    """An aborted request without observed tool-limit cancellation stays failed."""
    provider = HeldProvider()
    rig = EvalTestRig(provider)
    try:
        rig.setup("interruption-unobserved-cancellation")
        if external_cancel:
            task = asyncio.create_task(rig.run("Wait for a response."))
            await asyncio.wait_for(provider.entered.wait(), timeout=5)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        else:
            result = await rig.run("Wait for a response.", timeout=0.01)
            assert not result.success and "timed out" in (result.error or "")
        before = rig.last_run_outcome
        with pytest.raises(AssertionError, match="Expected an interrupted turn"):
            rig.consume_expected_interruption()
        assert rig.last_run_outcome == before
        assert rig.interruption_evidence == []
        with pytest.raises(AssertionError, match="Turn 1"):
            rig.assert_successful_runs()
    finally:
        rig.cleanup()


@pytest.mark.asyncio
async def test_interruption_classification_is_captured_and_reset_with_setup() -> None:
    """Mutable result copies and a reused rig cannot alter accepted evidence."""
    rig = EvalTestRig(_provider(_happy_path_responses()), profile="basic")
    try:
        rig.setup("interruption-snapshot")
        rig.create_file("orders.py", BROKEN_SOURCE)
        result = await rig.run("Inspect the module.", max_iterations=1)
        original = (result.success, result.error)
        result.events.clear()
        result.tool_logs.clear()
        result.success, result.error = True, None
        assert rig.consume_expected_interruption() == original
        assert rig.interruption_evidence == [original]
        rig.cleanup()

        rig.setup("interruption-new-workspace")
        assert rig.last_run_outcome is None
        assert rig.interruption_evidence == []
        with pytest.raises(AssertionError, match="did not run an agent turn"):
            rig.consume_expected_interruption()
    finally:
        rig.cleanup()
