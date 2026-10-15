"""Offline execution contracts for the live Counter refactoring evaluation."""

from collections.abc import AsyncGenerator
from typing import Any

import pytest
from evals import helpers, test_coding_tasks
from evals.helpers import EvalResult, EvalTestRig, MockProvider

from henchman.providers.base import Message, StreamChunk, ToolDeclaration

_INSTANCE_COUNTER = """class Counter:
    def __init__(self):
        self.count = 0

    def increment(self):
        self.count += 1
        return self.count

    def decrement(self):
        self.count -= 1
        return self.count

    def get_count(self):
        return self.count

    def reset(self):
        self.count = 0
"""

_GLOBAL_COUNTER = """count = 0

class Counter:
    def __init__(self):
        self.reset()

    def increment(self):
        global count
        count += 1
        return count

    def decrement(self):
        global count
        count -= 1
        return count

    def get_count(self):
        return count

    def reset(self):
        global count
        count = 0
"""

_CLASS_COUNTER = """class Counter:
    count = 0

    def __init__(self):
        self.reset()

    def increment(self):
        Counter.count += 1
        return Counter.count

    def decrement(self):
        Counter.count -= 1
        return Counter.count

    def get_count(self):
        return Counter.count

    def reset(self):
        Counter.count = 0
"""


class ErrorAfterWriteProvider(MockProvider):
    async def chat_completion_stream(
        self,
        messages: list[Message],
        tools: list[ToolDeclaration] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[StreamChunk, None]:
        if self.calls:
            raise RuntimeError("Provider failed after writing counter")
        async for chunk in super().chat_completion_stream(
            messages, tools, temperature, max_tokens, **kwargs
        ):
            yield chunk


def _write_counter(source: str, *, fail_after_write: bool = False) -> MockProvider:
    provider = ErrorAfterWriteProvider() if fail_after_write else MockProvider()
    provider.set_tool_response(
        "write_file", {"path": "counter.py", "content": source}, "Refactored."
    )
    return provider


async def _run_scenario(provider: MockProvider) -> EvalResult:
    rig = EvalTestRig(provider=provider)
    try:
        rig.setup("offline-counter-contract")
        return await test_coding_tasks.run_counter_refactor_scenario(rig)
    finally:
        rig.cleanup()


async def test_counter_eval_accepts_independent_instances() -> None:
    provider = _write_counter(_INSTANCE_COUNTER)
    result = await _run_scenario(provider)
    assert result.success
    assert result.final_response == "Refactored."
    assert len(provider.calls) == 2
    assert result.tool_logs[0].tool_name == "write_file"
    assert result.tool_logs[0].success


async def test_counter_eval_decorated_entrypoint_uses_real_scenario(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _write_counter(_INSTANCE_COUNTER)
    monkeypatch.setattr(helpers, "get_eval_provider", lambda: provider)
    await test_coding_tasks.test_refactor_to_class()
    assert len(provider.calls) == 2


@pytest.mark.parametrize("source", [_GLOBAL_COUNTER, _CLASS_COUNTER], ids=["global", "class"])
async def test_counter_eval_rejects_shared_state(source: str) -> None:
    with pytest.raises(AssertionError, match="Constructing another counter"):
        await _run_scenario(_write_counter(source))


async def test_counter_eval_rejects_reset_cross_talk() -> None:
    source = (
        _INSTANCE_COUNTER.replace("class Counter:", "class Counter:\n    instances = []")
        .replace(
            "    def __init__(self):\n        self.count = 0",
            "    def __init__(self):\n        self.count = 0\n        self.instances.append(self)",
        )
        .replace(
            "    def reset(self):\n        self.count = 0",
            "    def reset(self):\n        for other in self.instances:\n            other.count = 0",
        )
    )
    with pytest.raises(AssertionError, match="Reset changed another counter"):
        await _run_scenario(_write_counter(source))


async def test_counter_eval_rejects_correct_file_after_provider_failure() -> None:
    provider = _write_counter(_INSTANCE_COUNTER, fail_after_write=True)
    with pytest.raises(AssertionError, match="Provider failed after writing counter"):
        await _run_scenario(provider)


async def test_counter_eval_rejects_unchanged_source() -> None:
    with pytest.raises(AssertionError, match="cannot import name 'Counter'"):
        await _run_scenario(MockProvider(["I refactored the counter."]))
