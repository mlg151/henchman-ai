"""Own accounting across public turns, goal continuation and session recovery."""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass, replace
from pathlib import Path
from uuid import uuid4

from henchman.config.schema import Settings
from henchman.config.usage import model_pricing
from henchman.core.goals import GoalService
from henchman.core.run_accounting import new_run_budget
from henchman.core.run_budget import BudgetAccountingError, BudgetSnapshot
from henchman.core.session_data import Session, SessionAccountingReference
from henchman.ops.run_budget_store import RunBudgetStore
from henchman.providers.base import ModelProvider
from henchman.providers.runtime_budget import RunBudgetScope


@dataclass
class _ActiveRun:
    session: Session
    owner_key: str
    scope: RunBudgetScope
    durable: bool


@dataclass(frozen=True)
class _GoalTransition:
    """Single-use authority captured by a user command, never session evidence."""

    store_id: str | None
    expected_run_id: str | None
    expected_owner_key: str | None
    requested_owner_key: str | None
    durable: bool


class SessionRunAccounting:
    """Retain one active task budget per session; the database owns durable state.

    Successful ordinary turns end their run. Goals, interrupted turns and live
    background work retain it. A user changing a goal in this process creates a
    new task through an explicit command hook; goal metadata cannot reset state.
    """

    def __init__(
        self, settings: Settings, current_session: Callable[[], Session | None],
        save_session: Callable[[Session], None], store_path: Path,
    ) -> None:
        self.settings = settings
        self.current_session = current_session
        self.save_session = save_session
        self.store_path = store_path
        self._store: RunBudgetStore | None = None
        self._active: dict[tuple[str, str], _ActiveRun] = {}
        self._last_scopes: dict[tuple[str, str], RunBudgetScope] = {}
        self._goal_transitions: dict[tuple[str, str], _GoalTransition] = {}

    @property
    def store(self) -> RunBudgetStore:
        """Open only when durable accounting is requested or already referenced."""
        if self._store is None:
            self._store = RunBudgetStore(self.store_path)
        return self._store

    @staticmethod
    def _goal_owner(session: Session) -> str | None:
        goal = GoalService().get(session)
        return f"goal:{goal.id}" if goal is not None and goal.status != "complete" else None

    def _save_reference(self, session: Session) -> None:
        session.accounting = self._binding(session)
        try:
            self.save_session(session)
        except Exception as exc:
            raise BudgetAccountingError("session_save_failed") from exc

    def _binding(self, session: Session) -> SessionAccountingReference:
        """Validate advisory references against the independent accounting store."""
        reference = session.accounting
        if reference is not None and not self.store_path.exists():
            raise BudgetAccountingError("missing_accounting_store")
        binding = self.store.session_binding(session.project_hash, session.id)
        if reference is not None and (
            reference.store_id != binding.store_id
            or not set(reference.run_ids).issubset(binding.run_ids)
        ):
            raise BudgetAccountingError("session_accounting_identity_mismatch")
        return binding

    @staticmethod
    def _owner_mismatch(owner: str, goal_owner: str | None) -> bool:
        return owner != goal_owner and (goal_owner is not None or owner.startswith("goal:"))

    def apply_user_goal_transition(
        self, session: Session, *, update: Callable[[], None], save: Callable[[], None],
    ) -> None:
        """Save an explicit user replacement/clear and arm one runtime transition.

        Only user command handlers call this method. Goal state and model goal
        completion never grant this authority. A failed update/save restores
        the prior in-memory goal and grants no permission; a process exit after
        saving loses the permission and requires the user to repeat the action.
        """
        if self.current_session() is not session:
            raise BudgetAccountingError("session_changed")
        key = (session.project_hash, session.id)
        self._goal_transitions.pop(key, None)
        active = self._active.get(key)
        binding = None
        durable = self.settings.usage.persistence == "durable" or session.accounting is not None
        if durable or self.store_path.exists() or (active is not None and active.durable):
            binding = self._binding(session)
            durable = durable or binding.active_run_id is not None
        if active is not None and not active.durable and (durable or (binding is not None and binding.active_run_id is not None)):
            raise BudgetAccountingError("durable_accounting_conflict")
        if durable:
            assert binding is not None
            expected_run = binding.active_run_id
            expected_owner = binding.active_owner_key
        else:
            expected_run = active.scope.ledger.run_id if active is not None else None
            expected_owner = active.owner_key if active is not None else None
        previous = deepcopy(session.export_metadata.get("goal"))
        present = "goal" in session.export_metadata
        saving = False
        try:
            update()
            requested_owner = self._goal_owner(session)
            saving = True
            save()
        except BaseException as exc:
            if present:
                session.export_metadata["goal"] = previous
            else:
                session.export_metadata.pop("goal", None)
            if saving and isinstance(exc, Exception):
                raise BudgetAccountingError("session_save_failed") from exc
            raise
        self._goal_transitions[key] = _GoalTransition(
            binding.store_id if binding is not None else None,
            expected_run, expected_owner, requested_owner, durable,
        )

    def _consume_goal_transition(
        self, session: Session, transition: _GoalTransition,
        binding: SessionAccountingReference | None,
    ) -> SessionAccountingReference | None:
        """Revalidate captured authority, closing only the exact authorized run."""
        key = (session.project_hash, session.id)
        if self._goal_owner(session) != transition.requested_owner_key:
            raise BudgetAccountingError("goal_transition_conflict")
        if (binding.store_id if binding is not None else None) != transition.store_id:
            raise BudgetAccountingError("goal_transition_conflict")
        if transition.durable:
            binding = self._binding(session)
            if (binding.active_run_id, binding.active_owner_key) != (transition.expected_run_id, transition.expected_owner_key):
                raise BudgetAccountingError("goal_transition_conflict")
            if transition.expected_run_id is not None:
                # Concurrent replacement cannot be closed here: finish_run names
                # the captured immutable ID, and create_run rejects a new active
                # binding that appears between these independent transactions.
                self.store.finish_run(transition.expected_run_id)
            binding = self._binding(session)
            if binding.active_run_id is not None:
                raise BudgetAccountingError("goal_transition_conflict")
            self._active.pop(key, None)
            self._save_reference(session)
        else:
            active = self._active.get(key)
            actual = (active.scope.ledger.run_id, active.owner_key) if active is not None else (None, None)
            if actual != (transition.expected_run_id, transition.expected_owner_key) or (binding is not None and binding.active_run_id is not None):
                raise BudgetAccountingError("goal_transition_conflict")
            self._active.pop(key, None)
        return binding

    def _close(self, key: tuple[str, str], active: _ActiveRun) -> None:
        if active.durable:
            self.store.finish_run(active.scope.ledger.run_id)
            # The committed close is authoritative even if saving its advisory
            # transcript reference fails. Never hand out that closed scope again.
            self._active.pop(key, None)
            self._save_reference(active.session)
        else:
            self._active.pop(key, None)

    def usage_snapshot(self, session: Session | None = None) -> BudgetSnapshot | None:
        """Inspect the selected session without beginning or authorizing a run."""
        session = session if session is not None else self.current_session()
        if session is None:
            return None
        key = (session.project_hash, session.id)
        inspection = RunBudgetStore.inspect_session(
            self.store_path, *key, reference=session.accounting,
        )
        active = self._active.get(key)
        if inspection is not None and inspection.snapshot is not None:
            if active is not None and not active.durable:
                raise BudgetAccountingError("durable_accounting_conflict")
            return inspection.snapshot
        scope = self._last_scopes.get(key)
        return scope.ledger.snapshot() if scope is not None else None

    def begin(self, provider: ModelProvider) -> RunBudgetScope | None:
        """Bind before dispatch, consulting durable identity even for old backups."""
        session = self.current_session()
        if session is None:
            if self.settings.usage.persistence == "durable":
                raise BudgetAccountingError("durable_accounting_requires_session")
            return new_run_budget(self.settings, provider)
        key = (session.project_hash, session.id)
        transition = self._goal_transitions.pop(key, None)
        goal_owner = self._goal_owner(session)
        active = self._active.get(key)
        binding = None
        if session.accounting is not None or self.store_path.exists() or (active is not None and active.durable):
            binding = self._binding(session)
        if transition is not None:
            binding = self._consume_goal_transition(session, transition, binding)
            active = self._active.get(key)
        if active is not None and binding is not None:
            if active.durable and binding.active_run_id != active.scope.ledger.run_id:
                # A close can commit even when its acknowledgement fails. The
                # next call must recover current authority, not return a stale
                # cached handle to an already closed or superseded run.
                self._active.pop(key, None)
                active = None
            elif not active.durable and (binding.active_run_id is not None or session.accounting is not None):
                # There is no safe way to merge the cached process consumption
                # with a newly discovered durable run or imported references.
                raise BudgetAccountingError("durable_accounting_conflict")
        if active is not None:
            if self._owner_mismatch(active.owner_key, goal_owner):
                raise BudgetAccountingError("goal_accounting_identity_mismatch")
            active.session = session
            if active.durable:
                self._save_reference(session)
            return active.scope

        durable = self.settings.usage.persistence == "durable" or session.accounting is not None
        if not durable and binding is not None:
            # A backup can predate its JSON reference. Changing settings to
            # process accounting cannot erase existing database authority.
            durable = binding.active_run_id is not None
        scope = new_run_budget(self.settings, provider)
        owner = goal_owner or f"turn:{uuid4().hex}"
        if durable:
            binding = binding or self._binding(session)
            if binding.active_run_id is not None:
                ledger = self.store.resume_run(
                    binding.active_run_id, store_id=binding.store_id,
                    project_hash=session.project_hash, session_id=session.id,
                )
                owner = ledger.owner_key or "turn:recovered"
                if self._owner_mismatch(owner, goal_owner):
                    raise BudgetAccountingError("goal_accounting_identity_mismatch")
            elif scope is not None:
                ledger = self.store.create_run(
                    limits=scope.ledger.limits, project_hash=session.project_hash,
                    session_id=session.id, owner_key=owner,
                )
            else:
                return None
            if scope is None:
                captured = self.settings.model_copy(deep=True)
                scope = RunBudgetScope(ledger, pricing_resolver=lambda provider, model: model_pricing(
                    captured, provider=provider, model=model,
                ))
            else:
                scope = replace(scope, ledger=ledger)
        if scope is None:
            return None
        self._active[key] = _ActiveRun(session, owner, scope, durable)
        self._last_scopes[key] = scope
        if durable:
            self._save_reference(session)
        return scope

    def finish(self, scope: RunBudgetScope | None, *, completed: bool, background_active: bool) -> None:
        """Close only a successful finished task; interrupted work keeps its holds."""
        if scope is None or not completed or background_active:
            return
        for key, active in tuple(self._active.items()):
            if active.scope is not scope:
                continue
            if self._goal_owner(active.session) == active.owner_key:
                return
            self._close(key, active)
            return
