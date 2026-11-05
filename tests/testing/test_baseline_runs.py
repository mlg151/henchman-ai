"""Bounded repeat-run baseline runner records every run, not just successes."""

from __future__ import annotations

import asyncio
import json
import math
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

import pytest
from evals import baseline_runs
from evals.helpers import EvalTestRig, MockProvider
from evals.release_corpus import list_cases
from tests.testing.test_counter_eval_contract import (
    _GLOBAL_COUNTER,
    _INSTANCE_COUNTER,
    _write_counter,
)

from henchman.providers.base import (
    FinishReason,
    Message,
    StreamChunk,
    ToolCall,
    ToolDeclaration,
)


class HangingProvider(MockProvider):
    """Provider whose stream never completes, to exercise the bounded timeout."""

    async def chat_completion_stream(
        self,
        messages: list[Message],
        tools: list[ToolDeclaration] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[StreamChunk, None]:
        self.calls.append({"messages": messages, "tools": tools})
        await asyncio.sleep(60)
        yield StreamChunk(content="too late")
        return


class AlwaysToolProvider(MockProvider):
    """Provider that always requests a tool, to exercise iteration caps."""

    async def chat_completion_stream(
        self,
        messages: list[Message],
        tools: list[ToolDeclaration] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[StreamChunk, None]:
        self.calls.append({"messages": messages, "tools": tools})
        yield StreamChunk(
            tool_calls=[ToolCall(
                id=f"call_{len(self.calls)}",
                name="write_file",
                arguments={"path": "counter.py", "content": "x"},
            )],
            finish_reason=FinishReason.TOOL_CALLS,
        )
        return


def _percentile(values: list[float], pct: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * pct / 100.0
    low = math.floor(rank)
    high = math.ceil(rank)
    if low == high:
        return ordered[int(rank)]
    return ordered[low] + (ordered[high] - ordered[low]) * (rank - low)


async def test_two_successful_runs_record_two_successes() -> None:
    # One full scripted response per run: the mock queue is consumed per turn.
    provider = _write_counter(_INSTANCE_COUNTER)
    provider.set_tool_response(
        "write_file", {"path": "counter.py", "content": _INSTANCE_COUNTER}, "Refactored.",
    )
    records = await baseline_runs.run_case_repeated(
        "counter-refactor", provider=provider, runs=2
    )
    assert [record.run_index for record in records] == [1, 2]
    assert all(record.outcome == "success" for record in records)
    assert all(record.task_verified for record in records)
    assert all(record.error is None for record in records)
    assert all(record.profile == "engineer" for record in records)
    assert all(record.duration_ms > 0 for record in records)


async def test_wrong_patch_records_verification_failure_for_every_run() -> None:
    provider = _write_counter(_GLOBAL_COUNTER)
    records = await baseline_runs.run_case_repeated(
        "counter-refactor", provider=provider, runs=2
    )
    assert len(records) == 2
    assert all(record.outcome == "verification_failure" for record in records)
    assert all(not record.task_verified for record in records)
    assert all(record.error for record in records)


async def test_hanging_provider_is_classified_as_timeout() -> None:
    provider = HangingProvider()
    provider.set_tool_response("write_file", {"path": "counter.py", "content": ""}, "ok")
    records = await baseline_runs.run_case_repeated(
        "counter-refactor", provider=provider, runs=1, timeout=1.5
    )
    assert records[0].outcome == "timeout"
    assert not records[0].task_verified
    assert "timed out" in (records[0].error or "").lower()


async def test_env_timeout_is_a_hard_cap_on_case_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The runner's per-run bound is a ceiling: a case-declared per-turn
    # timeout may never exceed the EVAL_TIMEOUT the runner scoped.
    monkeypatch.setenv("EVAL_TIMEOUT", "1.5")
    provider = HangingProvider()
    rig = EvalTestRig(provider=provider, profile="engineer")
    rig.setup("cap_timeout_case")
    result = await rig.run("Wait", timeout=5.0)
    assert "timed out after 1.5s" in (result.error or "")


async def test_env_max_iterations_is_a_hard_cap_on_case_iterations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EVAL_MAX_ITERATIONS", "2")
    provider = AlwaysToolProvider()
    rig = EvalTestRig(provider=provider, profile="engineer")
    rig.setup("cap_iterations_case")
    result = await rig.run("Loop", max_iterations=10)
    assert "Tool iteration limit (2) reached" in (result.error or "")


async def test_unreported_usage_is_marked_unavailable() -> None:
    # The headless eval path does not surface provider usage; a 0/0 reading
    # means unreported and must not read as "0 tokens, available".
    provider = _write_counter(_INSTANCE_COUNTER)
    provider.set_tool_response(
        "write_file", {"path": "counter.py", "content": _INSTANCE_COUNTER}, "Refactored.",
    )
    records = await baseline_runs.run_case_repeated(
        "counter-refactor", provider=provider, runs=1
    )
    assert records[0].outcome == "success"
    assert records[0].tokens_in is None
    assert records[0].tokens_out is None
    summary = baseline_runs.summarize_runs(records)
    assert summary["usage"] == {"tokens_in": None, "tokens_out": None, "available": False}


async def test_provider_crash_is_classified_as_runtime_error() -> None:
    from tests.testing.test_counter_eval_contract import ErrorAfterWriteProvider

    provider = ErrorAfterWriteProvider()
    provider.set_tool_response(
        "write_file", {"path": "counter.py", "content": _INSTANCE_COUNTER}, "Refactored."
    )
    records = await baseline_runs.run_case_repeated(
        "counter-refactor", provider=provider, runs=1
    )
    assert records[0].outcome == "runtime_error"
    assert "Provider failed after writing counter" in (records[0].error or "")
    assert not records[0].task_verified


def test_summarize_publishes_denominators_and_latency() -> None:
    records = [
        baseline_runs.RunRecord(
            case_id="counter-refactor", run_index=1, profile="engineer",
            outcome="success", duration_ms=100.0,
            tokens_in=10, tokens_out=5, task_verified=True, error=None,
        ),
        baseline_runs.RunRecord(
            case_id="counter-refactor", run_index=2, profile="engineer",
            outcome="verification_failure", duration_ms=300.0,
            tokens_in=12, tokens_out=7, task_verified=False, error="wrong patch",
        ),
        baseline_runs.RunRecord(
            case_id="fibonacci", run_index=1, profile="basic",
            outcome="success", duration_ms=40.0,
            tokens_in=None, tokens_out=None, task_verified=True, error=None,
        ),
    ]
    summary = baseline_runs.summarize_runs(records)
    assert summary["total_runs"] == 3
    assert summary["successes"] == 2
    assert summary["failures"] == 1
    assert summary["outcome_counts"] == {
        "success": 2, "verification_failure": 1, "timeout": 0, "runtime_error": 0,
    }
    case_summary = summary["cases"]["counter-refactor"]
    assert case_summary["runs"] == 2 and case_summary["successes"] == 1
    assert case_summary["outcome_counts"]["verification_failure"] == 1
    # Linear interpolation (numpy convention): p95 of [40, 100, 300] is 280.
    assert summary["latency_ms"]["p50"] == pytest.approx(100.0)
    assert summary["latency_ms"]["p95"] == pytest.approx(280.0)
    assert summary["latency_ms"]["min"] == pytest.approx(40.0)
    assert summary["latency_ms"]["max"] == pytest.approx(300.0)
    assert summary["usage"] == {
        "tokens_in": 22, "tokens_out": 12, "available": True,
    }


def test_summarize_usage_unknown_when_provider_reports_no_usage() -> None:
    records = [
        baseline_runs.RunRecord(
            case_id="counter-refactor", run_index=1, profile="engineer",
            outcome="success", duration_ms=10.0,
            tokens_in=None, tokens_out=None, task_verified=True, error=None,
        ),
    ]
    summary = baseline_runs.summarize_runs(records)
    assert summary["usage"] == {"tokens_in": None, "tokens_out": None, "available": False}
    assert summary["latency_ms"] == {
        "p50": 10.0, "p95": 10.0, "min": 10.0, "max": 10.0,
    }


def test_summarize_empty_is_an_explicit_zero_denominator() -> None:
    summary = baseline_runs.summarize_runs([])
    assert summary["total_runs"] == 0
    assert summary["latency_ms"] is None
    assert summary["usage"] == {"tokens_in": None, "tokens_out": None, "available": False}


def test_cohort_is_derived_from_the_provider() -> None:
    assert baseline_runs.cohort_for_provider("openrouter") == "hosted"
    assert baseline_runs.cohort_for_provider("deepseek") == "hosted"
    assert baseline_runs.cohort_for_provider("openai_compat") == "local"
    assert baseline_runs.cohort_for_provider("ollama") == "local"
    assert baseline_runs.cohort_for_provider("mock") == "local"


def test_cost_provenance_distinguishes_local_from_hosted() -> None:
    local = baseline_runs.cost_provenance("local")
    assert local == {"source": "local", "amount_usd": 0.0, "billing": "none"}
    assert baseline_runs.cost_provenance("hosted") is None


def test_report_is_atomic_redacted_and_carries_the_denominator(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    records = [
        baseline_runs.RunRecord(
            case_id="counter-refactor", run_index=1, profile="engineer",
            outcome="success", duration_ms=12.5,
            tokens_in=4, tokens_out=2, task_verified=True, error=None,
        ),
    ]
    report = baseline_runs.build_report(
        cohort="local",
        requested={"cases": ["counter-refactor"], "runs_per_case": 1,
                  "timeout": 120.0, "max_iterations": 10,
                  "provider": "mock", "model": "mock-model"},
        summary=baseline_runs.summarize_runs(records),
        records=records,
    )
    assert report["kind"] == "baseline_repeat_runs"
    assert report["cohort"] == "local"
    assert report["budget"] == {"planned_runs": 1, "executed_runs": 1}
    assert report["summary"]["total_runs"] == 1
    assert report["cost"] == {"source": "local", "amount_usd": 0.0, "billing": "none"}
    assert report["runs"][0]["case_id"] == "counter-refactor"
    assert report["runs"][0]["outcome"] == "success"

    monkeypatch.setenv("BASELINE_RUNS_SECRET_KEY", "super-secret-value")
    baseline_runs.write_report(tmp_path / "baseline.json", report)
    raw = (tmp_path / "baseline.json").read_text()
    document = json.loads(raw)
    assert "super-secret-value" not in raw
    assert document == json.loads(json.dumps(report, sort_keys=True))
    # No partial document remains: the write replaced the file atomically.
    assert list(tmp_path.glob("baseline.json*")) == [tmp_path / "baseline.json"]
    assert not list(tmp_path.glob(".baseline*"))


def test_main_runs_declared_budget_and_reports_denominator(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    provider = _write_counter(_INSTANCE_COUNTER)
    provider.set_tool_response(
        "write_file", {"path": "counter.py", "content": _INSTANCE_COUNTER}, "Refactored.",
    )
    monkeypatch.setattr(baseline_runs, "get_eval_provider", lambda: provider)
    executed: list[str] = []
    real_runner = baseline_runs.run_case_repeated

    async def spy(case_id: str, **kwargs: Any) -> list:
        executed.append(case_id)
        return await real_runner(case_id, **kwargs)

    monkeypatch.setattr(baseline_runs, "run_case_repeated", spy)
    code = baseline_runs.main([
        "--cases", "counter-refactor", "--runs", "2",
        "--timeout", "30", "--report", "baseline.json",
    ])
    assert code == 0
    report = json.loads((tmp_path / "baseline.json").read_text())
    # One runner invocation per case; the two runs happen inside it.
    assert executed == ["counter-refactor"]
    assert report["budget"] == {"planned_runs": 2, "executed_runs": 2}
    assert report["summary"]["total_runs"] == 2
    assert report["summary"]["successes"] == 2
    assert report["cohort"] == "local"
    assert report["requested"]["cases"] == ["counter-refactor"]
    assert report["requested"]["runs_per_case"] == 2


def test_main_failing_runs_exit_nonzero_but_still_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    provider = _write_counter(_GLOBAL_COUNTER)
    monkeypatch.setattr(baseline_runs, "get_eval_provider", lambda: provider)
    code = baseline_runs.main([
        "--cases", "counter-refactor", "--runs", "2",
        "--timeout", "30", "--report", "baseline.json",
    ])
    assert code == 1
    report = json.loads((tmp_path / "baseline.json").read_text())
    assert report["summary"]["total_runs"] == 2
    assert report["summary"]["successes"] == 0
    assert report["summary"]["outcome_counts"]["verification_failure"] == 2


def test_main_rejects_unknown_case_and_unknown_provider(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit) as exc:
        baseline_runs.main(["--cases", "no-such-case", "--report", "baseline.json"])
    assert exc.value.code == 2
    assert not (tmp_path / "baseline.json").exists()
    monkeypatch.delenv("EVAL_PROVIDER", raising=False)
    monkeypatch.delenv("EVAL_MODEL", raising=False)
    monkeypatch.delenv("EVAL_BASE_URL", raising=False)
    monkeypatch.setenv("EVAL_PROVIDER", "no-such-provider")
    with pytest.raises(SystemExit) as exc:
        baseline_runs.main(["--cases", "counter-refactor", "--report", "baseline.json"])
    assert exc.value.code == 2


def test_default_case_selection_covers_the_registered_corpus(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(baseline_runs, "get_eval_provider", lambda: MockProvider())
    executed: list[str] = []

    async def spy(case_id: str, **_: Any) -> list:
        executed.append(case_id)
        return [
            baseline_runs.RunRecord(
                case_id=case_id, run_index=1, profile="basic",
                outcome="success", duration_ms=1.0,
                tokens_in=None, tokens_out=None, task_verified=True, error=None,
            )
        ]

    monkeypatch.setattr(baseline_runs, "run_case_repeated", spy)
    code = baseline_runs.main(["--runs", "1", "--report", "baseline.json"])
    registered = {metadata.id for metadata in list_cases()}
    assert code == 0
    assert set(executed) == registered
    assert len(executed) == len(registered)
    report = json.loads((tmp_path / "baseline.json").read_text())
    assert report["budget"]["planned_runs"] == len(registered)
    assert report["summary"]["total_runs"] == len(registered)
