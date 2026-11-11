"""Goal continuation and recovered transcripts cannot reset task accounting."""

from copy import deepcopy
from decimal import Decimal

import pytest

from henchman.agents.orchestrator import Orchestrator
from henchman.config.schema import Settings
from henchman.core.goals import GoalService
from henchman.core.run_budget import BudgetControlError, BudgetExceeded, RequestEstimate
from henchman.core.session_data import Session
from henchman.core.session_run_accounting import SessionRunAccounting
from henchman.providers.usage import UsageReport
from tests.agents.test_agent_budget_scope import AccountingProvider


@pytest.mark.parametrize("currency", ["USD", "EUR"])
def test_durable_resume_recaptures_future_prices_without_repricing_consumption_or_limits(tmp_path, currency):
    original_price = {
        "provider": "test", "model": "test-model", "input_per_1k": "1",
        "output_per_1k": "1", "cache_read_per_1k": "1", "cache_write_per_1k": "1",
        "source": "original-catalog", "as_of": "2026-11-06",
    }
    settings = Settings.model_validate({"usage": {
        "persistence": "durable", "limits": {"max_cost": "0.1"}, "prices": [original_price],
    }})
    session = Session("session", "project", "today", "today")
    path = tmp_path / "ops.db"
    runtime = SessionRunAccounting(settings, lambda: session, lambda _: None, path)
    scope = runtime.begin(AccountingProvider())
    price = scope.pricing_resolver("test", "test-model")
    first = scope.ledger.reserve(RequestEstimate(10, 10, price), provider="test", model="test-model")
    assert scope.ledger.start(first.request_id)
    usage = UsageReport(prompt_tokens=10, completion_tokens=2, source="reported")
    scope.ledger.reconcile(first.request_id, usage, final=True)

    replacement = Settings.model_validate({"usage": {
        "persistence": "durable", "limits": {"max_cost": "100", "currency": currency},
        "prices": [{**original_price, "input_per_1k": "2", "output_per_1k": "2",
                    "cache_read_per_1k": "2", "cache_write_per_1k": "2", "currency": currency,
                    "source": "replacement-catalog", "as_of": "2026-11-07"}],
    }})
    runtime.settings = replacement
    assert runtime.begin(AccountingProvider()).pricing_resolver("test", "test-model") == price
    restored_session = Session.from_dict(session.to_dict())
    restored = SessionRunAccounting(replacement, lambda: restored_session, lambda _: None, path)
    resumed = restored.begin(AccountingProvider())
    assert resumed.ledger.run_id == scope.ledger.run_id
    snapshot = resumed.ledger.snapshot()
    assert snapshot.limits.max_cost == Decimal("0.1")
    assert snapshot.limits.currency == "USD"
    assert snapshot.remaining_cost == Decimal("0.088")
    assert snapshot.records[0].estimate.pricing == price
    current_price = resumed.pricing_resolver("test", "test-model")
    assert current_price.source == "replacement-catalog"
    assert current_price.currency == currency
    if currency == "EUR":
        with pytest.raises(BudgetExceeded, match="currency_mismatch"):
            resumed.ledger.reserve(RequestEstimate(10, 10, current_price))
        assert resumed.ledger.snapshot().consumed_requests == 1
        assert resumed.ledger.snapshot().money[0].settled_estimated_cost == Decimal("0.012")
    else:
        second = resumed.ledger.reserve(RequestEstimate(10, 10, current_price), provider="test", model="test-model")
        assert resumed.ledger.start(second.request_id)
        resumed.ledger.reconcile(second.request_id, usage, final=True)
        resumed.ledger.reconcile(first.request_id, usage, final=True)
        snapshot = resumed.ledger.snapshot()
        assert snapshot.remaining_cost == Decimal("0.064")
        assert snapshot.consumed_requests == 2
        assert [(record.estimate.pricing.source, record.estimate.pricing.as_of, record.accounted_cost)
                for record in snapshot.records] == [
            ("original-catalog", "2026-11-06", Decimal("0.012")),
            ("replacement-catalog", "2026-11-07", Decimal("0.024")),
        ]
        with pytest.raises(BudgetExceeded, match="money_limit"):
            resumed.ledger.reserve(RequestEstimate(1, 100, current_price))


