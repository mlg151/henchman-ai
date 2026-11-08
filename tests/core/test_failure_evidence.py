"""Lower-level failure logs project credentials before logger formatting."""

from __future__ import annotations

import asyncio
import logging
from types import SimpleNamespace

import pytest

from henchman.agents.delegation import _fetch_agent_errors
from henchman.agents.delegation_manager import DelegationManager
from henchman.agents.orchestrator_execution import closing_event_stream
from henchman.core.agent_streaming import StreamContext, StreamState, generate_stream_events
from henchman.core.failure_evidence import failure_evidence_redactor
from henchman.core.runtime_operations import use_operation_run
from henchman.providers.base import FinishReason, StreamChunk, ToolCall
from henchman.utils.evidence_redaction import EvidenceRedactor
from henchman.utils.exception_evidence import exception_text

OLD = 'old-private-credential-"escaped"'
NEW = "new-private-credential"


def assert_safe_logs(caplog: pytest.LogCaptureFixture, *diagnostics: str) -> str:
    assert caplog.records
    rendered = "\n".join(logging.Formatter("%(levelname)s:%(message)s").format(record)
                         for record in caplog.records)
    for value in (OLD, NEW, "unregistered-local-only"):
        assert value not in rendered
    assert all(record.exc_info is None for record in caplog.records)
    assert "[REDACTED]" in rendered
    for value in diagnostics:
        assert value in rendered
    return rendered


class FailedClose:
    def __init__(self, error: BaseException, before_cancel=lambda: None) -> None:
        self.error = error
        self.before_cancel = before_cancel
        self.closed = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        self.before_cancel()
        raise asyncio.CancelledError("original caller cancellation")

    async def aclose(self):
        self.closed = True
        local_only = "unregistered-local-only"
        assert local_only
        raise self.error


@pytest.mark.asyncio
async def test_provider_cancel_cleanup_retains_old_and_current_provider_credentials(caplog):
    provider = SimpleNamespace(api_key=OLD)
    failure = OSError(f"close failed: {OLD} and {NEW}")
    stream = FailedClose(failure, lambda: setattr(provider, "api_key", NEW))
    provider.chat_completion_stream = lambda **_kwargs: stream
    ctx = StreamContext(provider=provider, api_messages=[], history=[], tool_declarations=[])
    with pytest.raises(asyncio.CancelledError, match="original caller cancellation"):
        async for _ in generate_stream_events(ctx, StreamState(), compacted=False):
            pass
    assert stream.closed
    assert str(failure) == f"close failed: {OLD} and {NEW}"
    assert_safe_logs(caplog, "Provider cleanup failed", "OSError", "aclose")


@pytest.mark.asyncio
async def test_forwarded_stream_cleanup_captures_operation_policy_and_exception_chain(caplog):
    policy = EvidenceRedactor([OLD])
    run = SimpleNamespace(session=SimpleNamespace(evidence_redactor=policy))
    primary = asyncio.CancelledError("keep original identity")
    failure = OSError(f"cleanup {OLD} {NEW}")
    failure.__cause__ = ValueError("Authorization: Bearer header-private-value")
    failure.add_note("header-private-value")
    stream = FailedClose(failure)
    with pytest.raises(asyncio.CancelledError) as caught, use_operation_run(run):
        async with closing_event_stream(stream):
            policy.register_secret(NEW)
            raise primary
    assert caught.value is primary
    rendered = assert_safe_logs(caplog, "Agent stream cleanup failed", "OSError", "ValueError", "direct cause")
    assert "header-private-value" not in rendered
    assert stream.closed


@pytest.mark.asyncio
async def test_forwarded_stream_environment_rotation_and_primary_failure(caplog, monkeypatch):
    monkeypatch.setenv("HENCHMAN_API_KEY", OLD)
    primary = RuntimeError("primary failure")
    stream = FailedClose(OSError(f"cleanup {OLD} {NEW}"))
    with pytest.raises(RuntimeError) as caught:
        async with closing_event_stream(stream):
            monkeypatch.setenv("HENCHMAN_API_KEY", NEW)
            raise primary
    assert caught.value is primary
    assert_safe_logs(caplog, "cleanup", "OSError")


