"""Read shared task usage without inventing prices or provider billing."""

from __future__ import annotations

from collections import Counter
from decimal import Decimal

from rich.table import Table
from rich.text import Text

from henchman.cli.commands import Command, CommandContext
from henchman.cli.evidence import runtime_evidence_redactor
from henchman.core.run_budget import BudgetControlError
from henchman.core.usage_summary import summarize_usage
from henchman.providers.runtime_budget import RunBudgetScope


def _remaining(value: int | float | Decimal | None, limit: int | float | Decimal | None) -> str:
    if limit is None:
        return "unlimited"
    return "unavailable" if value is None else f"{value} remaining of {limit}"


def _amount(currency: str, value: Decimal | None) -> str:
    return "unavailable" if value is None else f"{currency} {value}"


class UsageCommand(Command):
    """Inspect one shared run, including its delegates and retained holds."""

    @property
    def name(self) -> str:
        return "usage"

    @property
    def description(self) -> str:
        return "Show shared task usage, remaining budgets and cost provenance"

    @property
    def usage(self) -> str:
        return "/usage"

    async def execute(self, ctx: CommandContext) -> None:
        from henchman.core.session_run_accounting import SessionRunAccounting

        if ctx.args:
            ctx.console.print(f"Usage: {self.usage}", markup=False)
            return
        runtime = ctx.repl if ctx.repl is not None else ctx
        policy = runtime_evidence_redactor(runtime)
        orchestrator = getattr(runtime, "orchestrator", None)
        if orchestrator is None:
            orchestrator = getattr(getattr(runtime, "core_context", None), "orchestrator", None)
        scope = getattr(orchestrator, "last_budget_scope", None)
        try:
            accounting = getattr(orchestrator, "accounting_runtime", None)
            if isinstance(accounting, SessionRunAccounting):
                snapshot = accounting.usage_snapshot(ctx.session)
            else:
                snapshot = scope.ledger.snapshot() if isinstance(scope, RunBudgetScope) else None
        except BudgetControlError as exc:
            ctx.console.print(policy.text(f"Accounting unavailable: {exc}"), markup=False, highlight=False)
            return
        if snapshot is None:
            ctx.console.print("No run accounting is available.", markup=False)
            return
        table = Table(title="Task usage (all agents)", show_header=False, box=None)

        def row(label: str, value: str) -> None:
            table.add_row(Text(label), Text(policy.text(value)))

        row("Run", snapshot.run_id)
        row("Accounting", snapshot.accounting_lifetime + (
            " — retained for this process only" if snapshot.accounting_lifetime == "process" else " — persistent"
        ))
        row("Requests", f"{snapshot.consumed_requests} dispatched, {snapshot.reserved_requests} reserved; "
            + _remaining(snapshot.remaining_requests, snapshot.limits.max_requests))
        row("Task tokens", f"{snapshot.settled_tokens} settled, {snapshot.held_tokens} held; "
            + _remaining(snapshot.remaining_tokens, snapshot.limits.max_tokens))
        row("Time", f"{snapshot.elapsed_seconds:.1f}s elapsed; "
            + _remaining(snapshot.remaining_seconds, snapshot.limits.max_seconds))
        row("Money limit", _remaining(snapshot.remaining_cost, snapshot.limits.max_cost)
            + (f" {snapshot.limits.currency}" if snapshot.limits.max_cost is not None else ""))
        row("Uncertain usage", f"{snapshot.unknown_dispatched_requests} dispatched requests")
        if not snapshot.money:
            row("Estimated cost", "unavailable")
            row("Reported billing", "unavailable")
        for money in snapshot.money:
            row("Estimated cost", _amount(money.currency, money.settled_estimated_cost))
            row("Held estimate", _amount(money.currency, money.held_cost))
            row("Reported billing", _amount(money.currency, money.reported_cost))
        actors = Counter(record.agent_id or "unattributed" for record in snapshot.records if record.dispatched)
        for actor, count in sorted(actors.items()):
            row("Agent requests", f"{actor}: {count}")
        for summary in summarize_usage(snapshot):
            model = f"{summary.provider or 'unknown provider'}/{summary.model or 'unknown model'}"
            total = summary.counts["total_tokens"]
            observed = "tokens unavailable" if total is None else f"{total} observed tokens"
            coverage = f"{summary.counted_requests['total_tokens']}/{summary.dispatched_requests} requests have totals"
            row("Model usage", f"{model} — {summary.usage_source}: {observed}; {coverage}; "
                f"{summary.settled_requests} settled")
            price = summary.pricing
            if price is None:
                row("Price source", f"{model}: unavailable")
            else:
                row("Price source", f"{model}: {price.source} ({price.as_of or 'date unavailable'}); {price.currency}")
                rates = ", ".join(
                    f"{label} {getattr(price, name) if getattr(price, name) is not None else 'unavailable'}"
                    for label, name in (("input", "input_per_1k"), ("output", "output_per_1k"),
                                        ("cache read", "cache_read_per_1k"), ("cache write", "cache_write_per_1k"))
                )
                row("Configured rates", f"per 1,000 tokens: {rates}")
        if snapshot.stop_reason or snapshot.accounting_error:
            row("Accounting stop", snapshot.accounting_error or snapshot.stop_reason or "")
        ctx.console.print(table)