def runtime(tmp_path, *, durable=False, session=None):
    session = session or Session("session", "project", "today", "today")
    settings = Settings(usage={"persistence": "durable" if durable else "process", "limits": {"max_requests": 1}})
    provider = AccountingProvider()
    orchestrator = Orchestrator(provider, settings=settings)
    saved = []
    orchestrator.accounting_runtime = SessionRunAccounting(
        settings, lambda: session, lambda current: saved.append(current.to_dict()), tmp_path / "ops.db",
    )
    return orchestrator, session, saved


@pytest.mark.parametrize("durable", [False, True])
async def test_active_and_paused_goal_reuses_its_budget(tmp_path, durable):
    orchestrator, session, _ = runtime(tmp_path, durable=durable)
    goals = GoalService()
    goals.start(session, "finish the task")
    _ = [event async for event in orchestrator.run("first")]
    original = orchestrator.last_budget_scope
    goals.pause(session)
    goals.resume(session)
    with pytest.raises(BudgetExceeded, match="request_limit"):
        _ = [event async for event in orchestrator.run("continue")]
    assert orchestrator.last_budget_scope is original
    assert orchestrator.default_provider.calls == 1


@pytest.mark.parametrize("durable", [False, True])
async def test_explicit_new_goal_gets_a_new_budget_in_same_runtime(tmp_path, durable):
    orchestrator, session, _ = runtime(tmp_path, durable=durable)
    goals = GoalService()
    goals.start(session, "first task")
    _ = [event async for event in orchestrator.run("first")]
    original = orchestrator.last_budget_scope
    orchestrator.accounting_runtime.apply_user_goal_transition(
        session, update=lambda: goals.start(session, "second task"), save=lambda: None,
    )
    _ = [event async for event in orchestrator.run("second")]
    assert orchestrator.last_budget_scope.ledger.run_id != original.ledger.run_id
    assert orchestrator.default_provider.calls == 2


async def test_backup_without_reference_recovers_authoritative_active_budget(tmp_path):
    orchestrator, session, saved = runtime(tmp_path, durable=True)
    GoalService().start(session, "task")
    backup = deepcopy(session)
    _ = [event async for event in orchestrator.run("first")]
    assert saved and saved[0]["accounting"]["active_run_id"]
    restored, _, _ = runtime(tmp_path, durable=True, session=backup)
    with pytest.raises(BudgetExceeded, match="request_limit"):
        _ = [event async for event in restored.run("resume")]
    assert restored.default_provider.calls == 0


async def test_recovered_goal_mismatch_cannot_authorize_fresh_budget(tmp_path):
    orchestrator, session, _ = runtime(tmp_path, durable=True)
    GoalService().start(session, "task")
    _ = [event async for event in orchestrator.run("first")]
    restored_session = deepcopy(session)
    GoalService().start(restored_session, "different identity in recovered JSON")
    restored, _, _ = runtime(tmp_path, durable=True, session=restored_session)
    with pytest.raises(BudgetControlError, match="identity"):
        _ = [event async for event in restored.run("resume")]
    assert restored.default_provider.calls == 0


async def test_successful_ordinary_turns_keep_history_but_start_new_runs(tmp_path):
    orchestrator, session, _ = runtime(tmp_path, durable=True)
    _ = [event async for event in orchestrator.run("first")]
    first = orchestrator.last_budget_scope.ledger.run_id
    _ = [event async for event in orchestrator.run("second")]
    second = orchestrator.last_budget_scope.ledger.run_id
    assert session.accounting.active_run_id is None
    assert session.accounting.run_ids == (first, second)