@pytest.mark.asyncio
async def test_uninterrupted_cleanup_failure_is_still_original_exception():
    failure = OSError("ordinary cleanup failure")
    with pytest.raises(OSError) as caught:
        async with closing_event_stream(FailedClose(failure)):
            pass
    assert caught.value is failure


@pytest.mark.asyncio
async def test_delegation_failures_preserve_execution_inputs_and_correlations(caplog):
    caplog.set_level(logging.INFO)
    failure = RuntimeError(f"delegation failed {OLD} {NEW}")
    source = SimpleNamespace(provider=SimpleNamespace(api_key=OLD))

    class Runner:
        settings = SimpleNamespace(model_dump=lambda: {"api_key": NEW})

        async def run_delegation(self, params):
            assert params.task == OLD
            assert params.target_role == NEW
            raise failure
            yield

    manager = DelegationManager(Runner())
    call = ToolCall("unchanged-call-id", "delegate_task", {"agent": NEW, "task": OLD})
    identity = await manager.start_delegation(source, call, 0)
    record = manager.ongoing_tasks[identity]
    await record.asyncio_task
    assert record.tool_call_id == call.id == "unchanged-call-id"
    assert record.task_future.exception() is failure
    assert record.error == str(failure)
    content, success = await manager.wait_for_delegation(identity)
    assert not success and "Delegation failed" in content
    assert manager.submit_delegation_result(identity) is False
    assert_safe_logs(caplog, identity, "RuntimeError", "run_delegation", "result retrieval failed", "Failed to submit")


@pytest.mark.parametrize("kind", [RuntimeError, KeyError])
def test_fetch_delegation_errors_projects_both_warning_paths(caplog, kind):
    failure = kind(f"fetch {OLD}")

    def fail():
        raise failure

    target = SimpleNamespace(provider=SimpleNamespace(api_key=OLD), get_delegation_errors=fail)
    assert _fetch_agent_errors(target) == []
    assert_safe_logs(caplog, kind.__name__, "fetch", "fail")


def test_explicit_policy_merges_runtime_held_credentials_without_changing_inputs():
    provider = SimpleNamespace(api_key=OLD)
    runtime = SimpleNamespace(provider=provider)
    held = failure_evidence_redactor(runtime)
    provider.api_key = NEW
    destination = EvidenceRedactor()
    failure = RuntimeError(f"previous={OLD}; current={NEW}")

    assert failure_evidence_redactor(runtime, redactor=destination) is destination
    projected = exception_text(failure, destination)
    assert OLD not in projected and NEW not in projected
    assert runtime._failure_evidence_redactor is held
    assert provider.api_key == NEW and str(failure) == f"previous={OLD}; current={NEW}"


@pytest.mark.asyncio
async def test_provider_held_history_survives_rotation_then_delegation_diagnostic(caplog):
    async def stream(**_kwargs):
        yield StreamChunk(content="safe response", finish_reason=FinishReason.STOP)

    provider = SimpleNamespace(api_key=OLD, chat_completion_stream=stream)
    context = StreamContext(provider=provider, api_messages=[], history=[], tool_declarations=[])
    _ = [event async for event in generate_stream_events(context, StreamState(), compacted=False)]
    assert provider._failure_evidence_redactor.text(OLD) == "[REDACTED]"
    provider.api_key = NEW
    failure = RuntimeError(f"previous request={OLD}; current request={NEW}")

    def errors():
        raise failure

    agent = SimpleNamespace(provider=provider, get_delegation_errors=errors)
    assert _fetch_agent_errors(agent) == []
    assert_safe_logs(caplog, "previous request", "current request")
    assert str(failure) == f"previous request={OLD}; current request={NEW}"
    assert provider.api_key == NEW
