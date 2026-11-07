"""Versioned goal and input state; saved state never grants replay permission."""

from __future__ import annotations

import hashlib
import os
from datetime import UTC, datetime
from threading import RLock
from typing import Annotated, Literal
from uuid import uuid4

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from henchman.core.operation_recovery import OperationRecoveryError
from henchman.utils.evidence_redaction import EvidenceRedactor

Identity = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_.:-]{1,128}$")]
Digest = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
BoundedText = Annotated[str, StringConstraints(max_length=65536)]
InputState = Literal["queued", "started", "completed", "cancelled", "outcome_unknown"]
InputKind = Literal["message", "command", "direct"]
InputOutcome = Literal["success", "failure"]
MAX_WORKFLOW_BYTES = 4 * 1024 * 1024


class WorkflowError(OperationRecoveryError):
    """Workflow authority is unavailable or a requested transition conflicts."""


class _Record(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, validate_default=True)

    @field_validator("version", mode="before", check_fields=False)
    @classmethod
    def _version(cls, value: object) -> object:
        if type(value) is not int or value != 1:
            raise ValueError("Unsupported workflow version")
        return value


class GoalPolicy(_Record):
    """Evidence of accepted boundaries, never restored approval grants."""

    plan_mode: bool = False
    plan_mode_origin: Literal["user", "model"] = "user"
    tool_policy_digest: Digest | None = None
    instruction_digest: Digest | None = None


class GoalCheckReference(_Record):
    plan_id: Identity
    spec_digest: Digest
    observed_run_id: Identity | None = None


class WorkflowGoal(_Record):
    version: Literal[1] = 1
    id: Identity
    revision: int = Field(default=1, ge=1)
    objective: BoundedText
    objective_sha256: Digest | None = None
    availability: Literal["complete", "redacted"] = "complete"
    status: Literal["active", "paused", "complete"] = "active"
    completion_summary: BoundedText = ""
    policy: GoalPolicy = Field(default_factory=GoalPolicy)
    checks: tuple[GoalCheckReference, ...] = Field(default=(), max_length=32)

    @model_validator(mode="after")
    def _consistent(self) -> WorkflowGoal:
        if not self.objective.strip() or len({item.plan_id for item in self.checks}) != len(self.checks):
            raise ValueError("Invalid goal objective or duplicate check reference")
        if self.status == "complete" and not self.completion_summary.strip():
            raise ValueError("Completed goal requires a summary")
        if self.availability == "complete" and self.objective_sha256 is not None and hashlib.sha256(self.objective.encode()).hexdigest() != self.objective_sha256:
            raise ValueError("Goal objective integrity failed")
        return self


class QueuedInput(_Record):
    id: Identity
    revision: int = Field(default=1, ge=1)
    order: int = Field(ge=0)
    kind: InputKind = "message"
    role: Identity | None = None
    state: InputState = "queued"
    text: BoundedText | None
    text_sha256: Digest
    preview: BoundedText
    availability: Literal["complete", "redacted"]
    owner_id: Identity
    created_at: Annotated[str, StringConstraints(max_length=64)]
    updated_at: Annotated[str, StringConstraints(max_length=64)]
    claim_id: Identity | None = None
    outcome: InputOutcome | None = None
    resolution: Literal["abandoned"] | None = None
    resolution_note: BoundedText = ""

    @model_validator(mode="after")
    def _consistent(self) -> QueuedInput:
        if any(datetime.fromisoformat(value).tzinfo is None for value in (self.created_at, self.updated_at)):
            raise ValueError("Input timestamps require a timezone")
        if (self.kind == "direct") != (self.role is not None):
            raise ValueError("Direct inputs require an explicit role")
        if (self.availability == "complete") != (self.text is not None):
            raise ValueError("Unavailable input cannot carry executable text")
        if not self.preview.strip() or (self.text is not None and not self.text.strip()):
            raise ValueError("Input cannot be empty")
        if self.text is not None and hashlib.sha256(self.text.encode()).hexdigest() != self.text_sha256:
            raise ValueError("Input text integrity failed")
        if self.state in {"queued", "cancelled"} and self.claim_id is not None:
            raise ValueError("Undispatched input cannot carry a claim")
        if self.state in {"started", "completed", "outcome_unknown"} and self.claim_id is None:
            raise ValueError("Dispatched input requires its original claim")
        if (self.state == "completed") != (self.outcome is not None):
            raise ValueError("Only completed input has a known outcome")
        if self.resolution is not None and (self.state != "outcome_unknown" or not self.resolution_note.strip()):
            raise ValueError("Resolution requires uncertain input and an explicit note")
        return self