async def test_failed_session_save_prevents_dispatch_and_retains_binding(tmp_path):
    orchestrator, session, _ = runtime(tmp_path, durable=True)
    GoalService().start(session, "task")

    def fail(_session):
        raise OSError("disk write failed")

    orchestrator.accounting_runtime.save_session = fail
    with pytest.raises(BudgetControlError, match="session_save"):
        _ = [event async for event in orchestrator.run("first")]
    assert orchestrator.default_provider.calls == 0
    assert orchestrator.accounting_runtime.store.session_binding("project", "session").active_run_id


async def test_backup_and_process_setting_cannot_bypass_existing_durable_goal(tmp_path):
    orchestrator, session, _ = runtime(tmp_path, durable=True)
    GoalService().start(session, "original task")
    backup = deepcopy(session)
    _ = [event async for event in orchestrator.run("spend the request")]
    original_run = orchestrator.last_budget_scope.ledger.run_id
    restored, _, _ = runtime(tmp_path, durable=False, session=backup)
    with pytest.raises(BudgetExceeded, match="request_limit"):
        _ = [event async for event in restored.run("resume the same task")]
    assert restored.default_provider.calls == 0
    assert restored.last_budget_scope.ledger.run_id == original_run


async def test_failed_close_reference_save_does_not_reuse_a_closed_ledger(tmp_path):
    orchestrator, _session, saved = runtime(tmp_path, durable=True)
    save_calls = 0

    def fail_once_on_close(session):
        nonlocal save_calls
        save_calls += 1
        if save_calls == 2:
            raise OSError("close reference save failed once")
        saved.append(session.to_dict())

    orchestrator.accounting_runtime.save_session = fail_once_on_close
    with pytest.raises(BudgetControlError, match="session_save_failed"):
        _ = [event async for event in orchestrator.run("first completed task")]
    original_run = orchestrator.last_budget_scope.ledger.run_id
    _ = [event async for event in orchestrator.run("next task after storage recovers")]
    assert orchestrator.default_provider.calls == 2
    assert orchestrator.last_budget_scope.ledger.run_id != original_run


@pytest.mark.parametrize("durable", [False, True])
async def test_restored_turn_to_goal_mismatch_never_becomes_an_explicit_new_goal(tmp_path, durable):
    from henchman.core.events import EventType

    orchestrator, session, _ = runtime(tmp_path, durable=durable)
    stream = orchestrator.run("ordinary turn interrupted after dispatch")
    async for event in stream:
        if event.type == EventType.CONTENT:
            break
    await stream.aclose()
    original = orchestrator.last_budget_scope
    restored = deepcopy(session)
    GoalService().start(restored, "goal present only in the recovered transcript")
    orchestrator.accounting_runtime.current_session = lambda: restored
    for _ in range(2):
        with pytest.raises(BudgetControlError, match="identity"):
            _ = [event async for event in orchestrator.run("retry without changing the restored goal")]
    assert orchestrator.default_provider.calls == 1
    assert orchestrator.last_budget_scope is None
    assert original.ledger.snapshot().consumed_requests == 1


async def test_fresh_controller_cannot_promote_restored_turn_owner_to_goal(tmp_path):
    from henchman.core.events import EventType

    orchestrator, session, _ = runtime(tmp_path, durable=True)
    stream = orchestrator.run("interrupted ordinary task")
    async for event in stream:
        if event.type == EventType.CONTENT:
            break
    await stream.aclose()
    restored = deepcopy(session)
    GoalService().start(restored, "goal present only in recovered state")
    replacement, _, _ = runtime(tmp_path, durable=True, session=restored)
    for _ in range(2):
        with pytest.raises(BudgetControlError, match="identity"):
            _ = [event async for event in replacement.run("same unchanged restored goal")]
    assert replacement.default_provider.calls == 0


