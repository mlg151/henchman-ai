"""Inactive protocol bridge uses real runtime ownership with scripted providers."""

import asyncio
import json
import sys
from collections import deque
from functools import partial
from unittest.mock import AsyncMock, MagicMock

import pytest

from henchman.agents.orchestrator import Orchestrator
from henchman.cli.core_init import create_core_context
from henchman.cli.headless_protocol import decode_request
from henchman.cli.headless_runtime import HeadlessRuntime, HeadlessRuntimeError
from henchman.config.schema import Settings
from henchman.core.run_accounting import RunInvocation
from henchman.providers.base import FinishReason, ModelProvider, StreamChunk, ToolCall
from henchman.tools.builtins.tier6_tools import TaskCreateTool
from tests.agents.test_agent_budget_scope import AccountingProvider


async def test_admission_notification_uses_actual_operation_identity_before_provider(monkeypatch):
    provider = AccountingProvider()
    orchestrator = Orchestrator(provider)
    observed = []
    actual = []

    from henchman.core.session_operations import SessionRunOperations

    original = SessionRunOperations.begin

    def begin(self, **kwargs):
        run = original(self, **kwargs)
        actual.append(run)
        return run

    monkeypatch.setattr(SessionRunOperations, "begin", begin)

    async def admitted(identity):
        assert provider.calls == 0
        assert orchestrator._public_run_active
        assert identity.operation_run_id == actual[0].run_id
        assert identity.session_id == actual[0].session.id
        assert identity.project_hash == actual[0].session.project_hash
        observed.append(identity)

    invocation = RunInvocation(on_admitted=admitted)
    _ = [event async for event in orchestrator.run("ordinary input", invocation=invocation)]
    assert invocation.admission is observed[0]
    assert len(observed) == 1 and provider.calls == 1
    assert not orchestrator._public_run_active and not orchestrator.pool._execution_claims


@pytest.mark.parametrize("cancel", [False, True])
async def test_admission_callback_failure_settles_existing_runtime_before_propagating(monkeypatch, cancel):
    provider = AccountingProvider()
    orchestrator = Orchestrator(provider)
    entered = asyncio.Event()
    settlements = []

    from henchman.core.session_operations import SessionRunOperations

    original = SessionRunOperations.finish

    def finish(self, run, *, failed):
        settlements.append((run.run_id, failed))
        return original(self, run, failed=failed)

    monkeypatch.setattr(SessionRunOperations, "finish", finish)

    async def admitted(_identity):
        entered.set()
        if cancel:
            await asyncio.Event().wait()
        raise RuntimeError("callback failed")

    invocation = RunInvocation(on_admitted=admitted)

    async def consume():
        return [event async for event in orchestrator.run("ordinary input", invocation=invocation)]

    task = asyncio.create_task(consume())
    await asyncio.wait_for(entered.wait(), 2)
    if cancel:
        task.cancel()
    with pytest.raises(asyncio.CancelledError if cancel else RuntimeError):
        await task
    assert provider.calls == 0 and invocation.admission is not None
    assert settlements == [(invocation.admission.operation_run_id, True)]
    assert not orchestrator._public_run_active and not orchestrator.pool._execution_claims
    assert invocation.budget_scope.ledger.snapshot().consumed_requests == 0


def request(number, method, params, connection=None):
    value = {"v": 1, "id": number, "method": method, "params": params}
    if method != "initialize":
        value["connection_id"] = connection
    return decode_request(json.dumps(value).encode())


