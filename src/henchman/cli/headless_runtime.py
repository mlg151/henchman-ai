"""Inactive one-run protocol adapter over an exclusively owned CoreContext.

The embedding supplies a cancellable asynchronous byte sink. This module owns
no stdin/stdout, CLI route or provider loop. A bounded number of serialized writes
may wait for the sink. Producer cancellation never abandons a partial write and
then appends another frame; transport close aborts delivery and joins writers.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import asdict
from pathlib import Path
from typing import Any, TypeVar, cast
from uuid import uuid4

from henchman.advanced.tasks import TaskService
from henchman.cli.core_init import CoreContext
from henchman.cli.evidence import runtime_evidence_redactor, runtime_exception_text
from henchman.cli.headless import HeadlessRunObservation, forward_headless_events
from henchman.cli.headless_control import HeadlessControl, PendingDecision, ResultStatus
from henchman.cli.headless_protocol import FrameKind, ProtocolError, Request, ServerEncoder
from henchman.cli.json_output import event_to_dict
from henchman.cli.workflow import execute_workflow_input
from henchman.core.event_evidence import EventEvidenceRedactor
from henchman.core.events import AgentEvent, EventType
from henchman.core.run_accounting import (
    RunAdmissionIdentity,
    RunInvocation,
    budget_snapshot_payload,
)
from henchman.core.run_budget import BudgetControlError, BudgetSnapshot
from henchman.tools.base import ConfirmationRequest, Tool, ToolResult
from henchman.tools.builtins.ask_user import AskUserTool
from henchman.tools.builtins.python_exec import PythonExecTool
from henchman.tools.builtins.shell import ShellTool
from henchman.tools.builtins.tier6_tools import LSPTool, TaskCreateTool
from henchman.utils.evidence_redaction import PRESERVE_IDENTITY

_T = TypeVar("_T")
_MAX_WRITERS = 8
_MAX_REPLIES = 4
_MAX_PROMPTS = 4
_RUNTIME_STATUSES = {"completed", "responded", "no_work_done", "stalled", "timed_out", "failed"}


class HeadlessRuntimeError(RuntimeError):
    """Value-free adapter failure; raw input is never included."""

    def __init__(self, code: str) -> None:
        super().__init__(code if code in {
            "runtime_busy", "runtime_owned", "project_changed", "session_changed", "initialization_failed",
            "output_limit", "output_closed", "input_unavailable", "recovery_required", "runtime_closed",
        } else "runtime_closed")


async def _joined_storage(action: Callable[[], _T]) -> _T:
    """Wait for synchronous storage to stop before honoring cancellation."""
    return await _joined(asyncio.create_task(asyncio.to_thread(action)))


async def _joined(worker: asyncio.Task[_T]) -> _T:
    """Join owned cleanup without replacing an interruption with cleanup error."""
    cancellation: asyncio.CancelledError | None = None
    while True:
        try:
            result = await asyncio.shield(worker)
            break
        except asyncio.CancelledError as exc:
            cancellation = cancellation or exc
            if worker.done():
                break
        except BaseException:
            if cancellation is not None:
                cancellation.add_note("Headless owned cleanup also failed")
                raise cancellation from None
            raise
    if cancellation is not None:
        # Retrieve any worker exception without replacing the original cancel.
        if not worker.cancelled():
            worker.exception()
        raise cancellation
    return result


class HeadlessRuntime:
    """Bind one protocol conversation to existing session and run authorities.

    ``receive`` handles cancellation synchronously even while publication waits.
    ``wait_settled`` observes execution cleanup, not output delivery. ``aclose``
    means the transport is lost: it joins writers and emits nothing afterwards.
    The sink must support cancellation; a future stdio adapter owns nonblocking
    OS I/O, delivery deadlines, and process exit status.

    The trusted embedding transfers an idle context exclusively. Existing
    shared-runtime claims are checked, but arbitrary concurrent calls directly
    into its raw agents/components are outside this ownership contract.
    """

    def __init__(self, context: CoreContext, sink: Callable[[bytes], Awaitable[None]], *,
                 close_resources: Callable[[], Awaitable[None]] | None = None) -> None:
        if getattr(context, "_headless_runtime_owner", None) is not None:
            raise HeadlessRuntimeError("runtime_owned")
        self.context = context
        self._close_resources = close_resources
        self._require_idle()
        self._root = context.project_root.resolve()
        stat = self._root.stat()
        self._project_identity = (stat.st_dev, stat.st_ino)
        self._project_hash = context.session_manager.compute_project_hash(self._root)
        self._sink = sink
        self.control = HeadlessControl()
        self.invocation = RunInvocation(on_admitted=self._admitted)
        self._encoder = ServerEncoder()
        self._policy = runtime_evidence_redactor(context)
        self._events = EventEvidenceRedactor(self._policy, finish_all=True)
        self._write_lock = asyncio.Lock()
        self._prompt_lock = asyncio.Lock()
        self._writers: set[asyncio.Task[None]] = set()
        self._replies: set[asyncio.Task[None]] = set()
        self._main: asyncio.Task[None] | None = None
        self._initializer: asyncio.Task[None] | None = None
        self._main_started = False
        self._binding_ready = False
        self._cancelled_main: asyncio.Task[None] | None = None
        self._cleanup_task: asyncio.Task[None] | None = None
        self._close_task: asyncio.Task[None] | None = None
        self._initialized = asyncio.Event()
        self._settled = asyncio.Event()
        self._initialization_error: BaseException | None = None
        self.failure: BaseException | None = None
        self._transport_failure: BaseException | None = None
        self._settlement_failure: BaseException | None = None
        self._execution_failure: BaseException | None = None
        self._input_failure: ProtocolError | None = None
        self._output_closed = False
        self._cleaned = False
        self._session: Any = None
        self._connection = uuid4().hex
        self._waiting_prompts = 0
        self._answer: tuple[PendingDecision, asyncio.Future[object]] | None = None
        self._old_guard = context.tool_registry._execution_guard
        self._guard_callback = self._guard
        self._old_confirmation = context.tool_registry._local_confirmation_handler
        self._confirm_callback = self._confirm
        self._questions: list[tuple[AskUserTool, Callable[[str], Awaitable[str | None]] | None]] = []
        self._question_callback = self._question
        context.__dict__["_headless_runtime_owner"] = self

    def _require_idle(self) -> None:
        context = self.context
        if (context.orchestrator._public_run_active or context.orchestrator.pool._execution_claims
            or context.orchestrator.subagents.has_running_work()
            or context.session_manager.workflow_runtime.has_active_dispatch()
            or any(not task.done() for task in context.background_tasks)
            or TaskService.has_active_work(context.project_root)):
            raise HeadlessRuntimeError("runtime_busy")

    def _check_project(self) -> None:
        stat = self._root.stat()
        if (Path.cwd().resolve() != self._root or self.context.project_root.resolve() != self._root
            or (stat.st_dev, stat.st_ino) != self._project_identity):
            raise HeadlessRuntimeError("project_changed")

    def _check_session(self) -> None:
        self._check_project()
        if (self.context.session_manager.current is not self._session or self._session is None
            or self._session.project_hash != self._project_hash):
            raise HeadlessRuntimeError("session_changed")

    def receive(self, request: Request) -> None:
        """Accept controls without waiting for a blocked byte sink."""
        if request.method == "run" and not self._binding_ready:
            raise HeadlessRuntimeError("initialization_failed")
        intent = self.control.receive(request)
        if request.method == "initialize":
            self._main_started = False
            self._main = asyncio.create_task(self._initialize(request))
            self._initializer = self._main
        elif request.method == "run":
            self._main_started = False
            self._main = asyncio.create_task(self._run(request))
        elif request.method == "cancel":
            self._cancel_owned()
            self._reply(request.id, {"method": "cancel", "state": "requested"})
        elif request.method == "shutdown":
            self._cancel_owned()
            if self._main is None or self._main.done():
                self._main = asyncio.create_task(self._shutdown_idle())
        else:
            answer = self._answer
            if answer is None or intent.decision is not answer[0] or answer[1].done():
                raise ProtocolError("stale_decision")
            self._reply(request.id, {"method": request.method, "state": "received"})
            answer[1].set_result(request.params.get("approved") if request.method == "permission.respond"
                                 else request.params.get("answer"))

    def _cancel_owned(self) -> None:
        if self._answer is not None and not self._answer[1].done():
            self._answer[1].cancel()
        if (self._main_started and self._main is not None and not self._main.done()
            and self._main is not self._cancelled_main):
            self._cancelled_main = self._main
            self._main.cancel()
        if self._initializer is not None and self._initializer is not self._main and not self._initializer.done():
            self._initializer.cancel()

    def _reply(self, request_id: int, payload: dict[str, object]) -> None:
        self._queue_reply("response", request_id, payload)

    def _queue_reply(self, kind: FrameKind, request_id: int | None, payload: dict[str, object]) -> None:
        if len(self._replies) >= _MAX_REPLIES:
            failure = HeadlessRuntimeError("output_limit")
            self._fail_transport(failure)
            raise failure
        task = asyncio.create_task(self._send(kind, request_id, lambda: self._project(payload)))
        self._replies.add(task)
        task.add_done_callback(self._reply_done)

    def stop_input(self, error: ProtocolError | None = None) -> None:
        """Retire transport input, preserving joined execution and wire ownership.

        A signal is an explicit stop request. Malformed input additionally makes
        a still-running result incomplete; neither can rewrite an existing claim.
        EOF/output loss instead uses ``aclose`` and cannot claim delivery.
        """
        if error is not None and self._input_failure is None:
            self._input_failure = error
            self._queue_reply("error", None, {"code": error.code, "message": "Protocol input rejected."})
        self.control.disconnect()
        self._cancel_owned()
        if self._main is None or self._main.done():
            self._main = asyncio.create_task(self._shutdown_idle())

    def _reply_done(self, task: asyncio.Task[None]) -> None:
        self._replies.discard(task)
        if not task.cancelled() and task.exception() is not None:
            self._fail_transport(cast(BaseException, task.exception()))

    def _fail_transport(self, failure: BaseException) -> None:
        if self._transport_failure is None:
            self._transport_failure = failure
            self.failure = failure
            self._output_closed = True
            self.control.disconnect()
            self._cancel_owned()

    def _project(self, payload: dict[str, object]) -> dict[str, object]:
        schema = dict.fromkeys(("method", "type", "state", "connection_id", "decision_id", "generation"), PRESERVE_IDENTITY)
        schema["capabilities"] = dict.fromkeys(("permissions", "questions", "background_tasks", "lsp_processes"), PRESERVE_IDENTITY)
        return cast(dict[str, object], self._policy.redact(payload, schema=schema))

    async def _write(self, action: Callable[[], Awaitable[None]]) -> None:
        async with self._write_lock:
            if self._output_closed:
                raise HeadlessRuntimeError("output_closed")
            await action()

    async def _publish(self, action: Callable[[], Awaitable[None]]) -> None:
        if self._output_closed:
            raise HeadlessRuntimeError("output_closed")
        if len(self._writers) >= _MAX_WRITERS:
            raise HeadlessRuntimeError("output_limit")
        writer = asyncio.create_task(self._write(action))
        self._writers.add(writer)
        writer.add_done_callback(self._writer_done)
        await asyncio.shield(writer)

    def _writer_done(self, writer: asyncio.Task[None]) -> None:
        self._writers.discard(writer)
        if not writer.cancelled() and writer.exception() is not None:
            self._fail_transport(cast(BaseException, writer.exception()))

    async def _send(self, kind: FrameKind, request_id: int | None,
                    payload: Callable[[], object]) -> None:
        async def write() -> None:
            frame = self._encoder.encode(kind=kind, request_id=request_id,
                session_id=self._session.id if self._session is not None else None,
                run_id=self.control.run_id, payload=payload())
            await self._sink(frame)
        await self._publish(write)

    async def _send_event(self, event: AgentEvent) -> None:
        # Bound and detach raw evidence before an awaited sink can retain it.
        raw = ServerEncoder().encode(kind="event", request_id=None, session_id=None, run_id=None,
                                     payload=event_to_dict(event))
        snapshot = json.loads(raw)["payload"]
        copied = AgentEvent(event.type, snapshot.get("data"), snapshot.get("source_agent"))

        async def write() -> None:
            for projected in self._events.project(copied):
                if projected.type == EventType.FINISHED:
                    continue  # Flush evidence; only the joined result is terminal.
                await self._sink(self._encoder.encode(kind="event", request_id=self._run_request_id,
                    session_id=self._session.id, run_id=self.control.run_id, payload=event_to_dict(projected)))
        await self._publish(write)

    @property
    def _run_request_id(self) -> int | None:
        return self._run_request.id if hasattr(self, "_run_request") else None

    async def _initialize(self, request: Request) -> None:
        self._main_started = True
        try:
            if self.control.closing:
                raise asyncio.CancelledError
            self._check_project()
            self._require_idle()
            sessions = self.context.session_manager
            selection = cast(Mapping[str, object], request.params["session"])
            if selection["mode"] == "resume":
                selected = cast(str, selection["id"])
                session = await _joined_storage(lambda: sessions.load(selected, project_hash=self._project_hash))
                if session.id != selected:
                    raise HeadlessRuntimeError("session_changed")
            else:
                session = sessions.create_session(self._project_hash)
                await _joined_storage(lambda: sessions.save(session))
            self._check_project()
            self._require_idle()
            await _joined_storage(lambda: sessions.set_session(session))
            self._session = session
            self._check_session()
            self.context.tool_registry.bind_execution_guard(self._guard_callback)
            self.context.tool_registry.set_confirmation_handler(self._confirm_callback)
            registries = [self.context.tool_registry, *(agent.tool_registry for agent in self.context.orchestrator.pool._agents.values())]
            seen: set[int] = set()
            for registry in registries:
                for name in registry.list_tools():
                    tool = registry.get(name)
                    if not isinstance(tool, AskUserTool) or id(tool) in seen:
                        continue
                    seen.add(id(tool))
                    self._questions.append((tool, tool._question_handler))
                    tool._question_handler = self._question_callback
            self.control.bind_session(connection_id=self._connection, session_id=session.id)
            self._binding_ready = True
            await self._send("response", request.id, lambda: self._project({
                "method": "initialize", "connection_id": self._connection,
                "capabilities": {**dict(cast(Mapping[str, object], request.params["interactive"])),
                                 "background_tasks": False, "lsp_processes": False},
            }))
            self._initialized.set()
        except BaseException as exc:
            self._initialization_error = exc
            self.failure = exc
            self.control.disconnect()
            try:
                await self._cleanup()
            except BaseException as cleanup:
                self._settlement_failure = cleanup
                exc.add_note("Headless initialization cleanup also failed")
            finally:
                self._settled.set()
            if not self._output_closed and isinstance(exc, Exception):
                await self._send("error", request.id, lambda: {
                    "code": "initialization_failed", "message": "Requested session could not be initialized.",
                })

    def _guard(self, tool: Tool, params: dict[str, object]) -> ToolResult | None:
        if self._cleaned or self.control.closing or self.control.cancellation_requested:
            return ToolResult("Headless runtime is closing.", success=False, error="runtime_closed")
        self._check_session()
        if (isinstance(tool, TaskCreateTool) or tool.name == "task_create"
            or (isinstance(tool, (ShellTool, PythonExecTool)) and params.get("background", True) is not False)):
            return ToolResult("Background task launch is unavailable in this headless runtime. "
                              "Use shell or python_exec with explicit background=false to await completion.",
                              success=False, error="unsupported_background_launch")
        if isinstance(tool, LSPTool) and params.get("action") in {"start", "request", "stop"}:
            return ToolResult("LSP process lifecycle is unavailable in this headless runtime.",
                              success=False, error="unsupported_background_lifecycle")
        return self._old_guard(tool, params) if self._old_guard is not None else None

    async def _admitted(self, admission: RunAdmissionIdentity) -> None:
        self._check_session()
        if admission.session_id != self._session.id or admission.project_hash != self._project_hash:
            raise HeadlessRuntimeError("session_changed")
        self.control.admit_run(admission.operation_run_id)
        await self._send("event", self._run_request_id, lambda: {"type": "run_started"})

    async def _decision(self, kind: str, evidence: dict[str, object]) -> object:
        if self._waiting_prompts >= _MAX_PROMPTS:
            raise HeadlessRuntimeError("input_unavailable")
        self._waiting_prompts += 1
        try:
            async with self._prompt_lock:
                self._check_session()
                try:
                    pending = self.control.begin_decision(uuid4().hex, cast(Any, kind))
                except ProtocolError as exc:
                    if exc.code != "input_unavailable":
                        raise
                    await self._send("event", self._run_request_id, lambda: self._project({
                        "type": kind, "state": "unavailable", **evidence,
                    }))
                    raise HeadlessRuntimeError("input_unavailable") from None
                answer: asyncio.Future[object] = asyncio.get_running_loop().create_future()
                self._answer = (pending, answer)
                try:
                    await self._send("event", self._run_request_id, lambda: self._project({
                        "type": kind, "state": "pending", "decision_id": pending.id,
                        "generation": pending.generation, **evidence,
                    }))
                    return await answer
                finally:
                    self.control.retire_decision(pending)
                    if self._answer is not None and self._answer[0] is pending:
                        self._answer = None
                    if not answer.done():
                        answer.cancel()
        finally:
            self._waiting_prompts -= 1

    async def _confirm(self, request: ConfirmationRequest) -> bool:
        return await self._decision("permission", asdict(request)) is True

    async def _question(self, question: str) -> str | None:
        try:
            answer = await self._decision("question", {"question": question})
        except HeadlessRuntimeError:
            return None
        return answer if isinstance(answer, str) else None

    async def _run(self, request: Request) -> None:
        self._main_started = True
        self._run_request = request
        observation = HeadlessRunObservation()
        status: ResultStatus = "failed"
        primary: BaseException | None = None
        runtime_status: str | None = None
        budget: BudgetSnapshot | None = None
        try:
            if self.control.closing or self.control.cancellation_requested:
                raise asyncio.CancelledError
            if self._initializer is not None:
                await asyncio.shield(self._initializer)
            if not self._initialized.is_set():
                raise HeadlessRuntimeError("initialization_failed")
            self._check_session()
            self._require_idle()
            context = self.context
            role = cast(str | None, request.params["agent"])
            agent = context.orchestrator.pool.get_agent(role) if role else context.agent
            await _joined_storage(lambda: context.session_manager.set_session(self._session, history_agent=agent))
            self._check_session()
            workflow = context.session_manager.workflow_runtime
            queued = workflow.submit(cast(str, request.params["prompt"]), kind="direct" if role else "message", role=role)
            dispatch = workflow.next_input()
            if dispatch is None or dispatch.permit.input_id != queued.id:
                workflow.hold_pending()
                raise HeadlessRuntimeError("recovery_required")

            async def execute() -> bool:
                start = len(self._session.messages)
                turn = agent._turn_number
                context.session_manager.record_user_message(dispatch.text)
                execution_error: BaseException | None = None
                try:
                    stream = (context.orchestrator.run_direct(role, dispatch.text, invocation=self.invocation) if role
                              else context.orchestrator.run(dispatch.text, invocation=self.invocation))
                    await forward_headless_events(stream, role or "tech_lead", self._send_event, observation)
                    return observation.completion is not None and observation.completion.get("status") in {"completed", "responded"}
                except BaseException as exc:
                    execution_error = exc
                    self._execution_failure = exc
                    raise
                finally:
                    try:
                        if agent._turn_number != turn:
                            context.session_manager.sync_agent_turn(agent, session_start=start)
                        await _joined_storage(context.session_manager.auto_save_session)
                    except BaseException as persistence:
                        self._settlement_failure = persistence
                        if execution_error is None:
                            raise
                        execution_error.add_note("Headless session persistence also failed")

            succeeded = await execute_workflow_input(workflow, dispatch, execute)
            status = "completed" if succeeded else "incomplete"
        except asyncio.CancelledError as exc:
            primary, status = exc, "cancelled"
        except BaseException as exc:
            if self._execution_failure is not None and self._execution_failure is not exc:
                primary = self._execution_failure
                self._settlement_failure = exc
                primary.add_note("Headless workflow settlement also failed")
                status = "incomplete"
            else:
                primary = exc
                status = "rejected" if self.control.run_id is None else "failed"
        finally:
            if observation.completion is not None:
                value = observation.completion.get("status")
                runtime_status = value if isinstance(value, str) and value in _RUNTIME_STATUSES else None
            try:
                await self._cleanup()
            except BaseException as cleanup:
                self._settlement_failure = cleanup
                if primary is not None:
                    primary.add_note("Headless runtime cleanup also failed")
                else:
                    primary = cleanup
                status = "incomplete"
            if self.invocation.budget_scope is not None:
                try:
                    budget = self.invocation.budget_scope.ledger.snapshot()
                except BudgetControlError as accounting:
                    self._settlement_failure = accounting
                    primary = primary or accounting
                    status = "incomplete"
            if self._transport_failure is not None:
                primary = self._transport_failure
                status = "incomplete"
            if self._settlement_failure is not None:
                status = "incomplete"
            if self._input_failure is not None:
                if primary is None or isinstance(primary, asyncio.CancelledError):
                    primary = self._input_failure
                status = "incomplete"
            self.failure = primary
            self.control.claim_result(status)
            self._settled.set()
            if not self._output_closed:
                try:
                    await self._send_event(AgentEvent(EventType.FINISHED, {"scope": "run", "finish_reason":
                        "stop" if status == "completed" else "cancelled" if status == "cancelled" else "error"}))
                    def payload() -> dict[str, object]:
                        error = None
                        error_source = primary if not isinstance(primary, asyncio.CancelledError) else self._settlement_failure
                        if error_source is not None:
                            message = runtime_exception_text(self.context, error_source).encode("utf-8")[:3000].decode("utf-8", errors="ignore")
                            error = {"code": "runtime_error", "message": message}
                        return {"status": status, "runtime_status": runtime_status,
                                "task_verified": False, "error": error,
                                "budget": budget_snapshot_payload(budget, redactor=self._policy) if budget is not None else None}
                    await self._send("result", request.id, payload)
                except BaseException:
                    self._output_closed = True

    async def _cleanup(self) -> None:
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_owned())
        await _joined(self._cleanup_task)

    async def _cleanup_owned(self) -> None:
        if self._cleaned:
            return
        try:
            for task in self.context.background_tasks:
                task.cancel()
            if self.context.background_tasks:
                await asyncio.gather(*self.context.background_tasks, return_exceptions=True)
                self.context.background_tasks.clear()
            await self.context.orchestrator.aclose()
        finally:
            try:
                if self.context.mcp_manager is not None:
                    await self.context.mcp_manager.disconnect_all()
            finally:
                try:
                    if self._close_resources is not None:
                        await self._close_resources()
                finally:
                    self._cleaned = True
                    registry = self.context.tool_registry
                    if registry._execution_guard is self._guard_callback:
                        registry.bind_execution_guard(self._old_guard)
                    if registry._local_confirmation_handler is self._confirm_callback:
                        registry.set_confirmation_handler(cast(Any, self._old_confirmation))
                    for tool, handler in self._questions:
                        if tool._question_handler is self._question_callback:
                            tool._question_handler = handler
        if TaskService.has_active_work(self._root):
            raise HeadlessRuntimeError("runtime_busy")

    async def _shutdown_idle(self) -> None:
        try:
            await self._cleanup()
        finally:
            self._settled.set()

    async def wait_initialized(self) -> None:
        if self._initializer is not None:
            await asyncio.shield(self._initializer)
        if self._initialization_error is not None or not self._initialized.is_set():
            raise HeadlessRuntimeError("initialization_failed") from None

    async def wait_settled(self) -> None:
        await self._settled.wait()

    async def wait(self) -> None:
        while self._main is not None:
            task = self._main
            await asyncio.shield(task)
            if task is self._main:
                break
        if self._replies:
            await asyncio.gather(*self._replies, return_exceptions=True)
        if self._writers:
            await asyncio.gather(*self._writers, return_exceptions=True)

    async def aclose(self) -> None:
        """Abort a lost transport and join both runtime and pending writes."""
        if self._close_task is None:
            self._close_task = asyncio.create_task(self._close_owned())
        await _joined(self._close_task)

    async def _close_owned(self) -> None:
        """Deliver each cancellation once; callers only join this owner."""
        self._output_closed = True
        self.control.disconnect()
        self._cancel_owned()
        for task in (*self._replies, *self._writers):
            task.cancel()
        if self._main is not None:
            await asyncio.gather(self._main, return_exceptions=True)
        if self._initializer is not None:
            await asyncio.gather(self._initializer, return_exceptions=True)
        await asyncio.gather(*self._replies, *self._writers, return_exceptions=True)
        await self._shutdown_idle()