async def test_ambiguous_close_commit_does_not_cache_a_closed_run(tmp_path):
    orchestrator, _, _ = runtime(tmp_path, durable=True)
    store = orchestrator.accounting_runtime.store
    failures = 0

    def lose_close_acknowledgement(name):
        nonlocal failures
        if name == "finish_run:after_commit" and failures == 0:
            failures += 1
            raise OSError("lost acknowledgement after close committed")

    store._checkpoint = lose_close_acknowledgement
    with pytest.raises(BudgetControlError, match="store_unavailable"):
        _ = [event async for event in orchestrator.run("completed before acknowledgement failed")]
    old_run = orchestrator.last_budget_scope.ledger.run_id
    _ = [event async for event in orchestrator.run("new ordinary task after recovery")]
    assert orchestrator.default_provider.calls == 2
    assert orchestrator.last_budget_scope.ledger.run_id != old_run


@pytest.mark.parametrize("reference_present", [False, True])
async def test_cached_process_scope_cannot_ignore_new_durable_authority(tmp_path, reference_present):
    process, session, _ = runtime(tmp_path, durable=False)
    GoalService().start(session, "shared session task")
    original = process.accounting_runtime.begin(process.default_provider)
    durable, stored_session, _ = runtime(tmp_path, durable=True, session=deepcopy(session))
    _ = [event async for event in durable.run("consume the authoritative request")]
    restored = deepcopy(stored_session)
    if not reference_present:
        restored.accounting = None
    process.accounting_runtime.current_session = lambda: restored
    with pytest.raises(BudgetControlError, match="conflict"):
        _ = [event async for event in process.run("reload without resetting known accounting")]
    assert process.default_provider.calls == 0
    assert original.ledger.snapshot().consumed_requests == 0
    assert durable.last_budget_scope.ledger.snapshot().consumed_requests == 1


@pytest.mark.parametrize("clear", [False, True])
async def test_trusted_user_transition_replaces_restored_goal_once(tmp_path, clear):
    first, session, _ = runtime(tmp_path, durable=True)
    goals = GoalService()
    goals.start(session, "old goal")
    _ = [event async for event in first.run("use original budget")]
    old_run = first.last_budget_scope.ledger.run_id
    restored_session = deepcopy(session)
    restored, _, _ = runtime(tmp_path, durable=True, session=restored_session)
    controller = restored.accounting_runtime
    update = (lambda: goals.clear(restored_session)) if clear else (lambda: goals.start(restored_session, "new goal"))
    controller.apply_user_goal_transition(restored_session, update=update, save=lambda: None)
    assert controller.store.session_binding("project", "session").active_run_id == old_run
    _ = [event async for event in restored.run("explicit new task")]
    assert restored.last_budget_scope.ledger.run_id != old_run
    assert first.last_budget_scope.ledger.snapshot().consumed_requests == 1
    if not clear:
        with pytest.raises(BudgetExceeded, match="request_limit"):
            _ = [event async for event in restored.run("continue without another user action")]
        assert restored.default_provider.calls == 1


async def test_saved_goal_without_runtime_permission_cannot_replace_old_run(tmp_path):
    original, session, _ = runtime(tmp_path, durable=True)
    goals = GoalService()
    goals.start(session, "old")
    _ = [event async for event in original.run("spent")]
    controller = original.accounting_runtime
    controller.apply_user_goal_transition(session, update=lambda: goals.start(session, "new"), save=lambda: None)
    # Simulate termination after the goal save but before begin consumes permission.
    recovered, _, _ = runtime(tmp_path, durable=True, session=deepcopy(session))
    with pytest.raises(BudgetControlError, match="identity"):
        _ = [event async for event in recovered.run("resume only the saved JSON")]
    assert recovered.default_provider.calls == 0
    assert controller.store.session_binding("project", "session").active_run_id == original.last_budget_scope.ledger.run_id


@pytest.mark.parametrize("failure", ["update", "save"])
async def test_failed_user_transition_rolls_back_goal_and_keeps_consumption(tmp_path, failure):
    orchestrator, session, _ = runtime(tmp_path, durable=True)
    goals = GoalService()
    old_goal = goals.start(session, "old")
    _ = [event async for event in orchestrator.run("spent")]
    original = orchestrator.last_budget_scope

    def update():
        goals.start(session, "must not become authorized")
        if failure == "update":
            raise ValueError("invalid update")

    def save():
        raise OSError("save failed")

    with pytest.raises((ValueError, BudgetControlError)):
        orchestrator.accounting_runtime.apply_user_goal_transition(session, update=update, save=save)
    assert goals.get(session) == old_goal
    with pytest.raises(BudgetExceeded):
        _ = [event async for event in orchestrator.run("continue original task")]
    assert original.ledger.snapshot().consumed_requests == 1
    assert orchestrator.default_provider.calls == 1


