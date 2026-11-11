"""Read-only, session-scoped context and accounting inspection for Textual."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from copy import deepcopy
from dataclasses import dataclass, fields, is_dataclass, replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, ClassVar

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static, TextArea

from henchman.cli.inspection_runtime import (
    _agent as _agent,
)
from henchman.cli.inspection_runtime import (
    _binding as _binding,
)
from henchman.cli.inspection_runtime import (
    _current_policy as _current_policy,
)
from henchman.cli.inspection_runtime import (
    _joined as _joined,
)
from henchman.cli.inspection_runtime import (
    _model as _model,
)
from henchman.cli.inspection_runtime import (
    _provider_name as _provider_name,
)
from henchman.core.run_budget import BudgetSnapshot
from henchman.core.session_context import SessionContextService
from henchman.core.session_data import Session
from henchman.core.session_manager import SessionManager
from henchman.core.session_run_accounting import SessionRunAccounting
from henchman.core.usage_summary import summarize_usage
from henchman.utils.evidence_redaction import EvidenceRedactor, EvidenceStreamRedactor

_INPUT_BYTES = 2 * 1024 * 1024
_INPUT_NODES = 25000
_TEXT_BYTES = 65536
_DETAIL_ROWS = 128
_USAGE_RECORDS = 4096


def _check_size(value: Any) -> None:
    """Bound copying/tokenization before traversing arbitrary retained evidence."""
    remaining, nodes = _INPUT_BYTES, _INPUT_NODES

    def visit(item: Any, depth: int = 0) -> None:
        nonlocal remaining, nodes
        nodes -= 1
        if nodes < 0 or depth > 24:
            raise ValueError("inspection size limit")
        if isinstance(item, str):
            if len(item) > remaining:
                raise ValueError("inspection size limit")
            remaining -= len(item.encode("utf-8"))
        elif item is None or type(item) in (bool, int, float):
            remaining -= 16
        elif isinstance(item, (list, tuple, dict)):
            if len(item) > nodes:
                raise ValueError("inspection size limit")
            for key in item:
                visit(key, depth + 1)
                if isinstance(item, dict):
                    visit(item[key], depth + 1)
        elif is_dataclass(item) and not isinstance(item, type):
            for field in fields(item):
                visit(getattr(item, field.name), depth + 1)
        else:
            raise ValueError("unsupported session evidence")
        if remaining < 0:
            raise ValueError("inspection size limit")

    visit(value)


@dataclass(frozen=True)
class ContextCapture:
    """Detached selected-session evidence, with no execution authority."""

    binding: tuple[Any, ...]
    captured_at: str
    metadata: tuple[str, ...]
    session: Session | None
    manager: SessionManager | None
    accounting: SessionRunAccounting | None
    retention_error: str | None
    policy: EvidenceRedactor


@dataclass(frozen=True)
class ContextInspection:
    """Only allowlisted human-readable metadata crosses into the screen."""

    captured_at: str
    read_completed_at: str
    sections: dict[str, str]
    omitted: frozenset[str]


class _Rows:
    """Retain whole bounded evidence rows; never store a clipped credential."""

    def __init__(self, policy: EvidenceRedactor) -> None:
        self.policy = policy
        self.rows: list[str] = []
        self.size = 0
        self.omitted = False

    def append(self, row: str) -> None:
        if self.omitted:
            return
        row = self.policy.text(row)
        size = len(row.encode("utf-8")) + 1
        if len(self.rows) >= _DETAIL_ROWS or self.size + size > _TEXT_BYTES - 128:
            self.omitted = True
            return
        self.rows.append(row)
        self.size += size

    def extend(self, rows: Any) -> None:
        for row in rows:
            self.append(row)

    def text(self) -> str:
        return "\n".join(self.rows)


def _value(value: Any) -> str:
    return str(value) if isinstance(value, (str, int, float, Decimal)) and not isinstance(value, bool) else "unavailable"


def capture_context(runtime: Any) -> ContextCapture:
    """Detach a bounded current session on its event loop, without selecting one."""
    context = getattr(runtime, "core_context", None)
    repl = getattr(context, "session_manager", None)
    manager = getattr(repl, "session_manager", None)
    session = getattr(repl, "current", None)
    agent = _agent(runtime)
    provider = getattr(agent, "provider", None)
    policy = _current_policy(runtime)

    def label(value: Any) -> str:
        text = policy.text(_value(value))
        return text if len(text.encode("utf-8")) <= 8192 else "[Metadata omitted: display limit]"

    model = _model(provider)
    root = getattr(context, "project_root", None)
    metadata = (
        f"Provider: {label(_provider_name(provider))}", f"Model: {label(model)}",
        "Current provider selection; Usage names models observed on actual requests.",
        f"Project: {label(str(root) if isinstance(root, Path) else None)}",
        f"Request capacity: {_value(getattr(agent, 'context_window', None))} tokens",
        f"Conversation budget: {_value(getattr(agent, 'max_tokens', None))} tokens",
        "Capacity is configured, not a measurement of the next provider request.",
        f"Autosave: {'on' if getattr(repl, 'auto_save', None) is True else 'off' if getattr(repl, 'auto_save', None) is False else 'unavailable'}",
        "Disk save acknowledgement: unavailable; this is the current in-memory session.",
        "The composer draft is not part of this session snapshot.",
    )
    detached = None
    retention_error = None
    accounting = getattr(getattr(context, "orchestrator", None), "accounting_runtime", None)
    if not isinstance(session, Session) or not isinstance(manager, SessionManager) or not isinstance(root, Path):
        retention_error = "No selected project session is available."
    elif session.project_hash != manager.compute_project_hash(root):
        retention_error = "Selected session does not belong to this runtime project."
    else:
        # Accounting needs only immutable identity/reference fields. Never use a
        # global last-run fallback which might belong to a previously selected session.
        detached = Session(session.id, session.project_hash, session.started, session.last_updated,
                           accounting=session.accounting, tag=session.tag, plan_mode=session.plan_mode)
        try:
            payload = (session.messages, session.turn_summaries, session.export_metadata)
            _check_size(payload)
            messages, summaries, metadata_copy = deepcopy(payload)
            detached = replace(detached, messages=messages, turn_summaries=summaries, export_metadata=metadata_copy)
        except (ValueError, TypeError, RecursionError, UnicodeError):
            retention_error = "Retention details unavailable: inspection size limit or unsupported session evidence."
    return ContextCapture(
        _binding(runtime), datetime.now(UTC).isoformat(timespec="seconds"), metadata,
        detached, manager if isinstance(manager, SessionManager) else None,
        accounting if isinstance(accounting, SessionRunAccounting) and detached is not None else None,
        retention_error, policy,
    )


def _remaining(value: Any, limit: Any) -> str:
    return "unlimited" if limit is None else f"{_value(value)} remaining of {limit}"


def _usage(snapshot: BudgetSnapshot, policy: EvidenceRedactor) -> _Rows:
    rows = _Rows(policy)
    rows.extend([
        "Task usage across all agents; not session-history tokens or task verification.",
        f"Run: {snapshot.run_id}",
        f"Accounting: {snapshot.accounting_lifetime}" + (" (this process only)" if snapshot.accounting_lifetime == "process" else " (persistent)"),
        f"Requests: {snapshot.consumed_requests} dispatched, {snapshot.reserved_requests} reserved; "
        + _remaining(snapshot.remaining_requests, snapshot.limits.max_requests),
        f"Task tokens: {snapshot.settled_tokens} settled, {snapshot.held_tokens} held; "
        + _remaining(snapshot.remaining_tokens, snapshot.limits.max_tokens),
        f"Time: {snapshot.elapsed_seconds:.1f}s elapsed; " + _remaining(snapshot.remaining_seconds, snapshot.limits.max_seconds),
        "Money limit: " + _remaining(snapshot.remaining_cost, snapshot.limits.max_cost)
        + (f" {snapshot.limits.currency}" if snapshot.limits.max_cost is not None else ""),
        f"Uncertain usage: {snapshot.unknown_dispatched_requests} dispatched requests",
    ])
    if not snapshot.money:
        rows.extend(("Estimated cost: unavailable", "Reported billing: unavailable"))
    for money in snapshot.money:
        for label, value in (("Estimated cost", money.settled_estimated_cost), ("Held estimate", money.held_cost),
                             ("Reported billing", money.reported_cost)):
            rows.append(f"{label}: {money.currency + ' ' + str(value) if value is not None else 'unavailable'}")
    summaries = summarize_usage(snapshot) if len(snapshot.records) <= _USAGE_RECORDS else ()
    if len(snapshot.records) > _USAGE_RECORDS:
        rows.append("Model details unavailable: inspection limit of 4,096 request records; totals above remain complete.")
    for summary in summaries:
        if rows.omitted:
            break
        total = summary.counts["total_tokens"]
        observed = "tokens unavailable" if total is None else f"{total} observed tokens"
        rows.append(f"{policy.text(summary.provider or 'unknown provider')}/{policy.text(summary.model or 'unknown model')} — "
                    f"{summary.usage_source}: {observed}; "
                    f"{summary.counted_requests['total_tokens']}/{summary.dispatched_requests} requests have totals; "
                    f"{summary.settled_requests} settled")
        for name in ("prompt_tokens", "completion_tokens", "cached_tokens", "cache_creation_tokens", "reasoning_tokens"):
            if name in summary.counts:
                rows.append(f"  {name}: {_value(summary.counts[name])}; "
                            f"{summary.counted_requests[name]}/{summary.dispatched_requests} requests")
        price = summary.pricing
        if price is None:
            rows.append("Price source: unavailable")
        else:
            rows.append(f"Price source: {policy.text(price.source)}; {policy.text(price.as_of or 'date unavailable')}; {price.currency}")
            rows.append("Rates per 1,000 tokens: " + ", ".join(
                f"{label} {_value(getattr(price, name))}" for label, name in
                (("input", "input_per_1k"), ("output", "output_per_1k"),
                 ("cache read", "cache_read_per_1k"), ("cache write", "cache_write_per_1k"))))
    rows.append("Cache and reasoning counts are subsets, not additional total tokens.")
    if snapshot.stop_reason or snapshot.accounting_error:
        rows.append(f"Accounting stop: {snapshot.accounting_error or snapshot.stop_reason}")
    return rows


def inspect_context(captured: ContextCapture) -> ContextInspection:
    """Read shared services off the UI loop; never prepare, compact or save."""
    context = _Rows(captured.policy)
    context.extend(captured.metadata)
    retention = _Rows(captured.policy)
    if captured.session is not None:
        context.extend((f"Session: {captured.policy.text(captured.session.id)}",
                        f"Tag: {captured.policy.text(captured.session.tag or '(untagged)')}"))
    if captured.retention_error is not None:
        context.append(captured.retention_error)
        retention.append(captured.retention_error)
    elif captured.session is not None and captured.manager is not None:
        try:
            snapshot = SessionContextService(captured.manager).build_snapshot(captured.session)
            context.extend((f"Session history estimate: {snapshot.token_estimate} tokens",
                            "Estimate covers session history, not the full next request or provider billing.",
                            f"Messages: {snapshot.message_count}; turns: {snapshot.turn_count}"))
            retention.extend((f"Turn summaries: {snapshot.turn_summary_count}",
                              f"Compacted turns retained: {snapshot.compacted_turn_count}",
                              f"Memories: {snapshot.memory_count}",
                              f"Memory extraction: {'opted out' if snapshot.memory_extraction_opt_out else 'allowed (not opted out)'}",
                              f"Plan mode: {'on' if snapshot.plan_mode else 'off'}",
                              f"Recorded tool calls: {snapshot.tool_usage.total_calls}; results: {snapshot.tool_usage.total_results}",
                              "Retained content is not displayed; session recovery uses the shared session controls."))
        except Exception as error:
            context.append(f"Session snapshot unavailable ({type(error).__name__}).")
            retention.append(f"Retention snapshot unavailable ({type(error).__name__}).")
    usage = _Rows(captured.policy)
    usage.append("No run accounting is available.")
    if captured.accounting is not None and captured.session is not None:
        try:
            snapshot_usage = captured.accounting.usage_snapshot(captured.session)
            if snapshot_usage is not None:
                usage = _usage(snapshot_usage, captured.policy)
        except Exception as error:
            usage = _Rows(captured.policy)
            usage.append(f"Accounting unavailable ({type(error).__name__}); no previous totals substituted.")
    sections = {"Context": context, "Retention": retention, "Usage": usage}
    return ContextInspection(captured.captured_at, datetime.now(UTC).isoformat(timespec="seconds"),
                             {key: value.text() for key, value in sections.items()},
                             frozenset(key for key, value in sections.items() if value.omitted))


class ContextScreen(ModalScreen[None]):
    """Inspect a captured selection, with explicit refresh and predictable Back."""

    DEFAULT_CSS = """
    ContextScreen { background: $surface; }
    #context-dialog { width: 100%; height: 100%; padding: 0 1; }
    #context-title { height: 1; text-style: bold; }
    #context-capture { height: 2; }
    #context-section-actions, #context-navigation { height: 3; }
    #context-section-actions Button, #context-navigation Button { min-width: 10; width: 1fr; margin: 0; }
    #context-details { height: 1fr; }
    #context-state { height: 2; color: $warning; }
    """
    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        Binding("escape", "back", "Back", priority=True), Binding("f5", "refresh", "Refresh", priority=True),
    ]

    def __init__(self, runtime: Any) -> None:
        super().__init__()
        self.runtime = runtime
        self._capture: ContextCapture | None = None
        self._inspection: ContextInspection | None = None
        self._section = "Context"
        self._read_task: asyncio.Task[None] | None = None
        self._close_task: asyncio.Task[None] | None = None
        self._closing_inspector = False
        self._state = "Loading…"

    def compose(self) -> ComposeResult:
        with Vertical(id="context-dialog"):
            yield Static("Context and usage", markup=False, id="context-title")
            yield Static("No snapshot yet", markup=False, id="context-capture")
            with Horizontal(id="context-section-actions"):
                for section in ("Context", "Retention", "Usage"):
                    yield Button(section, id=f"context-{section.lower()}")
            yield TextArea(read_only=True, soft_wrap=True, show_line_numbers=False, id="context-details")
            yield Static("Loading…", markup=False, id="context-state")
            with Horizontal(id="context-navigation"):
                yield Button("Refresh (F5)", id="context-refresh")
                yield Button("Back (Esc)", id="context-back")

    def on_mount(self) -> None:
        self.action_refresh()
        self.query_one("#context-context", Button).focus()
        self.set_interval(0.25, self._project_current)

    def action_refresh(self) -> None:
        if self._closing_inspector or (self._read_task is not None and not self._read_task.done()):
            return
        self._inspection = None
        try:
            self._capture = capture_context(self.runtime)
        except Exception as error:
            self._capture = None
            self._state = f"Context unavailable ({type(error).__name__}); Refresh to retry."
            self._project_current()
            return
        self._state = "Reading selected session…"
        self._project_current()
        self._read_task = asyncio.create_task(self._read(self._capture))

    async def _read(self, captured: ContextCapture) -> None:
        try:
            result = await _joined(asyncio.create_task(asyncio.to_thread(inspect_context, captured)))
            if not self._closing_inspector and captured.binding == _binding(self.runtime):
                self._inspection = result
                self._state = "Read-only snapshot; F5 refreshes. No task verification or save acknowledgement."
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self._state = f"Inspection unavailable ({type(error).__name__}); Refresh to retry."
        finally:
            # The display owns only allowlisted bounded metadata after the read.
            if self._capture is captured:
                self._capture = replace(captured, session=None)
            if self.is_mounted and not self._closing_inspector:
                self._project_current()

    def _project_current(self) -> None:
        if not self.is_mounted or self._closing_inspector:
            return
        text = ""
        state = self._state
        if self._capture is not None and self._capture.binding != _binding(self.runtime):
            self._inspection = None
            state = "Selected session or provider changed. Refresh to inspect the current selection."
        if self._inspection is not None:
            policy = _current_policy(self.runtime)
            stream = EvidenceStreamRedactor(policy)
            text = stream.feed(self._inspection.sections[self._section])
            text += stream.finish(interrupted=self._section in self._inspection.omitted)
            rows = text.splitlines()
            omitted = (self._section in self._inspection.omitted or len(rows) > _DETAIL_ROWS
                       or len(text.encode("utf-8")) > _TEXT_BYTES - 128)
            text = "\n".join(rows[:_DETAIL_ROWS]).encode("utf-8")[:_TEXT_BYTES - 128].decode("utf-8", errors="ignore")
            if omitted:
                text += "\n[Additional inspection details omitted by the display limit.]"
            self.query_one("#context-capture", Static).update(
                f"Captured at {self._inspection.captured_at}; read completed {self._inspection.read_completed_at}. "
                f"{self._section} — values may have changed; Refresh explicitly.")
        area = self.query_one("#context-details", TextArea)
        if area.text != text:
            area.load_text(text)
        self.query_one("#context-state", Static).update(state)

    async def _close(self) -> None:
        self._closing_inspector = True
        if self._read_task is not None and not self._read_task.done():
            self._read_task.cancel()
            with suppress(asyncio.CancelledError):
                await _joined(self._read_task)
        self._inspection = None
        self._capture = None

    async def aclose(self) -> None:
        if self._close_task is None:
            self._close_task = asyncio.create_task(self._close())
        await _joined(self._close_task)

    async def on_unmount(self) -> None:
        await self.aclose()

    async def action_back(self) -> None:
        await self.aclose()
        if self.is_mounted:
            self.dismiss()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        name = (event.button.id or "").removeprefix("context-")
        if name == "back":
            await self.action_back()
        elif name == "refresh":
            self.action_refresh()
        elif name in ("context", "retention", "usage"):
            self._section = name.title()
            self._project_current()