@pytest.fixture
def context(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    provider = MagicMock(spec=ModelProvider)
    provider.name = "offline"
    provider.default_model = "test-model"
    provider.supports_run_budget = False
    provider.calls = 0
    provider.responses = deque([[StreamChunk(content="Done", finish_reason=FinishReason.STOP)]])
    provider.estimate_input_tokens.side_effect = partial(ModelProvider.estimate_input_tokens, provider)
    provider.prepare_output_budget.side_effect = partial(ModelProvider.prepare_output_budget, provider)

    async def stream(*_args, **_kwargs):
        provider.calls += 1
        for chunk in provider.responses.popleft():
            yield chunk

    provider.chat_completion_stream.side_effect = stream
    return create_core_context(provider, settings=Settings(agents={"max_delegation_retries": 0}))


async def initialize(context, *, session=None, sink=None):
    frames = []

    async def emit(frame):
        frames.append(json.loads(frame))
        if sink is not None:
            await sink(frames[-1])

    runtime = HeadlessRuntime(context, emit)
    runtime.receive(request(1, "initialize", {
        "session": session or {"mode": "new"}, "interactive": {"permissions": True, "questions": True},
    }))
    await asyncio.wait_for(runtime.wait_initialized(), 5)
    response = next(frame for frame in frames if frame["kind"] == "response")
    return runtime, frames, response["payload"]["connection_id"], response["session_id"]


def start(runtime, connection, session_id):
    runtime.receive(request(2, "run", {"session_id": session_id, "prompt": "work", "agent": None}, connection))


async def until(predicate):
    async with asyncio.timeout(5):
        while not predicate():
            await asyncio.sleep(0.001)


async def test_bridge_uses_shared_session_workflow_and_actual_run_identity(context):
    runtime, frames, connection, session_id = await initialize(context)
    capabilities = frames[0]["payload"]["capabilities"]
    assert capabilities["background_tasks"] is False and capabilities["lsp_processes"] is False
    start(runtime, connection, session_id)
    await asyncio.wait_for(runtime.wait(), 5)
    result = next(frame for frame in frames if frame["kind"] == "result")
    assert result["run_id"] == runtime.invocation.admission.operation_run_id
    assert result["session_id"] == context.session_manager.current.id == session_id
    assert result["payload"]["status"] == "completed"
    assert result["payload"]["runtime_status"] == "responded"
    assert result["payload"]["task_verified"] is False
    assert [frame["seq"] for frame in frames] == list(range(1, len(frames) + 1))
    assert context.session_manager.workflow_runtime.report().state.inputs[0].state == "completed"
    restored = context.session_manager.load(session_id, project_hash=context.session_manager.current.project_hash)
    assert restored.messages[-1].content == "Done"
    assert not any(frame["kind"] == "event" and frame["payload"].get("type") == "finished" for frame in frames)


@pytest.mark.parametrize("session_id", ["../outside", "missing", "foreign"])
async def test_resume_uses_project_scoped_validated_lookup_without_fallback(context, session_id):
    if session_id == "foreign":
        foreign = context.session_manager.create_session("other-project")
        context.session_manager.save(foreign)
        session_id = foreign.id
    frames = []

    async def emit(frame):
        frames.append(json.loads(frame))

    runtime = HeadlessRuntime(context, emit)
    runtime.receive(request(1, "initialize", {"session": {"mode": "resume", "id": session_id},
                                             "interactive": {"permissions": False, "questions": False}}))
    with pytest.raises(HeadlessRuntimeError):
        await runtime.wait_initialized()
    assert context.provider.calls == 0 and context.session_manager.current is None
    assert frames[-1]["kind"] == "error"
    assert "outside" not in json.dumps(frames)


async def test_cancel_remains_readable_while_event_sink_is_blocked_and_joins_provider(context):
    blocked, release, provider_closed = asyncio.Event(), asyncio.Event(), asyncio.Event()

    async def stream(*_args, **_kwargs):
        try:
            yield StreamChunk(content="partial")
            await asyncio.Event().wait()
        finally:
            provider_closed.set()

    context.provider.chat_completion_stream.side_effect = stream

    async def sink(frame):
        if frame["kind"] == "event" and frame["payload"].get("type") == "content":
            blocked.set()
            await release.wait()

    runtime, frames, connection, session_id = await initialize(context, sink=sink)
    start(runtime, connection, session_id)
    await asyncio.wait_for(blocked.wait(), 5)
    runtime.receive(request(3, "cancel", {"run_request_id": 2, "run_id": runtime.control.run_id}, connection))
    await asyncio.wait_for(runtime.wait_settled(), 5)
    assert provider_closed.is_set()
    assert not any(frame["kind"] == "result" for frame in frames)
    release.set()
    await asyncio.wait_for(runtime.wait(), 5)
    assert provider_closed.is_set()
    results = [frame for frame in frames if frame["kind"] == "result"]
    assert len(results) == 1 and results[0]["payload"]["status"] == "cancelled"
    assert not context.session_manager.workflow_runtime.has_active_dispatch()


async def test_real_write_approval_denial_cannot_be_replaced_by_display_data(context, tmp_path):
    context.provider.responses = deque([
        [StreamChunk(tool_calls=[ToolCall("write", "write_file", {"path": "target.txt", "content": "raw bytes"})],
                     finish_reason=FinishReason.TOOL_CALLS)],
        [StreamChunk(content="Permission denied.", finish_reason=FinishReason.STOP)],
    ])
    runtime, frames, connection, session_id = await initialize(context)
    start(runtime, connection, session_id)
    await until(lambda: runtime.control.pending_decision is not None)
    token = runtime.control.pending_decision
    runtime.receive(request(3, "permission.respond", {"session_id": session_id, "run_id": token.run_id,
        "decision_id": token.id, "generation": token.generation, "approved": False}, connection))
    await asyncio.wait_for(runtime.wait(), 5)
    assert not (tmp_path / "target.txt").exists()
    assert any(frame["payload"].get("type") == "permission" for frame in frames if frame["kind"] == "event")


async def test_eof_equivalent_close_joins_without_claiming_success(context):
    entered, cleanup_started, release = asyncio.Event(), asyncio.Event(), asyncio.Event()

    async def stream(*_args, **_kwargs):
        entered.set()
        try:
            await asyncio.Event().wait()
            yield StreamChunk(content="unreachable")
        finally:
            cleanup_started.set()
            await release.wait()

    context.provider.chat_completion_stream.side_effect = stream
    runtime, _, connection, session_id = await initialize(context)
    start(runtime, connection, session_id)
    await asyncio.wait_for(entered.wait(), 5)
    closing = asyncio.create_task(runtime.aclose())
    await asyncio.wait_for(cleanup_started.wait(), 5)
    assert not closing.done() and runtime.control.result is None
    release.set()
    await asyncio.wait_for(closing, 5)
    assert runtime.control.result.status == "cancelled"


async def test_existing_runtime_work_cannot_be_adopted_or_overwritten(context):
    async def emit(_frame):
        pass

    context.orchestrator._public_run_active = True
    with pytest.raises(HeadlessRuntimeError, match="runtime_busy"):
        HeadlessRuntime(context, emit)
    context.orchestrator._public_run_active = False
    with context.orchestrator.pool.claim_agent(context.agent, owner=object()), pytest.raises(HeadlessRuntimeError, match="runtime_busy"):
        HeadlessRuntime(context, emit)
    first = HeadlessRuntime(context, emit)
    with pytest.raises(HeadlessRuntimeError, match="runtime_owned"):
        HeadlessRuntime(context, emit)
    await first.aclose()


@pytest.mark.parametrize("alias", [False, True])
async def test_background_task_launch_is_denied_before_effect_even_when_autoapproved(context, monkeypatch, alias):
    from henchman.advanced.tasks import TaskService

    class AliasedTask(TaskCreateTool):
        @property
        def name(self):
            return "background_alias"

    if alias:
        context.tool_registry.register(AliasedTask())
    name = "background_alias" if alias else "task_create"
    context.tool_registry.add_auto_approve_policy(name)
    launched = AsyncMock(side_effect=AssertionError("background dispatch forbidden"))
    monkeypatch.setattr(TaskService, "start_task", launched)
    context.provider.responses = deque([
        [StreamChunk(tool_calls=[ToolCall("background", name, {"argv": [sys.executable, "-c", "pass"]})],
                     finish_reason=FinishReason.TOOL_CALLS)],
        [StreamChunk(content="Background launch unavailable.", finish_reason=FinishReason.STOP)],
    ])
    runtime, frames, connection, session_id = await initialize(context)
    start(runtime, connection, session_id)
    await asyncio.wait_for(runtime.wait(), 5)
    assert launched.await_count == 0
    result = next(frame["payload"]["data"] for frame in frames
                  if frame["kind"] == "event" and frame["payload"].get("type") == "tool_call_result")
    assert result["success"] is False and "unavailable" in result["result"]


async def test_question_answer_stays_raw_for_execution_and_projected_for_output(context, monkeypatch):
    from henchman.tools.builtins.ask_user import AskUserTool

    answers = []
    original = AskUserTool.execute

    async def execute(tool, **params):
        result = await original(tool, **params)
        answers.append(result.content)
        return result

    monkeypatch.setattr(AskUserTool, "execute", execute)
    context.provider.responses = deque([
        [StreamChunk(tool_calls=[ToolCall("question", "ask_user", {"question": "Actual choice?"})], finish_reason=FinishReason.TOOL_CALLS)],
        [StreamChunk(content="Received.", finish_reason=FinishReason.STOP)],
    ])
    runtime, frames, connection, session_id = await initialize(context)
    context.session_manager.session_manager.evidence_redactor.register_secret("answer-canary")
    start(runtime, connection, session_id)
    await until(lambda: runtime.control.pending_decision is not None)
    token = runtime.control.pending_decision
    runtime.receive(request(3, "question.respond", {"session_id": session_id, "run_id": token.run_id,
        "decision_id": token.id, "generation": token.generation, "answer": " exact answer-canary\n "}, connection))
    await asyncio.wait_for(runtime.wait(), 5)
    tool = next(message for message in context.agent.current_turn_messages if message.role == "tool")
    assert answers == [" exact answer-canary\n "]
    # The existing journal projects persisted/replayed results before history.
    assert "[REDACTED]" in tool.content
    assert "answer-canary" not in json.dumps(frames)


async def test_cleanup_failure_prevents_premature_result_and_keeps_observed_completion(context, monkeypatch):
    entered, release = asyncio.Event(), asyncio.Event()
    original = context.orchestrator.aclose

    async def failing_close():
        entered.set()
        await release.wait()
        await original()
        raise RuntimeError("cleanup-canary")

    monkeypatch.setattr(context.orchestrator, "aclose", failing_close)
    runtime, frames, connection, session_id = await initialize(context)
    context.session_manager.session_manager.evidence_redactor.register_secret("cleanup-canary")
    start(runtime, connection, session_id)
    await asyncio.wait_for(entered.wait(), 5)
    assert runtime.control.result is None and not any(frame["kind"] == "result" for frame in frames)
    release.set()
    await asyncio.wait_for(runtime.wait(), 5)
    result = next(frame["payload"] for frame in frames if frame["kind"] == "result")
    assert result["status"] == "incomplete" and result["runtime_status"] == "responded"
    assert "cleanup-canary" not in json.dumps(frames)


async def test_cancelled_execution_retains_primary_when_final_session_save_fails(context, monkeypatch):
    entered = asyncio.Event()
    original_cancel = []

    async def stream(*_args, **_kwargs):
        entered.set()
        try:
            await asyncio.Event().wait()
            yield StreamChunk(content="unreachable")
        except asyncio.CancelledError as exc:
            original_cancel.append(exc)
            raise

    context.provider.chat_completion_stream.side_effect = stream
    runtime, frames, connection, session_id = await initialize(context)
    start(runtime, connection, session_id)
    await asyncio.wait_for(entered.wait(), 5)

    def failed_save():
        raise OSError("final save failed")

    monkeypatch.setattr(context.session_manager, "auto_save_session", failed_save)
    runtime.receive(request(3, "cancel", {"run_request_id": 2, "run_id": runtime.control.run_id}, connection))
    await asyncio.wait_for(runtime.wait(), 5)
    assert runtime.failure is original_cancel[0]
    result = next(frame["payload"] for frame in frames if frame["kind"] == "result")
    assert result["status"] == "incomplete" and result["error"] is not None


async def test_sink_failure_is_incomplete_transport_evidence_not_user_cancellation(context):
    async def sink(frame):
        if frame["kind"] == "event" and frame["payload"].get("type") == "content":
            raise BrokenPipeError("owned pipe closed")

    runtime, _, connection, session_id = await initialize(context, sink=sink)
    start(runtime, connection, session_id)
    await asyncio.wait_for(runtime.wait(), 5)
    assert runtime.control.result.status == "incomplete"
    assert isinstance(runtime.failure, BrokenPipeError)


async def test_restored_queue_is_held_and_new_explicit_input_is_only_dispatch(context):
    sessions = context.session_manager
    session = sessions.create_session(sessions.compute_project_hash(context.project_root))
    sessions.set_session(session)
    old = sessions.workflow_runtime.submit("old input must not execute")
    sessions.workflow_runtime.hold_pending()
    sessions.save(session)
    runtime, _, connection, session_id = await initialize(context, session={"mode": "resume", "id": session.id})
    assert not sessions.workflow_runtime.has_ready_input()
    start(runtime, connection, session_id)
    await asyncio.wait_for(runtime.wait(), 5)
    report = sessions.workflow_runtime.report()
    assert next(item for item in report.state.inputs if item.id == old.id).state == "queued"
    assert context.provider.calls == 1
    assert not any(message.content == "old input must not execute" for message in context.agent.messages)


async def test_shutdown_immediately_after_run_reservation_settles_without_dispatch(context):
    runtime, frames, connection, session_id = await initialize(context)
    start(runtime, connection, session_id)
    runtime.receive(request(3, "shutdown", {}, connection))
    await asyncio.wait_for(runtime.wait_settled(), 2)
    await runtime.wait()
    assert context.provider.calls == 0
    assert runtime.control.result.status == "cancelled"
    assert len([frame for frame in frames if frame["kind"] == "result"]) == 1


async def test_shutdown_immediately_after_initialize_joins_cleanup(context):
    frames = []

    async def sink(frame):
        frames.append(json.loads(frame))

    runtime = HeadlessRuntime(context, sink)
    runtime.receive(request(1, "initialize", {
        "session": {"mode": "new"}, "interactive": {"permissions": False, "questions": False},
    }))
    runtime.receive(request(2, "shutdown", {}, None))
    await asyncio.wait_for(runtime.wait_settled(), 2)
    assert context.provider.calls == 0 and runtime._cleaned
    assert frames == []


async def test_repeated_shutdown_cannot_interrupt_owned_cleanup(context, monkeypatch):
    entered, release = asyncio.Event(), asyncio.Event()
    original = context.orchestrator.aclose
    interrupted = []

    async def close():
        entered.set()
        try:
            await release.wait()
        except asyncio.CancelledError:
            interrupted.append(True)
            raise
        await original()

    monkeypatch.setattr(context.orchestrator, "aclose", close)
    runtime, frames, connection, session_id = await initialize(context)
    start(runtime, connection, session_id)
    await asyncio.wait_for(entered.wait(), 5)
    runtime.receive(request(3, "cancel", {"run_request_id": 2, "run_id": runtime.control.run_id}, connection))
    runtime.receive(request(4, "shutdown", {}, connection))
    await asyncio.sleep(0)
    assert not runtime._settled.is_set() and not any(frame["kind"] == "result" for frame in frames)
    release.set()
    await asyncio.wait_for(runtime.wait(), 5)
    assert interrupted == [] and runtime._cleaned
    assert runtime.control.result.status != "completed"


async def test_sink_can_reentrantly_cancel_real_admission_before_provider(context):
    runtime = None
    connection = None

    async def sink(frame):
        if frame["kind"] == "event" and frame["payload"].get("type") == "run_started":
            runtime.receive(request(3, "cancel", {"run_request_id": 2, "run_id": frame["run_id"]}, connection))

    runtime, frames, connection, session_id = await initialize(context, sink=sink)
    start(runtime, connection, session_id)
    await asyncio.wait_for(runtime.wait(), 5)
    assert context.provider.calls == 0 and runtime.invocation.admission is not None
    assert runtime.control.result.status == "cancelled"
    assert len([frame for frame in frames if frame["kind"] == "result"]) == 1


@pytest.mark.parametrize("name,params,decision", [
    ("ask_user", {"question": "choose"}, "question"),
    ("write_file", {"path": "denied.txt", "content": "never written"}, "permission"),
])
async def test_unsupported_decisions_fail_explicitly_without_wait_or_effect(context, name, params, decision):
    frames = []

    async def sink(frame):
        frames.append(json.loads(frame))

    context.provider.responses = deque([
        [StreamChunk(tool_calls=[ToolCall("decision", name, params)], finish_reason=FinishReason.TOOL_CALLS)],
        [StreamChunk(content="Input unavailable.", finish_reason=FinishReason.STOP)],
    ])
    runtime = HeadlessRuntime(context, sink)
    runtime.receive(request(1, "initialize", {
        "session": {"mode": "new"}, "interactive": {"permissions": False, "questions": False},
    }))
    await runtime.wait_initialized()
    start(runtime, runtime._connection, runtime._session.id)
    await asyncio.wait_for(runtime.wait(), 5)
    assert any(frame["payload"].get("type") == decision and frame["payload"].get("state") == "unavailable"
               for frame in frames if frame["kind"] == "event")
    assert runtime.control.pending_decision is None
    assert not (context.project_root / "denied.txt").exists()


async def test_pending_confirmation_is_retired_and_cannot_authorize_after_shutdown(context):
    from henchman.cli.headless_protocol import ProtocolError

    context.provider.responses = deque([
        [StreamChunk(tool_calls=[ToolCall("write", "write_file", {"path": "denied.txt", "content": "no"})],
                     finish_reason=FinishReason.TOOL_CALLS)],
    ])
    runtime, _, connection, session_id = await initialize(context)
    start(runtime, connection, session_id)
    await until(lambda: runtime.control.pending_decision is not None)
    pending = runtime.control.pending_decision
    runtime.receive(request(3, "shutdown", {}, connection))
    with pytest.raises(ProtocolError):
        runtime.receive(request(4, "permission.respond", {"session_id": session_id, "run_id": pending.run_id,
            "decision_id": pending.id, "generation": pending.generation, "approved": True}, connection))
    await asyncio.wait_for(runtime.wait(), 5)
    assert not (context.project_root / "denied.txt").exists()
    assert runtime.control.pending_decision is None


async def test_runtime_restores_owned_callbacks_without_overwriting_replacement(context):
    registry = context.tool_registry
    ask = context.agent.tool_registry.get("ask_user")
    previous = ask._question_handler
    previous_guard = registry._execution_guard
    runtime, _, connection, session_id = await initialize(context)
    replacement = AsyncMock(return_value=False)
    registry.set_confirmation_handler(replacement)
    start(runtime, connection, session_id)
    await asyncio.wait_for(runtime.wait(), 5)
    assert registry._execution_guard is previous_guard
    assert registry._local_confirmation_handler is replacement
    assert ask._question_handler is previous


async def test_real_owned_task_blocks_context_takeover(context):
    from henchman.advanced.tasks import TaskService

    service = TaskService(context.project_root)
    record = await service.start_task(argv=[sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        with pytest.raises(HeadlessRuntimeError, match="runtime_busy"):
            HeadlessRuntime(context, AsyncMock())
    finally:
        await service.stop_task(record.task_id)
    assert not TaskService.has_active_work(context.project_root)


async def test_initialization_failure_still_settles_if_cleanup_fails(context, monkeypatch):
    runtime = HeadlessRuntime(context, AsyncMock())
    monkeypatch.setattr(context.orchestrator, "aclose", AsyncMock(side_effect=OSError("cleanup failure")))
    runtime.receive(request(1, "initialize", {
        "session": {"mode": "resume", "id": "missing"}, "interactive": {"permissions": False, "questions": False},
    }))
    with pytest.raises(HeadlessRuntimeError, match="initialization_failed"):
        await asyncio.wait_for(runtime.wait_initialized(), 5)
    await asyncio.wait_for(runtime.wait_settled(), 2)
    assert runtime.failure is not None and runtime._settlement_failure is not None


async def test_workflow_interruption_persistence_preserves_original_cancellation(context, monkeypatch):
    entered = asyncio.Event()
    interruptions = []

    async def stream(*_args, **_kwargs):
        entered.set()
        try:
            await asyncio.Event().wait()
            yield StreamChunk(content="unreachable")
        except asyncio.CancelledError as exc:
            interruptions.append(exc)
            raise

    context.provider.chat_completion_stream.side_effect = stream
    runtime, frames, connection, session_id = await initialize(context)
    start(runtime, connection, session_id)
    await asyncio.wait_for(entered.wait(), 5)

    def failed_interrupt():
        raise OSError("workflow persistence failed")

    monkeypatch.setattr(context.session_manager.workflow_runtime, "interrupt", failed_interrupt)
    runtime.receive(request(3, "cancel", {"run_request_id": 2, "run_id": runtime.control.run_id}, connection))
    await asyncio.wait_for(runtime.wait(), 5)
    assert runtime.failure is interruptions[0]
    terminal = next(frame["payload"] for frame in frames if frame["kind"] == "result")
    assert terminal["status"] == "incomplete" and terminal["error"] is not None


@pytest.mark.parametrize("name,params", [
    ("shell", {"command": "echo no"}),
    ("shell", {"command": "echo no", "background": True}),
    ("python_exec", {"code": "print('no')"}),
    ("python_exec", {"code": "print('no')", "background": True}),
    ("lsp", {"action": "start", "server": "fixture"}),
    ("lsp", {"action": "request", "server": "fixture", "method": "initialize"}),
    ("lsp", {"action": "stop", "server": "fixture"}),
])
async def test_other_background_entrypoints_are_denied_before_launch(context, monkeypatch, name, params):
    from henchman.advanced.tasks import TaskService
    from henchman.lsp import LspService

    launches = AsyncMock(side_effect=AssertionError("unowned lifecycle dispatched"))
    monkeypatch.setattr(TaskService, "start_task", launches)
    monkeypatch.setattr(LspService, "start_server", launches)
    monkeypatch.setattr(LspService, "request", launches)
    monkeypatch.setattr(LspService, "stop_server", launches)
    context.tool_registry.add_auto_approve_policy(name)
    context.provider.responses = deque([
        [StreamChunk(tool_calls=[ToolCall("background", name, params)], finish_reason=FinishReason.TOOL_CALLS)],
        [StreamChunk(content="Unavailable.", finish_reason=FinishReason.STOP)],
    ])
    runtime, frames, connection, session_id = await initialize(context)
    start(runtime, connection, session_id)
    await asyncio.wait_for(runtime.wait(), 5)
    assert launches.await_count == 0
    result = next(frame["payload"]["data"] for frame in frames
                  if frame["kind"] == "event" and frame["payload"].get("type") == "tool_call_result")
    assert result["success"] is False and "unavailable" in result["result"]


async def test_explicit_foreground_python_still_uses_normal_approval_and_joins_process(context):
    context.provider.responses = deque([
        [StreamChunk(tool_calls=[ToolCall("foreground", "python_exec", {"code": "value = 'joined'\nprint(value)", "background": False})],
                     finish_reason=FinishReason.TOOL_CALLS)],
        [StreamChunk(content="Done.", finish_reason=FinishReason.STOP)],
    ])
    runtime, frames, connection, session_id = await initialize(context)
    start(runtime, connection, session_id)
    await until(lambda: runtime.control.pending_decision is not None)
    token = runtime.control.pending_decision
    runtime.receive(request(3, "permission.respond", {"session_id": session_id, "run_id": token.run_id,
        "decision_id": token.id, "generation": token.generation, "approved": True}, connection))
    await asyncio.wait_for(runtime.wait(), 5)
    result = next(frame["payload"]["data"] for frame in frames
                  if frame["kind"] == "event" and frame["payload"].get("type") == "tool_call_result")
    assert result["success"] is True and "joined" in result["result"]


@pytest.mark.parametrize("cancel", [False, True])
async def test_initialize_ack_allows_reentrant_run_without_losing_task_ownership(context, cancel):
    frames = []
    runtime = None

    async def sink(frame):
        value = json.loads(frame)
        frames.append(value)
        if value["kind"] == "response" and value["payload"].get("method") == "initialize":
            start(runtime, value["payload"]["connection_id"], value["session_id"])
            if cancel:
                runtime.receive(request(3, "cancel", {"run_request_id": 2, "run_id": None}, value["payload"]["connection_id"]))

    runtime = HeadlessRuntime(context, sink)
    runtime.receive(request(1, "initialize", {
        "session": {"mode": "new"}, "interactive": {"permissions": False, "questions": False},
    }))
    await asyncio.wait_for(runtime.wait(), 5)
    assert context.provider.calls == (0 if cancel else 1)
    assert runtime.control.result.status == ("cancelled" if cancel else "completed")
    assert len([frame for frame in frames if frame["kind"] == "result"]) == 1


async def test_final_accounting_read_failure_retains_incomplete_terminal_evidence(context, monkeypatch):
    from henchman.core.run_budget import BudgetAccountingError

    context.provider.supports_run_budget = True
    runtime, frames, connection, session_id = await initialize(context)
    original = context.orchestrator.aclose

    async def close():
        await original()

        def failed_snapshot():
            raise BudgetAccountingError("final accounting evidence unavailable")

        monkeypatch.setattr(runtime.invocation.budget_scope.ledger, "snapshot", failed_snapshot)

    monkeypatch.setattr(context.orchestrator, "aclose", close)
    start(runtime, connection, session_id)
    await asyncio.wait_for(runtime.wait(), 5)
    terminal = next(frame["payload"] for frame in frames if frame["kind"] == "result")
    assert terminal["status"] == "incomplete" and terminal["runtime_status"] == "responded"
    assert terminal["error"] is not None and terminal["task_verified"] is False


async def test_cancel_with_unseen_admission_identity_settles_while_sink_is_blocked(context):
    entered, release = asyncio.Event(), asyncio.Event()

    async def sink(frame):
        if frame["kind"] == "event" and frame["payload"].get("type") == "run_started":
            entered.set()
            await release.wait()

    runtime, frames, connection, session_id = await initialize(context, sink=sink)
    start(runtime, connection, session_id)
    await asyncio.wait_for(entered.wait(), 5)
    try:
        assert runtime.control.run_id is not None  # The client has not received it.
        runtime.receive(request(3, "cancel", {"run_request_id": 2, "run_id": None}, connection))
        await asyncio.wait_for(runtime.wait_settled(), 5)
        assert context.provider.calls == 0 and runtime.control.result.status == "cancelled"
        assert not any(frame["kind"] == "result" for frame in frames)
    finally:
        release.set()
        if not runtime._settled.is_set():
            await runtime.aclose()
    await asyncio.wait_for(runtime.wait(), 5)
    assert len([frame for frame in frames if frame["kind"] == "result"]) == 1


@pytest.mark.parametrize("cancel_caller", [False, True])
async def test_concurrent_aclose_joins_sink_cleanup_despite_caller_cancellation(context, cancel_caller):
    blocked, cleaning, release, joined = (asyncio.Event() for _ in range(4))
    cleanup_interruptions = []

    async def sink(frame):
        if frame["kind"] == "event" and frame["payload"].get("type") == "run_started":
            blocked.set()
            try:
                await asyncio.Event().wait()
            finally:
                cleaning.set()
                try:
                    await release.wait()
                except asyncio.CancelledError:
                    cleanup_interruptions.append(True)
                    raise
                joined.set()

    runtime, frames, connection, session_id = await initialize(context, sink=sink)
    start(runtime, connection, session_id)
    await asyncio.wait_for(blocked.wait(), 5)
    runtime.receive(request(3, "cancel", {"run_request_id": 2, "run_id": None}, connection))
    await asyncio.wait_for(runtime.wait_settled(), 5)
    first = asyncio.create_task(runtime.aclose())
    await asyncio.wait_for(cleaning.wait(), 5)
    second = asyncio.create_task(runtime.aclose())
    if cancel_caller:
        first.cancel("caller interrupted close")
    # Allow the independent closer and cancellation delivery to run while the
    # deterministic cleanup gate remains closed; this is not a latency test.
    await asyncio.sleep(0.05)
    if cancel_caller:
        first.cancel("later cancellation must not replace the first")
        await asyncio.sleep(0)
    premature = first.done() or second.done()
    release.set()
    try:
        if cancel_caller:
            with pytest.raises(asyncio.CancelledError, match="caller interrupted close"):
                await first
        else:
            await first
        await second
        assert not premature
        assert joined.is_set() and cleanup_interruptions == []
        assert not runtime._writers and not runtime._replies
        assert not any(frame["kind"] == "result" for frame in frames)
    finally:
        release.set()
        await asyncio.gather(first, second, return_exceptions=True)
        await runtime.aclose()


async def test_unknown_tool_name_projects_known_credentials_without_changing_dispatch(context, monkeypatch):
    secret = "unknown-tool-private-canary"
    runtime, frames, connection, session_id = await initialize(context)
    context.session_manager.session_manager.evidence_redactor.register_secret(secret)
    context.provider.responses = deque([
        [StreamChunk(tool_calls=[ToolCall("one", secret, {})], finish_reason=FinishReason.TOOL_CALLS)],
        [StreamChunk(content="Tool was unavailable.", finish_reason=FinishReason.STOP)],
    ])
    raw_calls = []
    original = context.agent.tool_registry.execute

    async def execute(name, params):
        raw_calls.append((name, params))
        return await original(name, params)

    monkeypatch.setattr(context.agent.tool_registry, "execute", execute)
    try:
        start(runtime, connection, session_id)
        await asyncio.wait_for(runtime.wait(), 5)
        assert secret not in json.dumps(frames)
        assert raw_calls == [(secret, {})]
        events = [frame["payload"] for frame in frames if frame["kind"] == "event"]
        observed_request = next(event["data"] for event in events if event["type"] == "tool_call_request")
        observed_result = next(event["data"] for event in events if event["type"] == "tool_call_result")
        assert observed_request["id"] == observed_result["tool_call_id"] == "one"
        assert observed_request["name"] == observed_result["tool_name"] == "[REDACTED]"
        assert observed_result["success"] is False
    finally:
        await runtime.aclose()


@pytest.mark.parametrize("fail", [False, True])
async def test_owned_resource_close_finishes_before_result_and_runs_once(context, fail):
    frames = []
    entered, release = asyncio.Event(), asyncio.Event()
    calls = []
    async def emit(frame):
        frames.append(json.loads(frame))
    async def close_resources():
        calls.append(True)
        entered.set()
        await release.wait()
        if fail:
            raise RuntimeError("owned close failed")
    runtime = HeadlessRuntime(context, emit, close_resources=close_resources)
    runtime.receive(request(1, "initialize", {"session": {"mode": "new"},
                    "interactive": {"permissions": False, "questions": False}}))
    await runtime.wait_initialized()
    initial = frames[0]
    start(runtime, initial["payload"]["connection_id"], initial["session_id"])
    await asyncio.wait_for(entered.wait(), 5)
    assert not any(frame["kind"] == "result" for frame in frames)
    release.set()
    await asyncio.wait_for(runtime.wait(), 5)
    result = next(frame for frame in frames if frame["kind"] == "result")
    assert result["payload"]["status"] == ("incomplete" if fail else "completed")
    # Repeated transport close joins the already-owned failed/successful cleanup.
    for _ in range(2):
        try:
            await runtime.aclose()
        except RuntimeError:
            assert fail
    assert calls == [True]
