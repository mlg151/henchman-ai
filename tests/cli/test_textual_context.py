"""Context inspection reads shared retention/accounting without runtime effects."""

import asyncio
from decimal import Decimal
from threading import Event
from types import SimpleNamespace

import pytest
from textual.document._document import Selection
from textual.widgets import Button, Static, TabbedContent, TextArea

from henchman.cli.session_manager import ReplSessionManager
from henchman.cli.textual_context import ContextScreen, capture_context, inspect_context
from henchman.cli.textual_widgets import ChatPane, HenchmanTextArea
from henchman.core.agent import Agent
from henchman.core.run_budget import ReportedCost, RequestEstimate
from henchman.core.session import SessionManager, SessionMessage
from henchman.core.session_context import SessionContextService
from henchman.core.session_memory import SessionMemoryService
from henchman.core.session_run_accounting import SessionRunAccounting
from henchman.providers.usage import UsageReport
from tests.agents.test_agent_budget_scope import AccountingProvider
from tests.cli.ui_scenarios import InteractionApp, populate_history, settle_layout


@pytest.fixture
def context_app(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = InteractionApp(tmp_path)
    manager = SessionManager(data_dir=tmp_path / "sessions")
    session = manager.create_session(project_hash=manager.compute_project_hash(tmp_path), tag="current")
    repl = ReplSessionManager(manager, auto_save=False, settings=app.settings)
    repl.session = session
    provider = AccountingProvider()
    agent = Agent(provider, max_tokens=13926, context_window=16384)
    accounting = SessionRunAccounting(app.settings, lambda: repl.current, lambda _: None, tmp_path / "ops.db")

    async def close():
        pass

    app.core_context = SimpleNamespace(
        project_root=tmp_path, session_manager=repl, agent=agent,
        orchestrator=SimpleNamespace(accounting_runtime=accounting, aclose=close), mcp_manager=None,
        background_tasks=[],
    )
    return app, session, manager, accounting


async def ready(pilot):
    await settle_layout(pilot)
    screen = pilot.app.screen
    if isinstance(screen, ContextScreen) and screen._read_task is not None:
        await asyncio.wait_for(asyncio.shield(screen._read_task), 5)
    await settle_layout(pilot)
    return screen


def visible(screen):
    return screen.query_one("#context-details", TextArea).text


def test_snapshot_uses_current_retention_without_loading_saving_or_compacting(context_app, monkeypatch):
    app, session, manager, _ = context_app
    session.messages = [SessionMessage("user", "first"), SessionMessage("assistant", "answer"),
                        SessionMessage("user", "second")]
    memory = SessionMemoryService()
    memory.add_memory(session, content="private memory body")
    memory.set_extraction_opt_out(session, True)
    service = SessionContextService(manager)
    service.compact_session(session, preserve_turns=1)
    before = session.to_dict()
    expected = service.build_snapshot(session)
    for method in ("save", "load", "set_project_current"):
        monkeypatch.setattr(manager, method, lambda *_a, **_k: pytest.fail("inspection mutated selection/storage"))
    captured = capture_context(app)
    view = inspect_context(captured)
    text = "\n".join(view.sections.values())
    assert f"Session history estimate: {expected.token_estimate}" in text
    assert "Memory extraction: opted out" in text
    assert "Compacted turns retained: 1" in text and "Memories: 1" in text
    assert "private memory body" not in text and "answer" not in text
    assert "Autosave: off" in text and "Disk save acknowledgement: unavailable" in text
    assert "Request capacity: 16384" in text and "Conversation budget: 13926" in text
    assert "No run accounting is available" in text and "Reported billing: 0" not in text
    assert session.to_dict() == before


def test_selected_cached_role_is_actual_provider_and_inspection_never_constructs_agent(context_app):
    app, _, _, _ = context_app
    provider = SimpleNamespace(name="acting-local", default_model="actual-model")
    specialist = SimpleNamespace(provider=provider, max_tokens=123, context_window=None)
    app.config.agent_role = "engineer"
    pool = SimpleNamespace(_agents={"engineer": specialist}, get_agent=lambda _role: pytest.fail("created agent"))
    app.core_context.orchestrator.pool = pool
    text = inspect_context(capture_context(app)).sections["Context"]
    assert "Provider: acting-local" in text and "Model: actual-model" in text
    assert "Request capacity: unavailable" in text
    pool._agents.clear()
    text = inspect_context(capture_context(app)).sections["Context"]
    assert "Provider: unavailable" in text and "actual-model" not in text


@pytest.mark.parametrize("durable", [False, True])
def test_shared_usage_preserves_sources_coverage_currencies_and_session_scope(context_app, durable, monkeypatch):
    from dataclasses import replace

    app, session, _, accounting = context_app
    accounting.settings.usage.persistence = "durable" if durable else "process"
    scope = accounting.begin(AccountingProvider())
    first = scope.ledger.reserve(RequestEstimate(10, 10), provider="local", model="one", agent_id="worker")
    scope.ledger.start(first.request_id)
    scope.ledger.reconcile(first.request_id, UsageReport(total_tokens=12, source="reported"), final=True)
    scope.ledger.reconcile(first.request_id, reported_cost=ReportedCost(Decimal("0.1"), "USD"))
    scope.ledger.reconcile(first.request_id, reported_cost=ReportedCost(Decimal("0.2"), "EUR"))
    second = scope.ledger.reserve(RequestEstimate(10, 10), provider="local", model="two")
    scope.ledger.start(second.request_id)
    third = scope.ledger.reserve(RequestEstimate(10, 10), provider="local", model="three")
    scope.ledger.start(third.request_id)
    scope.ledger.reconcile(third.request_id, UsageReport(total_tokens=7, source="estimated"), final=True)
    original_snapshot = accounting.usage_snapshot

    def snapshot_with_elapsed(selected_session):
        snapshot = original_snapshot(selected_session)
        return replace(snapshot, elapsed_seconds=0.3) if snapshot is not None else None

    monkeypatch.setattr(accounting, "usage_snapshot", snapshot_with_elapsed)
    text = inspect_context(capture_context(app)).sections["Usage"]
    assert "Time: 0.3s elapsed; unlimited" in text
    assert f"Accounting: {'durable' if durable else 'process'}" in text
    assert "3 dispatched" in text
    assert f"Uncertain usage: {scope.ledger.snapshot().unknown_dispatched_requests} dispatched requests" in text
    assert "reported: 12 observed tokens; 1/1 requests have totals" in text
    assert "estimated: 7 observed tokens" in text
    assert "unknown: tokens unavailable; 0/1 requests have totals" in text
    money_rows = [line for line in text.splitlines()
                  if line.startswith(("Reported billing:", "Estimated cost:", "Held estimate:"))]
    assert sorted(money_rows) == sorted([
        "Reported billing: USD 0.1", "Reported billing: EUR 0.2",
        "Estimated cost: unavailable", "Estimated cost: unavailable",
        "Held estimate: unavailable", "Held estimate: unavailable",
    ])
    # A real different Session, rather than reusing a previous global last scope.
    app.core_context.session_manager.session = replace(session, id="different-session", accounting=None)
    assert "No run accounting" in inspect_context(capture_context(app)).sections["Usage"]


@pytest.mark.parametrize("size", [(80, 24), (120, 40)])
async def test_mounted_button_sections_refresh_back_preserve_draft_selection_and_hold(context_app, size):
    app, _, _, _ = context_app
    async with app.run_test(size=size) as pilot:
        chat = app.query_one(ChatPane)
        populate_history(chat)
        composer = app.query_one(HenchmanTextArea)
        composer.load_text("unsent\ndraft")
        composer.selection = Selection((0, 1), (1, 3))
        selection = composer.selection
        composer.focus()
        await pilot.press("alt+pageup")
        app.action_context_inspector()
        screen = await ready(pilot)
        assert isinstance(screen, ContextScreen)
        assert "Captured at" in str(screen.query_one("#context-capture", Static).render())
        assert screen.query_one("#context-back", Button).region.bottom <= size[1]
        assert screen.query_one(TextArea).region.height > 0
        screen.query_one("#context-usage", Button).focus()
        await pilot.press("enter", "f5")
        await ready(pilot)
        assert "No run accounting" in visible(screen)
        await pilot.press("escape")
        await ready(pilot)
        assert app.focused is composer and composer.text == "unsent\ndraft" and composer.selection == selection
        assert not chat.follow_live
        app.query_one(TabbedContent).active = "tab-context"
        await settle_layout(pilot)
        app.query_one("#context-inspect", Button).focus()
        await pilot.press("enter")
        assert isinstance(await ready(pilot), ContextScreen)


async def test_rotation_masks_metadata_and_never_displays_hidden_content(context_app):
    app, session, manager, _ = context_app
    secret = "new-context-secret"
    session.tag = secret
    session.messages = [SessionMessage("assistant", "visible body withheld", reasoning_content="hidden reasoning body")]
    async with app.run_test() as pilot:
        app.action_context_inspector()
        screen = await ready(pilot)
        assert secret in visible(screen)
        manager.evidence_redactor.register_secret(secret)
        screen._project_current()
        assert secret not in visible(screen) and "[REDACTED]" in visible(screen)
        assert "hidden reasoning body" not in visible(screen) and "visible body withheld" not in visible(screen)
        assert session.tag == secret


async def test_pending_question_keeps_ownership(context_app):
    app, _, _, _ = context_app
    async with app.run_test() as pilot:
        question = asyncio.create_task(app._textual_question("Current decision"))
        await settle_layout(pilot)
        current = app.screen
        app.action_context_inspector()
        await settle_layout(pilot)
        assert app.screen is current and not question.done()
        await pilot.press("escape")
        assert await question is None


async def test_back_joins_read_worker_and_stale_selection_cannot_publish(context_app, monkeypatch):
    from henchman.cli import textual_context

    app, session, _, _ = context_app
    entered, release, finished = Event(), Event(), Event()
    original = textual_context.inspect_context

    def gated(captured):
        entered.set()
        assert release.wait(5)
        try:
            return original(captured)
        finally:
            finished.set()

    monkeypatch.setattr(textual_context, "inspect_context", gated)
    async with app.run_test() as pilot:
        app.action_context_inspector()
        await settle_layout(pilot)
        screen = app.screen
        assert await asyncio.to_thread(entered.wait, 2)
        session.id = "changed-selection"
        closing = asyncio.create_task(screen.action_back())
        await asyncio.sleep(0)
        assert not closing.done() and not finished.is_set()
        release.set()
        await asyncio.wait_for(closing, 3)
        await settle_layout(pilot)
        assert finished.is_set() and screen not in app.screen_stack


def test_oversized_snapshot_is_unavailable_without_a_partial_token_estimate(context_app):
    app, session, _, _ = context_app
    session.messages = [SessionMessage("user", "x" * (2 * 1024 * 1024 + 1))]
    view = inspect_context(capture_context(app))
    assert "inspection size limit" in view.sections["Context"]
    assert "Session history estimate:" not in view.sections["Context"]
    assert "No run accounting" in view.sections["Usage"]


def test_actual_provider_alias_and_request_model_override_are_not_default_labels(context_app):
    app, _, _, _ = context_app
    provider = app.core_context.agent.provider
    provider._accounting_provider_name = "local-compatible-alias"
    provider.request_defaults = {"model": "option-model", "extra_body": {"model": "body-model"}}
    view = inspect_context(capture_context(app)).sections["Context"]
    assert "Provider: local-compatible-alias" in view
    assert "Model: body-model" in view and "Model: test-model" not in view


def test_cross_project_session_is_unavailable_without_accounting_lookup(context_app, monkeypatch):
    app, session, _, accounting = context_app
    session.project_hash = "another-project"
    monkeypatch.setattr(accounting, "usage_snapshot", lambda *_: pytest.fail("read foreign project accounting"))
    result = inspect_context(capture_context(app))
    assert "does not belong" in result.sections["Context"]
    assert "No run accounting" in result.sections["Usage"]


def test_context_copy_is_detached_and_hidden_continuation_never_becomes_display_evidence(context_app):
    from copy import deepcopy

    from henchman.providers.continuation import ContinuationEnvelope

    app, session, _, _ = context_app
    fake_provider = SimpleNamespace(name="deepseek", default_model="fixture", base_url="http://fixture.invalid",
                                    api_key="offline")
    continuation = ContinuationEnvelope.create(fake_provider, "opaque signed native reasoning").to_dict()
    session.messages = [SessionMessage("assistant", "ordinary private transcript", reasoning_content="hidden body",
                                       continuation=continuation)]
    captured = capture_context(app)
    before = deepcopy(session.messages[0])
    session.messages.append(SessionMessage("user", "later live turn"))
    text = "\n".join(inspect_context(captured).sections.values())
    assert "Messages: 1" in text
    for secret in ("opaque signed native reasoning", "hidden body", "ordinary private transcript", "later live turn"):
        assert secret not in text
    assert session.messages[0] == before and captured.session.messages is not session.messages


def test_explicit_auth_headers_are_projected_before_metadata_prefixes(context_app):
    app, session, _, _ = context_app
    session.tag = "Authorization: Bearer unregistered-tag-secret"
    app.core_context.agent.provider.default_model = "Cookie: unregistered-model-secret"
    view = inspect_context(capture_context(app))
    text = "\n".join(view.sections.values())
    assert "unregistered-tag-secret" not in text and "unregistered-model-secret" not in text
    assert "[REDACTED]" in text


def test_accounting_failure_has_no_raw_error_or_previous_totals(context_app, monkeypatch):
    from henchman.core.run_budget import BudgetAccountingError

    app, _, _, accounting = context_app

    def broken(_session):
        raise BudgetAccountingError("Authorization: Bearer private-storage-error")

    monkeypatch.setattr(accounting, "usage_snapshot", broken)
    view = inspect_context(capture_context(app)).sections["Usage"]
    assert "Accounting unavailable" in view and "no previous totals" in view
    assert "private-storage-error" not in view and "0.00" not in view


async def test_refresh_rejects_read_from_old_session_and_new_selection_is_explicit(context_app, monkeypatch):
    from dataclasses import replace

    from henchman.cli import textual_context

    app, session, _, _ = context_app
    entered, release = Event(), Event()
    original = textual_context.inspect_context

    def gated(captured):
        entered.set()
        assert release.wait(5)
        return original(captured)

    monkeypatch.setattr(textual_context, "inspect_context", gated)
    async with app.run_test() as pilot:
        app.action_context_inspector()
        await settle_layout(pilot)
        screen = app.screen
        assert await asyncio.to_thread(entered.wait, 2)
        app.core_context.session_manager.session = replace(session, id="new-selection", tag="new tag")
        release.set()
        await ready(pilot)
        assert visible(screen) == ""
        assert "Refresh" in str(screen.query_one("#context-state", Static).render())
        await pilot.press("f5")
        await ready(pilot)
        assert "Session: new-selection" in visible(screen) and "Tag: new tag" in visible(screen)
        assert screen._capture.session is None  # raw transcript released after inspection


async def test_request_model_change_requires_refresh_without_provider_replacement(context_app):
    app, _, _, _ = context_app
    async with app.run_test() as pilot:
        app.action_context_inspector()
        screen = await ready(pilot)
        app.core_context.agent.provider.request_defaults = {"model": "later-override"}
        screen._project_current()
        assert not visible(screen)
        await pilot.press("f5")
        await ready(pilot)
        assert "Model: later-override" in visible(screen)


async def test_cancelled_repeated_close_joins_exact_read_owner(context_app, monkeypatch):
    from henchman.cli import textual_context

    app, _, _, _ = context_app
    entered, release, finished = Event(), Event(), Event()
    calls = []
    original = textual_context.inspect_context

    def gated(captured):
        calls.append(captured)
        entered.set()
        assert release.wait(5)
        try:
            return original(captured)
        finally:
            finished.set()

    monkeypatch.setattr(textual_context, "inspect_context", gated)
    async with app.run_test() as pilot:
        app.action_context_inspector()
        await settle_layout(pilot)
        screen = app.screen
        assert await asyncio.to_thread(entered.wait, 2)
        screen.action_refresh()
        closing = asyncio.create_task(screen.aclose())
        other = asyncio.create_task(screen.aclose())
        await asyncio.sleep(0)
        closing.cancel("original close cancellation")
        await asyncio.sleep(0)
        closing.cancel("later cancellation")
        await asyncio.sleep(0)
        assert not closing.done() and not other.done()
        release.set()
        with pytest.raises(asyncio.CancelledError, match="original close cancellation"):
            await closing
        await other
        assert finished.is_set() and len(calls) == 1 and screen._capture is None


async def test_many_usage_groups_are_bounded_with_visible_omissions(context_app):
    app, _, _, accounting = context_app
    scope = accounting.begin(AccountingProvider())
    for index in range(30):
        request = scope.ledger.reserve(RequestEstimate(1, 1), provider="local", model=f"model-{index}")
        scope.ledger.start(request.request_id)
        scope.ledger.reconcile(request.request_id, UsageReport(total_tokens=1, source="reported"), final=True)
    async with app.run_test(size=(80, 24)) as pilot:
        app.action_context_inspector()
        screen = await ready(pilot)
        screen.query_one("#context-usage", Button).focus()
        await pilot.press("enter")
        text = visible(screen)
        assert "30 dispatched" in text and "details omitted" in text
        assert len(text.encode()) <= 65536 and len(text.splitlines()) <= 129


def test_inspection_does_not_change_durable_store_or_goal_authority(context_app):
    app, session, _, accounting = context_app
    accounting.settings.usage.persistence = "durable"
    scope = accounting.begin(AccountingProvider())
    request = scope.ledger.reserve(RequestEstimate(1, 1), provider="local", model="fixture")
    scope.ledger.start(request.request_id)
    scope.ledger.reconcile(request.request_id, UsageReport(total_tokens=1, source="reported"), final=True)
    before = accounting.store_path.read_bytes()
    reference = session.accounting
    owners = dict(accounting._active)
    text = inspect_context(capture_context(app)).sections["Usage"]
    assert "1 dispatched" in text
    assert accounting.store_path.read_bytes() == before and session.accounting == reference
    assert accounting._active == owners


async def test_accounting_owner_replacement_invalidates_display_even_for_same_session(context_app):
    app, _, _, _ = context_app
    async with app.run_test() as pilot:
        app.action_context_inspector()
        screen = await ready(pilot)
        app.core_context.orchestrator.accounting_runtime = None
        screen._project_current()
        assert visible(screen) == ""
        assert "Refresh" in str(screen.query_one("#context-state", Static).render())


def test_price_snapshot_zero_is_estimate_not_reported_bill_and_subsets_are_not_added(context_app):
    from henchman.providers.usage import TokenPricing

    app, _, _, accounting = context_app
    scope = accounting.begin(AccountingProvider())
    price = TokenPricing(0, 0, 0, 0, source="fixture catalog", as_of="2026-11-07")
    request = scope.ledger.reserve(RequestEstimate(10, 10, price), provider="local", model="fixture")
    scope.ledger.start(request.request_id)
    scope.ledger.reconcile(request.request_id, UsageReport(prompt_tokens=10, completion_tokens=5,
                                                         cached_tokens=3, reasoning_tokens=2, source="reported"), final=True)
    text = inspect_context(capture_context(app)).sections["Usage"]
    assert "reported: 15 observed tokens" in text
    assert "cached_tokens: 3; 1/1 requests" in text and "reasoning_tokens: 2; 1/1 requests" in text
    assert "Estimated cost: USD 0" in text and "Reported billing: unavailable" in text
    assert "fixture catalog; 2026-11-07; USD" in text
    assert "Rates per 1,000 tokens: input 0, output 0, cache read 0, cache write 0" in text


async def test_application_shutdown_joins_inspection_read(context_app, monkeypatch):
    from henchman.cli import textual_context

    app, _, _, _ = context_app
    entered, release, finished = Event(), Event(), Event()
    original = textual_context.inspect_context

    def gated(captured):
        entered.set()
        assert release.wait(5)
        try:
            return original(captured)
        finally:
            finished.set()

    monkeypatch.setattr(textual_context, "inspect_context", gated)
    async with app.run_test() as pilot:
        app.action_context_inspector()
        await settle_layout(pilot)
        screen = app.screen
        assert await asyncio.to_thread(entered.wait, 2)
        app.exit()
        await asyncio.sleep(0)
        assert not finished.is_set()
        release.set()
    assert finished.is_set() and screen._read_task.done() and screen._capture is None


async def test_context_details_rotation_preserves_read_selection_and_scroll(context_app):
    app, _, manager, _ = context_app
    async with app.run_test(size=(80, 24)) as pilot:
        app.action_context_inspector()
        screen = await ready(pilot)
        area = screen.query_one(TextArea)
        area.selection = Selection((0, 2), (0, 5))
        area.scroll_end(animate=False)
        before = area.selection
        screen._project_current()
        assert area.selection == before
        manager.evidence_redactor.register_secret("test-model")
        screen._project_current()
        assert "test-model" not in area.text


@pytest.mark.parametrize("source", ["actor", "cached-role", "session-policy"])
async def test_current_actor_and_session_credentials_reproject_without_refresh(context_app, source):
    from henchman.utils.evidence_redaction import EvidenceRedactor

    app, session, _, _ = context_app
    previous, rotated = "previous-actor-secret", "rotated-selected-secret"
    session.tag = f"{previous} and {rotated}"
    provider = app.core_context.agent.provider
    if source == "session-policy":
        session.evidence_redactor = EvidenceRedactor()
        session.evidence_redactor.register_secret(previous)
    else:
        provider.api_key = previous
    if source == "cached-role":
        app.config.agent_role = "engineer"
        app.core_context.orchestrator.pool = SimpleNamespace(
            _agents={"engineer": app.core_context.agent}, get_agent=lambda _role: app.core_context.agent,
        )
    async with app.run_test() as pilot:
        app.action_context_inspector()
        screen = await ready(pilot)
        captured = screen._inspection
        assert previous not in visible(screen) and rotated in visible(screen)
        if source == "session-policy":
            session.evidence_redactor.register_secret(rotated)
        else:
            provider.api_key = rotated
        screen._project_current()
        assert rotated not in visible(screen) and previous not in visible(screen)
        assert "[REDACTED]" in visible(screen) and screen._inspection is captured
        # Clearing/replacing a credential source must not reveal earlier evidence.
        if source == "session-policy":
            session.evidence_redactor = EvidenceRedactor()
        else:
            provider.api_key = None
        screen._project_current()
        assert rotated not in visible(screen) and previous not in visible(screen)
        assert session.tag == f"{previous} and {rotated}"