class WorkflowState(_Record):
    version: Literal[1] = 1
    project_hash: Identity
    session_id: Identity
    revision: int = Field(default=0, ge=0)
    goal: WorkflowGoal | None = None
    inputs: tuple[QueuedInput, ...] = Field(default=(), max_length=1024)

    @model_validator(mode="after")
    def _consistent(self) -> WorkflowState:
        if len({item.id for item in self.inputs}) != len(self.inputs):
            raise ValueError("Duplicate input identity")
        if len({item.order for item in self.inputs}) != len(self.inputs):
            raise ValueError("Duplicate input order")
        return self


class WorkflowReference(_Record):
    version: Literal[1] = 1
    store_id: Identity
    project_hash: Identity
    session_id: Identity


class InputPermit(_Record):
    """Returned after committed start, retained only by the executing runtime."""

    project_hash: Identity
    session_id: Identity
    input_id: Identity
    owner_id: Identity
    claim_id: Identity


def decode_state(payload: str) -> WorkflowState:
    if not isinstance(payload, str) or len(payload.encode("utf-8")) > MAX_WORKFLOW_BYTES:
        raise WorkflowError("invalid_state")
    try:
        return WorkflowState.model_validate_json(payload)
    except ValueError as exc:
        raise WorkflowError("invalid_state") from exc


def encode_state(state: WorkflowState) -> str:
    payload = state.model_dump_json()
    if len(payload.encode("utf-8")) > MAX_WORKFLOW_BYTES:
        raise WorkflowError("workflow_size_limit")
    return payload


