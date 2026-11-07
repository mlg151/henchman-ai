"""Session workflow ownership and explicit user recovery, shared by frontends."""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal
from uuid import uuid4

from henchman.config.schema import Settings
from henchman.core.session_data import Session
from henchman.core.workflow_state import (
    GoalCheckReference,
    GoalPolicy,
    InputKind,
    InputOutcome,
    InputPermit,
    QueuedInput,
    WorkflowError,
    WorkflowGoal,
    WorkflowJournal,
    WorkflowState,
)
from henchman.ops.workflow_store import StoredWorkflow, WorkflowStore

Journal = WorkflowJournal | StoredWorkflow


@dataclass(frozen=True)
class WorkflowDispatch:
    permit: InputPermit
    text: str
    kind: InputKind
    role: str | None


@dataclass(frozen=True)
class WorkflowReport:
    state: WorkflowState
    persistence: Literal["process", "durable"]
    blocking_input_ids: tuple[str, ...]
    goal_requires_resume: bool
    failure_reason: str | None = None


@dataclass
class _Binding:
    session: Session
    journal: Journal
    eligible: dict[str, int] = field(default_factory=dict)
    goal_enabled: bool = False
    active: InputPermit | None = None
    failure: str | None = None
    live_text: dict[str, str] = field(default_factory=dict)
    live_goal: WorkflowGoal | None = None