async def test_pending_transition_rejects_concurrent_new_authority_without_closing_it(tmp_path):
    orchestrator, session, _ = runtime(tmp_path, durable=True)
    goals = GoalService()
    goals.start(session, "old")
    _ = [event async for event in orchestrator.run("spent")]
    controller = orchestrator.accounting_runtime
    old_run = orchestrator.last_budget_scope.ledger.run_id
    controller.apply_user_goal_transition(session, update=lambda: goals.start(session, "requested"), save=lambda: None)
    controller.store.finish_run(old_run)
    competing = controller.store.create_run(run_id="concurrent", project_hash="project", session_id="session", owner_key="goal:other")
    for _ in range(2):
        with pytest.raises(BudgetControlError):
            _ = [event async for event in orchestrator.run("consume stale transition")]
    assert controller.store.session_binding("project", "session").active_run_id == competing.run_id
    assert orchestrator.default_provider.calls == 1


async def test_same_object_goal_metadata_change_does_not_authorize_new_budget(tmp_path):
    orchestrator, session, _ = runtime(tmp_path, durable=True)
    goals = GoalService()
    goals.start(session, "old")
    _ = [event async for event in orchestrator.run("spent")]
    goals.start(session, "metadata alone")
    with pytest.raises(BudgetControlError, match="identity"):
        _ = [event async for event in orchestrator.run("unauthorized replacement")]
    assert orchestrator.default_provider.calls == 1


async def test_transition_rechecks_concurrent_binding_between_validation_and_close(tmp_path, monkeypatch):
    from henchman.ops.run_budget_store import RunBudgetStore

    orchestrator, session, _ = runtime(tmp_path, durable=True)
    goals = GoalService()
    goals.start(session, "old")
    _ = [event async for event in orchestrator.run("spent")]
    controller = orchestrator.accounting_runtime
    controller.apply_user_goal_transition(session, update=lambda: goals.start(session, "requested"), save=lambda: None)
    original_finish = controller.store.finish_run

    def replace_before_close(run_id):
        other = RunBudgetStore(tmp_path / "ops.db")
        other.finish_run(run_id)
        other.create_run(run_id="racing-run", project_hash="project", session_id="session", owner_key="goal:racer")
        original_finish(run_id)

    monkeypatch.setattr(controller.store, "finish_run", replace_before_close)
    with pytest.raises(BudgetControlError, match="conflict"):
        _ = [event async for event in orchestrator.run("race after validation")]
    assert controller.store.session_binding("project", "session").active_run_id == "racing-run"
    assert orchestrator.default_provider.calls == 1


async def test_mismatched_requested_goal_consumes_permission_without_closing_authority(tmp_path):
    orchestrator, session, _ = runtime(tmp_path, durable=True)
    goals = GoalService()
    goals.start(session, "old")
    _ = [event async for event in orchestrator.run("spent")]
    original_run = orchestrator.last_budget_scope.ledger.run_id
    controller = orchestrator.accounting_runtime
    controller.apply_user_goal_transition(session, update=lambda: goals.start(session, "requested"), save=lambda: None)
    requested = deepcopy(session.export_metadata["goal"])
    goals.start(session, "changed without a user command")
    with pytest.raises(BudgetControlError, match="conflict"):
        _ = [event async for event in orchestrator.run("mismatched goal")]
    session.export_metadata["goal"] = requested
    with pytest.raises(BudgetControlError, match="identity"):
        _ = [event async for event in orchestrator.run("try to replay spent permission")]
    assert controller.store.session_binding("project", "session").active_run_id == original_run
    assert orchestrator.default_provider.calls == 1