class WorkflowJournal:
    """Pure in-memory authority, also reconstructed inside store transactions."""

    def __init__(self, project_hash: str, session_id: str, *, owner_id: str | None = None,
                 state: WorkflowState | None = None, redactor: EvidenceRedactor | None = None) -> None:
        self.state = state or WorkflowState(project_hash=project_hash, session_id=session_id)
        if (self.state.project_hash, self.state.session_id) != (project_hash, session_id):
            raise WorkflowError("session_identity_mismatch")
        self._origin_pid = os.getpid()
        self._owner_id = owner_id or f"{os.getpid()}:{uuid4().hex}"
        self.redactor = redactor if redactor is not None else EvidenceRedactor()
        self._lock = RLock()

    @property
    def owner_id(self) -> str:
        if os.getpid() != self._origin_pid:
            raise WorkflowError("process_authority_changed")
        return self._owner_id

    def snapshot(self) -> WorkflowState:
        return self.state

    def report(self) -> WorkflowState:
        """Observers classify unowned starts without changing original authority."""
        state = self.projected_state()
        return state.model_copy(update={"inputs": tuple(
            item.model_copy(update={"state": "outcome_unknown"})
            if item.state == "started" and item.owner_id != self.owner_id else item
            for item in state.inputs)})

    def projected_state(self) -> WorkflowState:
        """Project all evidence using current credentials before any persistence."""
        inputs = []
        for item in self.state.inputs:
            text = item.text
            changed = text is not None and self.redactor.text(text) != text
            inputs.append(item.model_copy(update={
                "text": None if changed else text,
                "availability": "redacted" if changed else item.availability,
                "preview": self.redactor.text(item.preview),
                "resolution_note": self.redactor.text(item.resolution_note),
            }))
        goal = self.state.goal
        if goal is not None:
            objective = self.redactor.text(goal.objective)
            goal = goal.model_copy(update={
                "objective": objective,
                "objective_sha256": goal.objective_sha256 or hashlib.sha256(goal.objective.encode()).hexdigest(),
                "availability": "redacted" if objective != goal.objective else goal.availability,
                "completion_summary": self.redactor.text(goal.completion_summary),
            })
        return WorkflowState.model_validate({**self.state.model_dump(), "inputs": tuple(inputs), "goal": goal})

    def _set(self, **changes: object) -> None:
        state = WorkflowState.model_validate({**self.state.model_dump(), **changes, "revision": self.state.revision + 1})
        encode_state(state)
        self.state = state

    def _find(self, input_id: str, revision: int | None = None) -> QueuedInput:
        item = next((record for record in self.state.inputs if record.id == input_id), None)
        if item is None:
            raise WorkflowError("missing_input")
        if revision is not None and (type(revision) is not int or revision != item.revision):
            raise WorkflowError("revision_conflict")
        return item

    def _replace(self, item: QueuedInput, **changes: object) -> QueuedInput:
        record = QueuedInput.model_validate({**item.model_dump(), **changes, "revision": item.revision + 1,
                                            "updated_at": datetime.now(UTC).isoformat()})
        self._set(inputs=tuple(record if current.id == item.id else current for current in self.state.inputs))
        return record

    def _text(self, text: str) -> dict[str, object]:
        if not isinstance(text, str) or not text.strip() or len(text) > 65536:
            raise WorkflowError("invalid_input_text")
        projected = self.redactor.text(text)
        if len(projected) > 65536:
            raise WorkflowError("input_projection_limit")
        return {"text": text if projected == text else None, "preview": projected,
                "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
                "availability": "complete" if projected == text else "redacted"}

    def enqueue(self, text: str, *, kind: InputKind = "message", role: str | None = None,
                input_id: str | None = None) -> QueuedInput:
        with self._lock:
            now = datetime.now(UTC).isoformat()
            record = QueuedInput.model_validate({"id": input_id or uuid4().hex, "order": max((item.order for item in self.state.inputs), default=-1) + 1,
                                                 "kind": kind, "role": role, "owner_id": self.owner_id,
                                                 "created_at": now, "updated_at": now, **self._text(text)})
            self._set(inputs=(*self.state.inputs, record))
            return record

    def edit(self, input_id: str, revision: int, text: str) -> QueuedInput:
        with self._lock:
            item = self._find(input_id, revision)
            if item.state != "queued":
                raise WorkflowError("input_not_queued")
            return self._replace(item, **self._text(text))

    def transfer_queued(self, input_id: str, revision: int, *, live_text: str | None = None) -> QueuedInput:
        """User-only transfer; caller must separately arm a runtime dispatch."""
        with self._lock:
            item = self._find(input_id, revision)
            if item.state != "queued":
                raise WorkflowError("input_not_queued")
            if item.availability != "complete" and not (item.owner_id == self.owner_id and live_text is not None
                                                         and hashlib.sha256(live_text.encode()).hexdigest() == item.text_sha256):
                raise WorkflowError("input_payload_unavailable")
            return self._replace(item, owner_id=self.owner_id)

    def claim(self, input_id: str, revision: int, *, live_text: str | None = None) -> InputPermit:
        with self._lock:
            item = self._find(input_id, revision)
            if item.state != "queued":
                raise WorkflowError("input_not_queued")
            if item.owner_id != self.owner_id:
                raise WorkflowError("input_owner_changed")
            if any(other.state == "started" for other in self.state.inputs):
                raise WorkflowError("workflow_dispatch_active")
            if any(other.state == "outcome_unknown" and other.resolution is None for other in self.state.inputs):
                raise WorkflowError("workflow_recovery_required")
            text = live_text if live_text is not None else item.text
            if (text is None or hashlib.sha256(text.encode()).hexdigest() != item.text_sha256
                or (live_text is None and self.redactor.text(text) != text)):
                raise WorkflowError("input_payload_unavailable")
            record = self._replace(item, state="started", claim_id=uuid4().hex)
            assert record.claim_id is not None
            return InputPermit(project_hash=self.state.project_hash, session_id=self.state.session_id,
                               input_id=record.id, owner_id=record.owner_id, claim_id=record.claim_id)

    def finish(self, permit: InputPermit, *, outcome: InputOutcome) -> QueuedInput:
        with self._lock:
            item = self._find(permit.input_id)
            if (permit.project_hash, permit.session_id, permit.owner_id, permit.claim_id) != (
                self.state.project_hash, self.state.session_id, item.owner_id, item.claim_id
            ) or self.owner_id != permit.owner_id:
                raise WorkflowError("input_owner_changed")
            if item.state == "completed" and item.outcome == outcome:
                return item
            if item.state not in {"started", "outcome_unknown"} or item.resolution is not None:
                raise WorkflowError("input_already_settled")
            return self._replace(item, state="completed", outcome=outcome)

    def cancel(self, input_id: str, revision: int) -> QueuedInput:
        with self._lock:
            item = self._find(input_id, revision)
            if item.state == "queued":
                return self._replace(item, state="cancelled")
            if item.state == "started" and item.owner_id == self.owner_id:
                return self._replace(item, state="outcome_unknown")
            raise WorkflowError("input_not_cancellable")

    def abandon(self, input_id: str, revision: int, note: str) -> QueuedInput:
        with self._lock:
            item = self._find(input_id, revision)
            if item.state != "outcome_unknown" and not (item.state == "started" and item.owner_id != self.owner_id):
                raise WorkflowError("input_not_uncertain")
            if item.resolution is not None or not isinstance(note, str) or not note.strip():
                raise WorkflowError("invalid_resolution")
            return self._replace(item, state="outcome_unknown", resolution="abandoned", resolution_note=self.redactor.text(note))

    def set_goal(self, goal: WorkflowGoal | None, *, expected_revision: int) -> WorkflowGoal | None:
        with self._lock:
            if type(expected_revision) is not int or self.state.revision != expected_revision:
                raise WorkflowError("revision_conflict")
            previous = self.state.goal
            if goal is not None and previous is not None and goal.id == previous.id and goal.revision != previous.revision + 1:
                raise WorkflowError("goal_revision_conflict")
            self._set(goal=goal)
            return goal
