"""Terminal budget reporting keeps unknown, estimated and billed values distinct."""

import re
from decimal import Decimal
from io import StringIO
from types import SimpleNamespace

import pytest
from rich.console import Console

from henchman.cli.commands import CommandContext
from henchman.cli.commands.builtins import get_builtin_commands
from henchman.config.schema import Settings
from henchman.core.run_budget import BudgetLimits, ReportedCost, RequestEstimate, RunBudgetLedger
from henchman.providers.runtime_budget import RunBudgetScope
from henchman.providers.usage import TokenPricing, UsageReport


async def render(ledger=None, *, textual=False, settings=None):
    output = StringIO()
    orchestrator = SimpleNamespace(last_budget_scope=RunBudgetScope(ledger) if ledger else None)
    runtime = SimpleNamespace(settings=settings or Settings())
    if textual:
        runtime.core_context = SimpleNamespace(orchestrator=orchestrator)
    else:
        runtime.orchestrator = orchestrator
    command = next(command for command in get_builtin_commands() if command.name == "usage")
    await command.execute(CommandContext(console=Console(file=output, width=160), repl=runtime))
    return output.getvalue()


async def test_no_run_is_unavailable_rather_than_zero_cost():
    text = await render()
    assert "No run accounting" in text
    assert "0.00" not in text


@pytest.mark.parametrize("textual", [False, True])
async def test_shared_remaining_limits_and_unknown_cost_are_visible(textual):
    ledger = RunBudgetLedger(limits=BudgetLimits(max_requests=3, max_tokens=100))
    request = ledger.reserve(RequestEstimate(10, 10), agent_id="child")
    ledger.start(request.request_id)
    ledger.reconcile(request.request_id, UsageReport(total_tokens=12, source="reported"), final=True)
    text = await render(ledger, textual=textual)
    assert "process" in text
    assert "Requests" in text and "2 remaining" in text
    assert "88 remaining" in text
    assert "unavailable" in text
    assert "child" in text


async def test_zero_price_is_valid_but_unreported_billing_remains_unavailable():
    ledger = RunBudgetLedger(limits=BudgetLimits(max_cost=Decimal(0)))
    pricing = TokenPricing(0, 0, 0, 0, source="explicit catalog", as_of="2026-11-07")
    request = ledger.reserve(RequestEstimate(10, 10, pricing))
    ledger.start(request.request_id)
    ledger.reconcile(request.request_id, UsageReport(prompt_tokens=10, completion_tokens=2, source="reported"), final=True)
    text = await render(ledger)
    assert re.search(r"Estimated cost\s+USD 0\s", text)
    assert re.search(r"Reported billing\s+unavailable", text)
    assert "explicit catalog" in text and "2026-11-07" in text


async def test_reported_currencies_stay_separate_and_evidence_is_redacted():
    ledger = RunBudgetLedger()
    request = ledger.reserve(RequestEstimate(10, 10), agent_id="private-canary", provider="local", model="fixture")
    ledger.start(request.request_id)
    ledger.reconcile(request.request_id, reported_cost=ReportedCost(Decimal("0.1"), "USD"))
    ledger.reconcile(request.request_id, reported_cost=ReportedCost(Decimal("0.2"), "EUR"))
    settings = Settings(providers={"deepseek": {"api_key": "private-canary"}})
    text = await render(ledger, settings=settings)
    assert "USD 0.1" in text and "EUR 0.2" in text
    assert "0.3" not in text
    assert "private-canary" not in text
    assert "[REDACTED]" in text


async def selected_usage(orchestrator, session):
    output = StringIO()
    runtime = SimpleNamespace(orchestrator=orchestrator, settings=orchestrator.settings)
    command = next(command for command in get_builtin_commands() if command.name == "usage")
    await command.execute(CommandContext(console=Console(file=output, width=160), repl=runtime, session=session))
    return output.getvalue()


async def test_switching_sessions_cannot_display_previous_task_budget(tmp_path):
    from henchman.core.goals import GoalService
    from henchman.core.session_data import Session
    from tests.core.test_session_run_accounting import runtime

    orchestrator, session, _ = runtime(tmp_path, durable=True)
    GoalService().start(session, "old session task")
    _ = [event async for event in orchestrator.run("spent")]
    previous = orchestrator.last_budget_scope.ledger.run_id
    selected = Session("new-session", "project", "now", "now")
    orchestrator.accounting_runtime.current_session = lambda: selected
    output = await selected_usage(orchestrator, selected)
    assert previous not in output
    assert "No run accounting" in output


@pytest.mark.parametrize("completed", [False, True])
async def test_durable_session_usage_is_available_before_resumed_dispatch(tmp_path, completed):
    from copy import deepcopy

    from henchman.core.goals import GoalService
    from tests.core.test_session_run_accounting import runtime

    old, session, _ = runtime(tmp_path, durable=True)
    if not completed:
        GoalService().start(session, "active task")
    _ = [event async for event in old.run("spent")]
    run_id = old.last_budget_scope.ledger.run_id
    restored_session = deepcopy(session)
    restored, _, _ = runtime(tmp_path, durable=True, session=restored_session)
    before = (tmp_path / "ops.db").read_bytes()
    output = await selected_usage(restored, restored_session)
    assert run_id in output and "1 dispatched" in output
    assert restored.default_provider.calls == 0
    assert restored.last_budget_scope is None
    assert not restored.accounting_runtime._active
    assert (tmp_path / "ops.db").read_bytes() == before


async def test_completed_process_usage_remains_scoped_to_its_session(tmp_path):
    from tests.core.test_session_run_accounting import runtime

    orchestrator, session, _ = runtime(tmp_path)
    _ = [event async for event in orchestrator.run("completed")]
    assert "1 dispatched" in await selected_usage(orchestrator, session)
    assert not (tmp_path / "ops.db").exists()


async def test_usage_does_not_consume_pending_user_goal_authorization(tmp_path):
    from henchman.core.goals import GoalService
    from tests.core.test_session_run_accounting import runtime

    orchestrator, session, _ = runtime(tmp_path, durable=True)
    goals = GoalService()
    goals.start(session, "old goal")
    _ = [event async for event in orchestrator.run("spent")]
    old_run = orchestrator.last_budget_scope.ledger.run_id
    controller = orchestrator.accounting_runtime
    controller.apply_user_goal_transition(session, update=lambda: goals.start(session, "new goal"), save=lambda: None)
    before = (tmp_path / "ops.db").read_bytes()
    assert old_run in await selected_usage(orchestrator, session)
    assert (tmp_path / "ops.db").read_bytes() == before
    assert controller.store.session_binding("project", "session").active_run_id == old_run
    _ = [event async for event in orchestrator.run("consume still-valid user authorization")]
    assert orchestrator.default_provider.calls == 2


async def test_usage_reports_referenced_storage_failure_without_previous_totals(tmp_path):
    from tests.core.test_session_run_accounting import runtime

    orchestrator, session, _ = runtime(tmp_path, durable=True)
    _ = [event async for event in orchestrator.run("completed")]
    (tmp_path / "ops.db").unlink()
    output = await selected_usage(orchestrator, session)
    assert "Accounting unavailable" in output
    assert "1 dispatched" not in output
    assert not (tmp_path / "ops.db").exists()
