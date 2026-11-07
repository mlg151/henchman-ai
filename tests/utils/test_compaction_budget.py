"""Summary fallbacks cannot swallow exhausted run budgets or strand streams."""

import asyncio
from types import SimpleNamespace

import pytest

from henchman.core.run_budget import BudgetAccountingError, BudgetControlError, BudgetExceeded
from henchman.providers.base import FinishReason, Message, StreamChunk
from henchman.utils.compaction import (
    CompactionResult,
    _attempt_summarization,
    _generate_summary_with_provider,
)


async def test_summary_exhaustion_propagates_through_all_fallback_layers() -> None:
    async def stream(**_kwargs):
        raise BudgetExceeded("request_limit")
        yield

    provider = SimpleNamespace(chat_completion_stream=stream)
    message = Message("user", "Earlier work")
    with pytest.raises(BudgetExceeded, match="request_limit"):
        await _attempt_summarization(CompactionResult(messages=[]), [message], provider)


async def test_summary_drains_and_closes_after_finish() -> None:
    observed = []

    async def stream(**_kwargs):
        try:
            yield StreamChunk(content="Summary", finish_reason=FinishReason.STOP)
            observed.append("trailing usage")
            yield StreamChunk(usage={"prompt_tokens": 5, "completion_tokens": 1})
        finally:
            observed.append("closed")

    summary = await _generate_summary_with_provider(
        SimpleNamespace(chat_completion_stream=stream), [Message("user", "Earlier work")], lambda _: "formatted",
    )
    assert summary == "Summary"
    assert observed == ["trailing usage", "closed"]


@pytest.mark.parametrize("primary_kind", ["ordinary", "accounting", "cancellation"])
async def test_summary_cleanup_accounting_error_cannot_become_an_ordinary_fallback(primary_kind):
    primary = {
        "ordinary": ValueError("invalid summary response"),
        "accounting": BudgetExceeded("token_limit"),
        "cancellation": asyncio.CancelledError(),
    }[primary_kind]
    cleanup = BudgetAccountingError("durable_cleanup_failed")
    expected = cleanup if primary_kind == "ordinary" else primary
    closed = []

    class Stream:
        def __aiter__(self):
            return self

        async def __anext__(self):
            raise primary

        async def aclose(self):
            closed.append(True)
            raise cleanup

    provider = SimpleNamespace(chat_completion_stream=lambda **_kwargs: Stream())
    with pytest.raises((BudgetControlError, asyncio.CancelledError)) as failure:
        await _attempt_summarization(
            CompactionResult(messages=[]), [Message("user", "Earlier work")], provider,
        )
    assert failure.value is expected
    assert closed == [True]
