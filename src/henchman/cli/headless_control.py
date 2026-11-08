"""Inactive headless connection controls; runtime authority stays in the core.

An embedding consumes intents, uses existing session/run/registry services, and
binds their actual identities. No method here grants a tool, resumes work, owns
a worker, or proves cleanup finished. In particular, requesting cancellation is
not a terminal result. The embedding claims its observed outcome after joining.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal, cast

from henchman.cli.headless_protocol import (
    MAX_SAFE_INTEGER,
    RESULT_STATUSES,
    ProtocolError,
    Request,
    identity,
)

DecisionKind = Literal["permission", "question"]
ResultStatus = Literal["completed", "failed", "cancelled", "incomplete", "rejected"]


@dataclass(frozen=True)
class PendingDecision:
    """Transport waiter identity, never a tool grant or execution permit."""

    id: str
    generation: int
    kind: DecisionKind
    session_id: str
    run_id: str


@dataclass(frozen=True)
class ControlIntent:
    """A validated request for the embedding; raw input is excluded from repr."""

    request: Request = field(repr=False)
    changed: bool = True
    decision: PendingDecision | None = None


@dataclass(frozen=True)
class ResultClaim:
    """An embedding-supplied outcome, not proof of delivery or task correctness."""

    request_id: int
    session_id: str
    run_id: str | None
    status: ResultStatus

    @property
    def admitted(self) -> bool:
        return self.run_id is not None


class HeadlessControl:
    """One connection, explicit session binding, and at most one run intent.

    Calls are synchronous and must be serialized by one event-loop owner. This
    object stores no prompts, answers, approval parameters or session history.
    """

    def __init__(self) -> None:
        self._last_request = 0
        self._initializing = False
        self._capabilities: Mapping[str, object] = {}
        self._connection_id: str | None = None
        self._session_id: str | None = None
        self._requested_session_id: str | None = None
        self._run_request: int | None = None
        self._run_id: str | None = None
        self._generation = 0
        self._pending: PendingDecision | None = None
        self._cancellation_requested = False
        self._closing = False
        self._result: ResultClaim | None = None

    @property
    def run_id(self) -> str | None:
        return self._run_id

    @property
    def pending_decision(self) -> PendingDecision | None:
        return self._pending

    @property
    def cancellation_requested(self) -> bool:
        return self._cancellation_requested

    @property
    def closing(self) -> bool:
        return self._closing

    @property
    def result(self) -> ResultClaim | None:
        return self._result

    def receive(self, request: Request) -> ControlIntent:
        """Validate a transport request and return an intent, without effects."""
        if request.id <= self._last_request:
            raise ProtocolError("request_replayed")
        self._last_request = request.id
        if self._closing:
            raise ProtocolError("connection_closing")
        if request.method == "initialize":
            if self._initializing or self._session_id is not None:
                raise ProtocolError("already_initialized")
            self._initializing = True
            self._capabilities = cast(Mapping[str, object], request.params["interactive"])
            selection = cast(Mapping[str, object], request.params["session"])
            self._requested_session_id = cast(str | None, selection.get("id"))
            return ControlIntent(request)
        if request.method == "shutdown" and request.connection_id == self._connection_id:
            self.disconnect()
            return ControlIntent(request)
        if self._session_id is None:
            raise ProtocolError("not_initialized")
        if request.connection_id != self._connection_id:
            raise ProtocolError("connection_mismatch")
        if request.method == "run":
            if self._run_request is not None:
                raise ProtocolError("run_already_reserved")
            if request.params["session_id"] != self._session_id:
                raise ProtocolError("session_mismatch")
            self._run_request = request.id
            return ControlIntent(request)
        if request.method == "cancel":
            if self._run_request is None:
                raise ProtocolError("run_not_reserved")
            # Admission may be ahead of a blocked client output stream. The
            # exact connection-owned request remains a cancellation target even
            # before the client observes its actual runtime identity.
            if (request.params["run_request_id"] != self._run_request
                or (request.params["run_id"] is not None and request.params["run_id"] != self._run_id)):
                raise ProtocolError("run_mismatch")
            if self._result is not None:
                raise ProtocolError("run_finished")
            changed = not self._cancellation_requested
            self._cancellation_requested = True
            self._pending = None
            return ControlIntent(request, changed=changed)
        if request.method in {"permission.respond", "question.respond"}:
            pending = self._pending
            if (pending is None or request.method != f"{pending.kind}.respond"
                or request.params["session_id"] != pending.session_id
                or request.params["run_id"] != pending.run_id
                or request.params["decision_id"] != pending.id
                or request.params["generation"] != pending.generation):
                raise ProtocolError("stale_decision")
            self._pending = None
            return ControlIntent(request, decision=pending)
        raise ProtocolError("connection_mismatch")

    def bind_session(self, *, connection_id: str, session_id: str) -> None:
        """Bind identities supplied by the trusted embedding after session setup."""
        if self._closing:
            raise ProtocolError("connection_closing")
        if self._session_id is not None:
            raise ProtocolError("already_initialized")
        if not self._initializing:
            raise ProtocolError("not_initialized")
        connection_id, session_id = identity(connection_id), identity(session_id)
        if self._requested_session_id is not None and session_id != self._requested_session_id:
            raise ProtocolError("session_mismatch")
        self._connection_id, self._session_id = connection_id, session_id

    def admit_run(self, operation_run_id: str) -> None:
        """Bind the core OperationRun identity once, never an invented wire ID."""
        if self._run_id is not None:
            raise ProtocolError("already_admitted")
        if self._closing:
            raise ProtocolError("connection_closing")
        if self._cancellation_requested:
            raise ProtocolError("cancellation_requested")
        if self._run_request is None:
            raise ProtocolError("run_not_reserved")
        if self._result is not None:
            raise ProtocolError("run_finished")
        self._run_id = identity(operation_run_id)

    def begin_decision(self, decision_id: str, kind: DecisionKind) -> PendingDecision:
        """Reserve one advertised input channel; embedding serializes waiters."""
        if self._closing:
            raise ProtocolError("connection_closing")
        if self._cancellation_requested:
            raise ProtocolError("cancellation_requested")
        if self._run_id is None or self._session_id is None:
            raise ProtocolError("run_not_reserved")
        if self._result is not None:
            raise ProtocolError("run_finished")
        capability = {"permission": "permissions", "question": "questions"}.get(kind)
        if capability is None or self._capabilities.get(capability) is not True:
            raise ProtocolError("input_unavailable")
        if self._pending is not None:
            raise ProtocolError("decision_pending")
        if self._generation >= MAX_SAFE_INTEGER:
            raise ProtocolError("sequence_exhausted")
        decision_id = identity(decision_id)
        self._generation += 1
        self._pending = PendingDecision(decision_id, self._generation, kind, self._session_id, self._run_id)
        return self._pending

    def retire_decision(self, decision: PendingDecision) -> bool:
        """A timed-out owner may remove only its own still-current waiter."""
        if self._pending is not decision:
            return False
        self._pending = None
        return True

    def disconnect(self) -> None:
        """Retire controls and request cancellation, without asserting cleanup."""
        self._closing = True
        self._pending = None
        if self._run_request is not None and self._result is None:
            self._cancellation_requested = True

    def claim_result(self, status: ResultStatus) -> ResultClaim:
        """Called only by the embedding after joining runtime cleanup.

        A cancellation request cannot establish the observed terminal status;
        a completed run may also have won a race with that request. This method
        records the caller's observation, and cannot prove its cleanup occurred.
        """
        if self._result is not None:
            raise ProtocolError("result_already_claimed")
        if self._run_request is None or self._session_id is None:
            raise ProtocolError("run_not_reserved")
        if not isinstance(status, str) or status not in RESULT_STATUSES:
            raise ProtocolError("invalid_result")
        if status == "completed" and self._run_id is None:
            raise ProtocolError("result_requires_admission")
        if status == "rejected" and self._run_id is not None:
            raise ProtocolError("invalid_result")
        self._pending = None
        self._result = ResultClaim(self._run_request, self._session_id, self._run_id, status)
        return self._result