class SessionWorkflow:
    """Keep dispatch eligibility in memory and prior authority outside backups.

    ``send``, goal lifecycle and check-binding methods are trusted user adapters.
    Restored state never invokes them. Tool completion uses the separate matching
    goal revision method; it cannot resume goals or arm queued inputs.
    """

    def __init__(self, settings: Settings, current: Callable[[], Session | None],
                 save_session: Callable[[Session], None], path: Path,
                 *, check_status: Callable[[str], dict[str, object]] | None = None) -> None:
        self.settings = settings
        self.current = current
        self.save_session = save_session
        self.path = Path(path)
        self.check_status = check_status
        self._origin_pid = os.getpid()
        self._bindings: dict[tuple[str, str], _Binding] = {}

    def _session(self) -> Session:
        if os.getpid() != self._origin_pid:
            raise WorkflowError("process_authority_changed")
        session = self.current()
        if session is None:
            raise WorkflowError("workflow_session_required")
        return session

    @staticmethod
    def _key(session: Session) -> tuple[str, str]:
        return session.project_hash, session.id

    def _policy(self, session: Session) -> GoalPolicy:
        tools = json.dumps(self.settings.tools.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        provenance = session.export_metadata.get("instruction_sources")
        digest = provenance.get("digest") if isinstance(provenance, dict) else None
        return GoalPolicy.model_validate({"plan_mode": session.plan_mode, "plan_mode_origin": session.plan_mode_origin,
                                          "tool_policy_digest": hashlib.sha256(tools.encode()).hexdigest(), "instruction_digest": digest})

    @staticmethod
    def _goal_value(binding: _Binding, state: WorkflowState) -> WorkflowGoal | None:
        live, saved = binding.live_goal, state.goal
        if live is not None and saved is not None and (live.id, live.revision, live.objective_sha256) == (saved.id, saved.revision, saved.objective_sha256):
            return live
        return saved

    @classmethod
    def _publish(cls, binding: _Binding) -> None:
        state = binding.journal.snapshot()
        if isinstance(binding.journal, StoredWorkflow):
            binding.session.workflow = binding.journal.reference
        goal = cls._goal_value(binding, state)
        if goal is None:
            binding.session.export_metadata.pop("goal", None)
        else:
            binding.session.export_metadata["goal"] = goal.model_dump(mode="json")

    def attach(self, session: Session, *, restored: bool = True) -> None:
        """Select current authority; recovered eligibility is always empty."""
        if self._session() is not session:
            raise WorkflowError("session_changed")
        key = self._key(session)
        existing = WorkflowStore.existing_reference(self.path, *key, reference=session.workflow)
        cached = self._bindings.get(key)
        if any(binding.active is not None and binding.session is not session for binding in self._bindings.values()):
            raise WorkflowError("workflow_dispatch_active")
        if cached is not None:
            if isinstance(cached.journal, StoredWorkflow):
                if existing != cached.journal.reference:
                    raise WorkflowError("missing_or_changed_workflow_store")
            elif existing is not None or session.workflow is not None:
                raise WorkflowError("durable_workflow_conflict")
            if cached.session is not session or restored:
                cached.eligible.clear()
                cached.goal_enabled = False
                cached.live_text.clear()
                cached.live_goal = None
            cached.session = session
            binding = cached
        else:
            journal: Journal
            if existing is not None or self.settings.operations.persistence == "durable":
                store = WorkflowStore(self.path, expected_store_id=existing.store_id if existing else None,
                                      redactor=session.evidence_redactor)
                journal = store.open_session(*key, create=existing is None)
            else:
                journal = WorkflowJournal(*key, redactor=session.evidence_redactor)
            binding = _Binding(session, journal)
            self._bindings[key] = binding
            if existing is None and (raw := session.export_metadata.get("goal")) is not None:
                if not isinstance(raw, dict):
                    raise WorkflowError("invalid_legacy_goal")
                try:
                    goal = WorkflowGoal.model_validate_json(json.dumps({**raw, "policy": raw.get("policy", self._policy(session).model_dump())}))
                except (TypeError, ValueError) as exc:
                    raise WorkflowError("invalid_legacy_goal") from exc
                journal.set_goal(goal, expected_revision=journal.snapshot().revision)
        session._workflow_runtime = self
        self._publish(binding)

    def _binding(self) -> _Binding:
        session = self._session()
        key = self._key(session)
        if key not in self._bindings or self._bindings[key].session is not session:
            self.attach(session)
        binding = self._bindings[key]
        existing = WorkflowStore.existing_reference(self.path, *key, reference=session.workflow)
        if isinstance(binding.journal, StoredWorkflow):
            if existing != binding.journal.reference:
                raise WorkflowError("missing_or_changed_workflow_store")
        elif existing is not None:
            raise WorkflowError("durable_workflow_conflict")
        return binding

    def _save(self, binding: _Binding) -> None:
        self._publish(binding)
        try:
            self.save_session(binding.session)
        except Exception as exc:
            self.mark_save_failed(binding.session)
            raise WorkflowError("session_save_failed") from exc
        binding.failure = None

    def mark_save_failed(self, session: Session) -> None:
        """A committed workflow change outlives a failed advisory transcript save."""
        binding = self._bindings.get(self._key(session))
        if binding is not None:
            binding.failure = "session_save_failed"
            binding.eligible.clear()
            binding.goal_enabled = False
            self._publish(binding)

    def has_active_dispatch(self) -> bool:
        """Report actual locally held input ownership without I/O."""
        return any(binding.active is not None for binding in self._bindings.values())

    def report(self) -> WorkflowReport:
        """Inspect without creating a store, binding or dispatch permission."""
        session = self._session()
        key = self._key(session)
        binding = self._bindings.get(key)
        state = WorkflowStore.inspect(self.path, *key, reference=session.workflow)
        durable = state is not None
        if binding is not None:
            if durable != isinstance(binding.journal, StoredWorkflow):
                raise WorkflowError("workflow_authority_conflict")
            state = binding.journal.report()
            state = state.model_copy(update={"inputs": tuple(
                item.model_copy(update={"state": "outcome_unknown"})
                if item.state == "started" and (binding.active is None or item.claim_id != binding.active.claim_id)
                else item for item in state.inputs)})
        elif state is None:
            state = WorkflowState(project_hash=session.project_hash, session_id=session.id)
        else:
            state = WorkflowJournal(*key, state=state, redactor=session.evidence_redactor).report()
        blocking = tuple(item.id for item in state.inputs if item.state == "outcome_unknown" and item.resolution is None)
        return WorkflowReport(state, "durable" if durable else "process", blocking,
                              state.goal is not None and state.goal.status == "active" and (
                                  binding is None or not binding.goal_enabled or binding.failure is not None
                                  or state.goal.policy != self._policy(session)),
                              binding.failure if binding is not None else None)

    def submit(self, text: str, *, kind: InputKind = "message", role: str | None = None) -> QueuedInput:
        binding = self._binding()
        if binding.failure is not None:
            raise WorkflowError(binding.failure)
        item = binding.journal.enqueue(text, kind=kind, role=role)
        binding.live_text[item.id] = text
        self._save(binding)
        if not self.report().blocking_input_ids:
            binding.eligible[item.id] = item.revision
        return item

    def send(self, input_id: str, revision: int) -> QueuedInput:
        binding = self._binding()
        item = binding.journal.transfer_queued(input_id, revision, live_text=binding.live_text.get(input_id))
        self._save(binding)
        binding.eligible[item.id] = item.revision
        return item

    def next_input(self) -> WorkflowDispatch | None:
        binding = self._binding()
        if binding.active is not None or binding.failure is not None or self.report().blocking_input_ids:
            return None
        for item in sorted(binding.journal.snapshot().inputs, key=lambda item: item.order):
            if binding.eligible.get(item.id) != item.revision:
                continue
            binding.eligible.pop(item.id)
            text = binding.live_text.get(item.id, item.text)
            try:
                permit = binding.journal.claim(item.id, item.revision, live_text=binding.live_text.get(item.id))
            except BaseException:
                binding.eligible.clear()
                binding.goal_enabled = False
                raise
            binding.active = permit
            assert text is not None
            return WorkflowDispatch(permit, text, item.kind, item.role)
        return None

    def finish(self, dispatch: WorkflowDispatch, *, outcome: InputOutcome) -> None:
        key = (dispatch.permit.project_hash, dispatch.permit.session_id)
        binding = self._bindings.get(key)
        if binding is None or binding.active != dispatch.permit:
            raise WorkflowError("input_owner_changed")
        try:
            binding.journal.finish(dispatch.permit, outcome=outcome)
            self._save(binding)
        except BaseException:
            binding.eligible.clear()
            binding.goal_enabled = False
            raise
        finally:
            binding.active = None
            binding.live_text.pop(dispatch.permit.input_id, None)

    def interrupt(self) -> None:
        binding = self._binding()
        binding.eligible.clear()
        binding.goal_enabled = False
        if binding.active is not None:
            item = next(item for item in binding.journal.snapshot().inputs if item.id == binding.active.input_id)
            binding.journal.cancel(item.id, item.revision)
            binding.active = None
        self._save(binding)

    def abandon(self, input_id: str, revision: int, note: str) -> QueuedInput:
        binding = self._binding()
        item = binding.journal.abandon(input_id, revision, note)
        self._save(binding)
        return item

    def goal(self) -> WorkflowGoal | None:
        binding = self._binding()
        return self._goal_value(binding, binding.journal.snapshot())

    def _set_goal(self, binding: _Binding, goal: WorkflowGoal | None, *, expected_revision: int) -> WorkflowGoal | None:
        binding.goal_enabled = False
        binding.live_goal = goal
        binding.journal.set_goal(goal, expected_revision=expected_revision)
        self._save(binding)
        return goal

    def start_goal(self, objective: str) -> WorkflowGoal:
        binding = self._binding()
        revision = binding.journal.snapshot().revision
        goal = WorkflowGoal(id=uuid4().hex, objective=objective.strip(), policy=self._policy(binding.session),
                            objective_sha256=hashlib.sha256(objective.strip().encode()).hexdigest())
        self._set_goal(binding, goal, expected_revision=revision)
        binding.goal_enabled = True
        return goal

    def goal_continuation_allowed(self) -> bool:
        binding = self._binding()
        goal = self._goal_value(binding, binding.journal.snapshot())
        return bool(goal is not None and goal.status == "active" and binding.goal_enabled
                    and binding.failure is None and not self.report().blocking_input_ids
                    and goal.policy == self._policy(binding.session))

    def resume_goal(self, *, accept_policy_change: bool = False) -> WorkflowGoal:
        binding = self._binding()
        state = binding.journal.snapshot()
        goal = self._goal_value(binding, state)
        if goal is None or goal.status == "complete":
            raise WorkflowError("goal_not_resumable")
        if goal.availability != "complete":
            raise WorkflowError("goal_payload_unavailable")
        policy = self._policy(binding.session)
        if goal.policy != policy and not accept_policy_change:
            raise WorkflowError("goal_policy_changed")
        updated = goal.model_copy(update={"revision": goal.revision + 1, "status": "active", "policy": policy})
        self._set_goal(binding, updated, expected_revision=state.revision)
        binding.goal_enabled = True
        return updated

    def bind_plan(self, plan_id: str) -> WorkflowGoal:
        binding = self._binding()
        state = binding.journal.snapshot()
        goal = self._goal_value(binding, state)
        if goal is None or self.check_status is None:
            raise WorkflowError("goal_check_runtime_unavailable")
        status = self.check_status(plan_id)
        reference = GoalCheckReference.model_validate({"plan_id": plan_id, "spec_digest": status.get("spec_digest"),
                                                       "observed_run_id": status.get("run_id")})
        checks = tuple(item for item in goal.checks if item.plan_id != plan_id) + (reference,)
        updated = WorkflowGoal.model_validate({**goal.model_dump(), "revision": goal.revision + 1, "checks": checks})
        enabled = binding.goal_enabled
        self._set_goal(binding, updated, expected_revision=state.revision)
        binding.goal_enabled = enabled
        return updated

    def complete_goal(self, goal_id: str, revision: int, summary: str) -> WorkflowGoal:
        binding = self._binding()
        state = binding.journal.snapshot()
        goal = self._goal_value(binding, state)
        if goal is None or goal.id != goal_id or goal.revision != revision:
            raise WorkflowError("goal_revision_conflict")
        if not self.goal_continuation_allowed():
            raise WorkflowError("goal_not_active")
        for reference in goal.checks:
            if self.check_status is None:
                raise WorkflowError("goal_check_runtime_unavailable")
            status = self.check_status(reference.plan_id)
            if status.get("spec_digest") != reference.spec_digest or status.get("current_checks_passed") is not True:
                raise WorkflowError("goal_checks_unverified")
        updated = WorkflowGoal.model_validate({**goal.model_dump(), "revision": goal.revision + 1,
                                               "status": "complete", "completion_summary": summary.strip()})
        self._set_goal(binding, updated, expected_revision=state.revision)
        binding.goal_enabled = False
        return updated
