"""Session workflow ownership and explicit user recovery, shared by frontends."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from threading import Event
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
    WorkflowReference,
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


@dataclass(frozen=True)
class QueueControlView:
    """Ephemeral user-control snapshot, never a persisted dispatch permit."""

    report: WorkflowReport
    eligible: tuple[tuple[str, int], ...]
    active_input_id: str | None
    busy: bool
    _runtime: object = field(repr=False)
    _session: Session = field(repr=False)
    _reference: WorkflowReference | None = field(repr=False)
    _generation: int


@dataclass
class _Binding:
    session: Session
    journal: Journal
    eligible: dict[str, int] = field(default_factory=dict)
    goal_enabled: bool = False
    active: InputPermit | None = None
    failure: str | None = None
    live_text: dict[str, str] = field(default_factory=dict)
    live_roles: dict[str, str] = field(default_factory=dict)
    live_goal: WorkflowGoal | None = None
    live_identity: object = field(default_factory=object)


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
        self._queue_generation = 0
        self._queue_control_busy = False

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
            # Only the original executable objective belongs to the live cache.
            # A losing compare-and-swap may share the winner's revision, so its
            # proposed checks, policy or lifecycle must never shadow authority.
            return saved.model_copy(update={"objective": live.objective, "availability": live.availability})
        if saved is not None:
            objective = binding.session.evidence_redactor.text(saved.objective)
            if objective != saved.objective:
                return saved.model_copy(update={
                    "objective": objective, "availability": "redacted",
                    "objective_sha256": saved.objective_sha256 or hashlib.sha256(saved.objective.encode()).hexdigest(),
                })
        return saved

    @staticmethod
    def _input_role(binding: _Binding, item: QueuedInput) -> str | None:
        live = binding.live_roles.get(item.id)
        if live is not None and item.owner_id == binding.journal.owner_id:
            return live
        if not item.role_available or (item.role is not None and binding.session.evidence_redactor.text(item.role) != item.role):
            raise WorkflowError("input_payload_unavailable")
        return item.role

    @staticmethod
    def _goal_permission(binding: _Binding, goal: WorkflowGoal | None) -> bool:
        live = binding.live_goal
        return bool(binding.goal_enabled and live is not None and goal is not None
                    and (live.id, live.revision) == (goal.id, goal.revision))

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
        self._queue_generation += 1
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
                cached.live_identity = object()
                cached.eligible.clear()
                cached.goal_enabled = False
                cached.live_text.clear()
                cached.live_roles.clear()
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
            self._queue_generation += 1
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
                                  binding is None or not self._goal_permission(binding, state.goal) or binding.failure is not None
                                  or state.goal.policy != self._policy(session)),
                              binding.failure if binding is not None else None)

    def queue_view(self) -> QueueControlView:
        """Read current evidence and local eligibility without creating authority."""
        session, generation = self._session(), self._queue_generation
        reference = session.workflow
        report = self.report()
        binding = self._bindings.get(self._key(session))
        eligible: tuple[tuple[str, int], ...] = ()
        active = None
        if binding is not None and binding.session is session:
            eligible = tuple((item.id, item.revision) for item in report.state.inputs
                             if item.state == "queued" and binding.eligible.get(item.id) == item.revision)
            active = binding.active.input_id if binding.active is not None else None
        if (generation != self._queue_generation or self.current() is not session or session.workflow != reference
            or self._key(session) != (report.state.project_hash, report.state.session_id)):
            raise WorkflowError("queue_controls_changed")
        return QueueControlView(report, eligible, active, self._queue_control_busy, self, session, reference, generation)

    async def control_queue(self, view: QueueControlView, input_id: str, revision: int,
                            action: Literal["send", "edit", "drop", "move"], *,
                            text: str | None = None, position: int | None = None,
                            guard: Callable[[], None] | None = None) -> QueuedInput:
        """Apply one explicit user decision, joining serialized storage on cancellation.

        Only the transaction runs off-loop. Revocation is checked after obtaining
        the storage lock and before commit, and again before local dispatch is
        armed. A commit already completed remains real evidence but stays held.
        """
        if (view._runtime is not self or view._generation != self._queue_generation
            or self._session() is not view._session or view._session.workflow_runtime is not self
            or self._key(view._session) != (view.report.state.project_hash, view.report.state.session_id)
            or view._session.workflow != view._reference):
            raise WorkflowError("queue_controls_changed")
        if self._queue_control_busy:
            raise WorkflowError("queue_control_busy")
        if action not in {"send", "edit", "drop", "move"}:
            raise WorkflowError("invalid_queue_action")
        binding = self._bindings.get(self._key(view._session))
        if binding is None or binding.session is not view._session:
            raise WorkflowError("queue_controls_changed")
        if guard is not None:
            guard()
        self._queue_control_busy = True
        self._queue_generation += 1
        generation = self._queue_generation
        live_identity = binding.live_identity
        revoked = Event()
        # No existing permission may dispatch this item during its transaction.
        binding.eligible.pop(input_id, None)

        def admitted() -> None:
            if (revoked.is_set() or generation != self._queue_generation
                or self._session() is not view._session or binding.session is not view._session
                or view._session.workflow_runtime is not self
                or self._key(view._session) != (view.report.state.project_hash, view.report.state.session_id)
                or view._session.workflow != view._reference):
                raise WorkflowError("queue_controls_changed")
            if guard is not None:
                guard()

        def change(journal: WorkflowJournal) -> QueuedInput:
            admitted()
            if journal.snapshot().revision != view.report.state.revision:
                raise WorkflowError("revision_conflict")
            if action == "send":
                current = journal._find(input_id, revision)
                self._input_role(binding, current)
                return journal.transfer_queued(input_id, revision, live_text=binding.live_text.get(input_id))
            if action == "edit":
                if text is None:
                    raise WorkflowError("invalid_input_text")
                return journal.edit(input_id, revision, text)
            if action == "move":
                if position is None:
                    raise WorkflowError("invalid_queue_position")
                return journal.move(input_id, revision, position)
            return journal.drop(input_id, revision)

        def transaction() -> QueuedInput:
            journal = binding.journal
            if isinstance(journal, StoredWorkflow):
                return journal._call("queue_control", change, guard=admitted)
            with journal._lock:
                snapshot = journal.snapshot()
                staged = WorkflowJournal(snapshot.project_hash, snapshot.session_id,
                                         owner_id=journal.owner_id, state=snapshot, redactor=journal.redactor)
                result = change(staged)
                admitted()
                journal.state = staged.state
                return result

        worker = asyncio.create_task(asyncio.to_thread(transaction))
        cancelled: asyncio.CancelledError | None = None
        primary: BaseException | None = None
        try:
            while not worker.done():
                try:
                    await asyncio.shield(worker)
                except asyncio.CancelledError as error:
                    cancelled = cancelled or error
                    revoked.set()
                except BaseException:
                    break
            if cancelled is not None:
                try:
                    committed = worker.result()
                except BaseException:
                    cancelled.add_note("Queue storage settled without granting dispatch permission")
                else:
                    if (action == "edit" and text is not None and binding.live_identity is live_identity
                        and binding.session is view._session and committed.text_sha256 == hashlib.sha256(text.encode()).hexdigest()):
                        # Keep the user's actual committed replacement only in
                        # the original live binding; cancellation grants nothing.
                        binding.live_text[input_id] = text
                raise cancelled
            result = worker.result()
            admitted()
            if action == "edit":
                assert text is not None
                binding.live_text[input_id] = text
            elif action == "drop":
                binding.live_text.pop(input_id, None)
                binding.live_roles.pop(input_id, None)
            self._save(binding)
            admitted()
            if action == "send":
                binding.eligible[input_id] = result.revision
            return result
        except BaseException as error:
            primary = error
            raise
        finally:
            revoked.set()
            # Any shifted records also lose stale permissions. Reconcile raw
            # caches after interrupted or uncertain commits without replay.
            try:
                state = binding.journal.snapshot()
                records = {item.id: item for item in state.inputs}
                binding.eligible = {key: value for key, value in binding.eligible.items()
                                    if key in records and records[key].state == "queued" and records[key].revision == value}
                binding.live_text = {key: value for key, value in binding.live_text.items()
                                     if key in records and records[key].text_sha256 == hashlib.sha256(value.encode()).hexdigest()}
            except Exception as cleanup:
                binding.eligible.clear()
                binding.live_text.clear()
                if primary is None:
                    raise
                primary.add_note(f"Queue cache reconciliation also failed: {type(cleanup).__name__}")
            finally:
                self._queue_control_busy = False

    def submit(self, text: str, *, kind: InputKind = "message", role: str | None = None) -> QueuedInput:
        binding = self._binding()
        if binding.failure is not None:
            raise WorkflowError(binding.failure)
        item = binding.journal.enqueue(text, kind=kind, role=role)
        binding.live_text[item.id] = text
        if role is not None:
            binding.live_roles[item.id] = role
        self._save(binding)
        if not self.report().blocking_input_ids:
            binding.eligible[item.id] = item.revision
        return item

    def send(self, input_id: str, revision: int) -> QueuedInput:
        binding = self._binding()
        current = next((item for item in binding.journal.snapshot().inputs
                        if item.id == input_id and item.revision == revision), None)
        if current is not None:
            self._input_role(binding, current)
        item = binding.journal.transfer_queued(input_id, revision, live_text=binding.live_text.get(input_id))
        self._save(binding)
        binding.eligible[item.id] = item.revision
        return item

    def submit_goal(self) -> QueuedInput | None:
        from henchman.core.goals import GoalService

        binding = self._binding()
        text = GoalService().continuation_prompt(binding.session)
        goal = self.goal()
        if text is None or goal is None:
            return None
        item = binding.journal.enqueue(text, kind="goal", goal_id=goal.id, goal_revision=goal.revision)
        binding.live_text[item.id] = text
        self._save(binding)
        binding.eligible[item.id] = item.revision
        return item

    def has_ready_input(self) -> bool:
        binding = self._binding()
        if binding.failure is not None or self.report().blocking_input_ids:
            return False
        goal = binding.journal.snapshot().goal
        return any(binding.eligible.get(item.id) == item.revision and item.state == "queued"
                   and (item.kind != "goal" or (goal is not None and self.goal_continuation_allowed()
                                                and (goal.id, goal.revision) == (item.goal_id, item.goal_revision)))
                   for item in binding.journal.snapshot().inputs)

    def edit(self, input_id: str, revision: int, text: str) -> QueuedInput:
        binding = self._binding()
        item = binding.journal.edit(input_id, revision, text)
        binding.eligible.pop(input_id, None)
        binding.live_text[input_id] = text
        self._save(binding)
        return item

    def drop(self, input_id: str, revision: int) -> QueuedInput:
        binding = self._binding()
        item = binding.journal.drop(input_id, revision)
        binding.eligible.pop(input_id, None)
        binding.live_text.pop(input_id, None)
        binding.live_roles.pop(input_id, None)
        self._save(binding)
        return item

    def move(self, input_id: str, revision: int, position: int) -> QueuedInput:
        binding = self._binding()
        item = binding.journal.move(input_id, revision, position)
        binding.eligible.pop(input_id, None)
        # Reordering never grants a new revision permission to execute. This
        # also prevents a concurrent external edit from inheriting a grant.
        binding.eligible = {record.id: record.revision for record in binding.journal.snapshot().inputs
                            if binding.eligible.get(record.id) == record.revision and record.state == "queued"}
        self._save(binding)
        return item

    def hold_pending(self) -> None:
        """Disarm continuation immediately; retain live ownership until joined."""
        self._queue_generation += 1
        for binding in self._bindings.values():
            binding.eligible.clear()
            binding.goal_enabled = False

    def next_input(self) -> WorkflowDispatch | None:
        binding = self._binding()
        if binding.active is not None or binding.failure is not None or self.report().blocking_input_ids:
            return None
        for item in sorted(binding.journal.snapshot().inputs, key=lambda item: item.order):
            if binding.eligible.get(item.id) != item.revision:
                continue
            if item.kind == "goal":
                goal = binding.journal.snapshot().goal
                if goal is None or not self.goal_continuation_allowed() or (goal.id, goal.revision) != (item.goal_id, item.goal_revision):
                    binding.eligible.pop(item.id, None)
                    continue
            binding.eligible.pop(item.id)
            text = binding.live_text.get(item.id, item.text)
            try:
                role = self._input_role(binding, item)
                permit = binding.journal.claim(item.id, item.revision, live_text=binding.live_text.get(item.id))
            except BaseException:
                binding.eligible.clear()
                binding.goal_enabled = False
                raise
            binding.active = permit
            assert text is not None
            return WorkflowDispatch(permit, text, item.kind, role)
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
            binding.live_roles.pop(dispatch.permit.input_id, None)

    def correlate(self, dispatch: WorkflowDispatch, session: Session, *, budget_run_id: str | None = None,
                  operation_run_id: str | None = None, operation_id: str | None = None) -> None:
        """Link original work, even after settlement; never authorize dispatch.

        Background tasks retain their original session and claim. Selection of
        another frontend session does not reassign or revoke that evidence.
        Persistence failure prevents the calling run or operation from starting.
        """
        if os.getpid() != self._origin_pid:
            raise WorkflowError("process_authority_changed")
        key = (dispatch.permit.project_hash, dispatch.permit.session_id)
        binding = self._bindings.get(key)
        if self._key(session) != key or binding is None or binding.session is not session:
            raise WorkflowError("session_identity_mismatch")
        if binding.failure is not None:
            raise WorkflowError(binding.failure)
        binding.journal.correlate(dispatch.permit, budget_run_id=budget_run_id,
                                  operation_run_id=operation_run_id, operation_id=operation_id)
        self._save(binding)

    def interrupt(self) -> None:
        """Settle only after the frontend has cancelled and joined actual work."""
        self._queue_generation += 1
        session = self._session()
        binding = self._bindings.get(self._key(session))
        if binding is None or binding.session is not session:
            raise WorkflowError("session_identity_mismatch")
        binding.eligible.clear()
        binding.goal_enabled = False
        try:
            if binding.active is not None:
                item = next(item for item in binding.journal.snapshot().inputs if item.id == binding.active.input_id)
                binding.journal.cancel(item.id, item.revision)
            self._save(binding)
        except BaseException:
            if binding.failure is None:
                binding.failure = "interruption_settlement_failed"
            raise
        finally:
            # Actual work is joined even if authority could not be written.
            # report() then classifies the unacknowledged start as uncertain.
            binding.active = None

    def abandon(self, input_id: str, revision: int, note: str) -> QueuedInput:
        binding = self._binding()
        current = next((item for item in binding.journal.snapshot().inputs if item.id == input_id), None)
        if current is not None and current.state == "started" and current.owner_id == binding.journal.owner_id and binding.active is None:
            if type(revision) is not int or current.revision != revision:
                raise WorkflowError("revision_conflict")
            if not isinstance(note, str) or not note.strip():
                raise WorkflowError("invalid_resolution")
            current = binding.journal.cancel(input_id, revision)
            revision = current.revision
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
        return bool(goal is not None and goal.status == "active" and goal.availability == "complete"
                    and self._goal_permission(binding, goal)
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

    def pause_goal(self) -> WorkflowGoal:
        binding = self._binding()
        state = binding.journal.snapshot()
        goal = self._goal_value(binding, state)
        if goal is None or goal.status == "complete":
            raise WorkflowError("goal_not_pausable")
        updated = goal.model_copy(update={"revision": goal.revision + 1, "status": "paused"})
        self._set_goal(binding, updated, expected_revision=state.revision)
        return updated

    def clear_goal(self) -> None:
        binding = self._binding()
        self._set_goal(binding, None, expected_revision=binding.journal.snapshot().revision)

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
        enabled = self._goal_permission(binding, goal)
        self._set_goal(binding, updated, expected_revision=state.revision)
        binding.goal_enabled = enabled
        return updated

    def unbind_plan(self, plan_id: str) -> WorkflowGoal:
        binding = self._binding()
        state = binding.journal.snapshot()
        goal = self._goal_value(binding, state)
        if goal is None or not any(item.plan_id == plan_id for item in goal.checks):
            raise WorkflowError("goal_check_not_bound")
        updated = goal.model_copy(update={"revision": goal.revision + 1,
                                          "checks": tuple(item for item in goal.checks if item.plan_id != plan_id)})
        enabled = self._goal_permission(binding, goal)
        self._set_goal(binding, updated, expected_revision=state.revision)
        binding.goal_enabled = enabled
        return updated

    def acknowledge_goal(self) -> WorkflowGoal:
        """Record explicit user completion; it is not configured-check proof."""
        binding = self._binding()
        state = binding.journal.snapshot()
        goal = self._goal_value(binding, state)
        if goal is None:
            raise WorkflowError("goal_not_set")
        updated = goal.model_copy(update={"revision": goal.revision + 1, "status": "complete",
                                          "completion_summary": "Completed by user", "completion_source": "user"})
        self._set_goal(binding, updated, expected_revision=state.revision)
        return updated

    def complete_goal(self, goal_id: str, revision: int, summary: str) -> WorkflowGoal:
        binding = self._binding()
        state = binding.journal.snapshot()
        goal = self._goal_value(binding, state)
        if goal is None or goal.id != goal_id or type(revision) is not int or goal.revision != revision:
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
                                               "status": "complete", "completion_summary": summary.strip(), "completion_source": "model"})
        self._set_goal(binding, updated, expected_revision=state.revision)
        binding.goal_enabled = False
        return updated
