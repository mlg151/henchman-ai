"""Keyboard checkpoint review over shared content and verification services."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any, ClassVar, TypeVar

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, OptionList, Static, TextArea
from textual.widgets.option_list import Option

from henchman.advanced.checkpoint_models import CheckpointRecord, CheckpointReview, ReviewPlan
from henchman.advanced.checkpoints import CheckpointConflict, CheckpointService
from henchman.advanced.plans import PlanExecutionService, PlanRecord
from henchman.advanced.tasks import TaskService
from henchman.cli.evidence import runtime_evidence_redactor, runtime_exception_text
from henchman.cli.textual_context import _current_policy
from henchman.config.schema import Settings
from henchman.utils.evidence_redaction import EvidenceRedactor

_T = TypeVar("_T")
_TEXT_LIMIT = 65536
_CHECK_PLAN_LIMIT = 64


def require_idle(runtime: Any, root: Path) -> None:
    """Check only this runtime's ownership; external writers need service conflicts."""
    context = getattr(runtime, "core_context", None)
    orchestrator = getattr(context, "orchestrator", None)
    operations = getattr(orchestrator, "operation_runtime", None)
    subagents = getattr(orchestrator, "subagents", None)
    prompt = getattr(getattr(runtime, "_tool_prompts", None), "_answer", None)
    task = getattr(runtime, "current_agent_task", None)
    active = (bool(getattr(runtime, "is_processing", False))
              or (isinstance(task, asyncio.Task) and not task.done())
              or (isinstance(prompt, asyncio.Future) and not prompt.done())
              or bool(getattr(operations, "_inflight", None))
              or (subagents is not None and subagents.has_running_work()))
    if active or TaskService.has_active_work(root):
        raise ValueError("Apply requires an idle runtime: finish or cancel active work and pending decisions first.")


async def _joined(action: Callable[[], _T]) -> _T:
    """Never leave an authorized filesystem worker behind a closed screen."""
    worker = asyncio.create_task(asyncio.to_thread(action))
    cancelled: asyncio.CancelledError | None = None
    while not worker.done():
        try:
            await asyncio.shield(worker)
        except asyncio.CancelledError as error:
            cancelled = cancelled or error
        except BaseException:
            if not worker.done():
                raise
    try:
        value = worker.result()
    except BaseException:
        if cancelled is not None:
            cancelled.add_note("Checkpoint worker also failed during joined shutdown")
            raise cancelled from None
        raise
    if cancelled is not None:
        raise cancelled
    return value


class CheckpointReviewScreen(ModalScreen[None]):
    """Inspect one project with explicit preview and separately activated apply."""

    DEFAULT_CSS = """
    CheckpointReviewScreen { background: $surface; }
    #checkpoint-dialog { width: 100%; height: 100%; padding: 0 1; }
    #checkpoint-title { height: 1; text-style: bold; }
    #checkpoint-summary { height: 2; }
    #checkpoint-status { height: 2; color: $warning; }
    #checkpoint-body { height: 1fr; }
    #checkpoint-list { width: 32; height: 1fr; border: solid $accent; }
    #checkpoint-content { width: 1fr; height: 1fr; }
    #checkpoint-actions { height: 3; }
    #checkpoint-actions Button { min-width: 10; width: 1fr; margin: 0; }
    #checkpoint-hints { height: 1; }
    CheckpointReviewScreen.narrow #checkpoint-list { width: 1fr; }
    """
    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        Binding("escape", "back", "Back", priority=True),
        Binding("n", "next_hunk", "Next hunk", priority=True),
        Binding("p", "previous_hunk", "Previous hunk", priority=True),
        Binding("w", "whole_file", "Whole file", priority=True),
        Binding("a", "preview_accept", "Preview accept", priority=True),
        Binding("r", "preview_reject", "Preview reject", priority=True),
        Binding("v", "checks", "Project checks", priority=True),
        Binding("f5", "refresh", "Refresh", priority=True),
        Binding("ctrl+enter", "retain_draft", "Retain draft", priority=True, show=False),
    ]

    def __init__(self, runtime: Any, root: Path) -> None:
        super().__init__()
        self.runtime, self.root = runtime, root
        self._policy = runtime_evidence_redactor(runtime)
        self._records: tuple[CheckpointRecord, ...] = ()
        self._pending: tuple[str, ...] = ()
        self._review: CheckpointReview | None = None
        self._file_index = 0
        self._record_index = 0
        self._hunk_index: int | None = None
        self._stage = "catalog"
        self._return_stage = "catalog"
        self._plan: ReviewPlan | None = None
        self._checks = ""
        self._status = "Loading captures…"
        self._action_task: asyncio.Task[None] | None = None
        self._busy = False
        self._review_closing = False
        self._refresh_required = False
        self._checks_policy = EvidenceRedactor()
        self._checks_settings = self._runtime_settings()
        self._checks_binding = self._checks_identity()

    def _runtime_settings(self) -> Settings | None:
        context = getattr(self.runtime, "core_context", None)
        settings = getattr(context, "settings", None)
        if settings is None:
            settings = getattr(self.runtime, "settings", None)
        return settings if isinstance(settings, Settings) else None

    def _checks_identity(self) -> tuple[object, ...]:
        """Bind read-only check observations to this selected runtime/project."""
        context = getattr(self.runtime, "core_context", None)
        manager = getattr(context, "session_manager", None) or getattr(self.runtime, "session_manager", None)
        session = getattr(manager, "current", None)
        root = self.root.resolve(strict=True)
        info = root.stat()
        return (id(context), id(manager), id(session), getattr(session, "id", None),
                getattr(session, "project_hash", None), id(self._runtime_settings()),
                getattr(context, "project_root", None), getattr(self.runtime, "project_root", None),
                Path.cwd(), root, info.st_dev, info.st_ino)

    def _require_checks_binding(self) -> None:
        if self._review_closing or self._checks_identity() != self._checks_binding:
            raise ValueError("Check inspection runtime or project changed. Close and reopen review.")
        context = getattr(self.runtime, "core_context", None)
        bound_root = getattr(context, "project_root", None) or getattr(self.runtime, "project_root", None)
        if bound_root is not None and Path(bound_root).resolve(strict=True) != self.root.resolve(strict=True):
            raise ValueError("Check inspection project does not match the selected runtime. Close and reopen review.")
        if self._checks_settings is None:
            raise ValueError("Held runtime settings are unavailable for check inspection.")

    def compose(self) -> ComposeResult:
        with Vertical(id="checkpoint-dialog"):
            yield Static("Review changes", markup=False, id="checkpoint-title")
            yield Static("", markup=False, id="checkpoint-summary")
            yield Static("", markup=False, id="checkpoint-status")
            with Horizontal(id="checkpoint-body"):
                yield OptionList(id="checkpoint-list")
                yield TextArea(read_only=True, soft_wrap=True, show_line_numbers=False, id="checkpoint-content")
            with Horizontal(id="checkpoint-actions"):
                yield Button("Back", id="checkpoint-back")
                yield Button("Refresh", id="checkpoint-refresh")
                yield Button("Checks", id="checkpoint-checks")
                yield Button("Accept…", id="checkpoint-accept")
                yield Button("Reject…", id="checkpoint-reject")
                yield Button("Apply", variant="warning", id="checkpoint-apply", disabled=True)
            yield Static("Enter inspect · n/p hunk · w whole file · a/r preview · Esc Back", markup=False, id="checkpoint-hints")

    def on_mount(self) -> None:
        self.action_refresh()
        self.query_one(OptionList).focus()

    def on_resize(self) -> None:
        if self.is_mounted:
            self._layout()

    async def on_unmount(self) -> None:
        self._review_closing = True
        if self._action_task is not None and not self._action_task.done():
            self._action_task.cancel()
            await asyncio.gather(self._action_task, return_exceptions=True)

    def _service(self) -> CheckpointService:
        return CheckpointService(self.root, redactor=self._policy)

    def _safe(self, text: str) -> str:
        text = runtime_evidence_redactor(self.runtime).text(text)
        return text if len(text) <= _TEXT_LIMIT else text[:_TEXT_LIMIT] + "\n[Display truncated; decisions use full captured bytes.]"

    def _launch(self, action: Callable[[], Awaitable[None]]) -> None:
        if self._busy:
            return
        self._policy = runtime_evidence_redactor(self.runtime)
        self._busy = True
        self._render_view()

        async def owned() -> None:
            try:
                await action()
            except asyncio.CancelledError:
                raise
            except Exception as error:
                self._plan = None
                self._status = runtime_exception_text(self.runtime, error)
                if isinstance(error, CheckpointConflict) and error.paths:
                    self._status += ": " + self._safe(", ".join(error.paths))
                self._status += " Refresh before another decision."
                self._refresh_required = True
                if self._stage == "preview":
                    self._stage = "detail"
            finally:
                self._busy = False
                if not self._review_closing:
                    self._render_view()

        self._action_task = asyncio.create_task(owned())

    async def _reload(self) -> None:
        def read() -> tuple[tuple[CheckpointRecord, ...], tuple[str, ...], CheckpointReview | None]:
            service = self._service()
            records = service.list_checkpoints()
            review = service.review(self._review.checkpoint_id) if self._review is not None else None
            return records, service.pending_restores(), review
        self._records, self._pending, review = await _joined(read)
        self._plan = None
        self._refresh_required = False
        if review is not None:
            self._review = review
            self._file_index = min(self._file_index, max(0, len(review.files) - 1))
            self._hunk_index = None
        self._status = ("Interrupted restore pending. Use /checkpoint recover " + ", ".join(self._pending)
                        if self._pending else "Select a capture." if not self._records else "Preview a decision before applying. Workspace restore is separate from conversation history.")
        self._render_list()

    def action_refresh(self) -> None:
        if self._stage == "checks":
            self.action_checks()
            return
        if self._stage == "preview":
            self._stage = "detail"
        self._launch(self._reload)

    def _render_list(self) -> None:
        widget = self.query_one(OptionList)
        selected = widget.highlighted
        widget.clear_options()
        if self._stage == "catalog":
            rows = [f"{record.checkpoint_id[:12]} · {record.actor} · {record.state}" for record in self._records]
            selected = self._record_index
        else:
            rows = [f"{file.path} [{file.decision}]" + (" — non-restorable" if not file.restorable else "")
                    for file in self._review.files] if self._review else []
            selected = self._file_index
        widget.add_options([Option(Text(self._safe(row)), id=str(index)) for index, row in enumerate(rows)])
        widget.highlighted = min(selected or 0, len(rows) - 1) if rows else None

    def _layout(self) -> None:
        narrow = self.size.width < 100
        self.set_class(narrow, "narrow")
        self.query_one(OptionList).display = self._stage in {"catalog", "files"} or (not narrow and self._stage == "detail")
        self.query_one(TextArea).display = self._stage not in {"catalog", "files"} or (not narrow and self._stage == "files")

    def _detail(self) -> str:
        review = self._review
        if review is None or not review.files:
            return "No file selected."
        file = review.files[self._file_index]
        identity = review.operation
        details = [f"Checkpoint {review.checkpoint_id} · revision {review.revision}",
                   f"Metadata policy: {review.metadata_policy}"]
        if identity is not None:
            details.extend([f"Operation: {identity.operation_id} · Run: {identity.run_id}",
                            f"Agent: {identity.agent_id} · Tool: {identity.tool_name}"])
        lines = [f"File: {file.path} · decision: {file.decision}",
                 f"Before: {file.before.status}; after: {file.after.status}"]
        if review.metadata_policy == "windows-private-acl-content-only":
            lines.append("Restore uses a private ACL; original ACLs/timestamps are not restored.")
        if not file.restorable:
            lines.append("This file is non-restorable; accept/reject is unavailable.")
        selected = [hunk for hunk in file.hunks if self._hunk_index is None or hunk.index == self._hunk_index]
        lines.append("Scope: whole file" if self._hunk_index is None else f"Scope: hunk {self._hunk_index + 1}")
        if not selected:
            lines.append(f"Hunks: {file.hunk_status}. Whole-file decision only when restorable.")
            if file.restorable:
                lines.extend(["--- Before", file.before.content.decode("utf-8") if file.before.content is not None else "[missing]",
                              "+++ After", file.after.content.decode("utf-8") if file.after.content is not None else "[missing]"])
        for hunk in selected:
            lines.extend([f"@@ Hunk {hunk.index + 1} ({'accepted' if hunk.accepted else 'pending'}) @@",
                          "--- Before", hunk.before, "+++ After", hunk.after])
        lines.extend(["", "Capture details", *details])
        return "\n".join(lines)

    def _render_view(self) -> None:
        if not self.is_mounted or self._review_closing:
            return
        self.query_one("#checkpoint-title", Static).update(self._safe(f"Review changes · {self.root}"))
        self.query_one("#checkpoint-summary", Static).update(
            "Checks inspect declared-input freshness; checkpoint acceptance is not established.\n"
            + ("No captures yet." if not self._records else f"{len(self._records)} capture(s) · {self._stage}"))
        self.query_one("#checkpoint-status", Static).update(self._safe("Working; closing waits for filesystem cleanup." if self._busy else self._status))
        content = self._checks if self._stage == "checks" else self._detail()
        if self._stage == "preview" and self._plan is not None:
            action = "record acceptance without changing bytes" if self._plan.decision == "accept" else "restore selected original content"
            content = f"PREVIEW: {self._plan.decision} — {action}\nPlan: {self._plan.plan_id}\nNothing has been applied. Activate Apply explicitly.\n\n" + content
        area = self.query_one(TextArea)
        safe = self._safe(content)
        if area.text != safe:
            area.load_text(safe)
        eligible = (self._stage == "detail" and self._review is not None and bool(self._review.files)
                    and self._review.files[self._file_index].restorable and not self._pending and not self._refresh_required)
        for button in self.query(Button):
            button.disabled = self._busy
        self.query_one("#checkpoint-accept", Button).disabled = self._busy or not eligible
        self.query_one("#checkpoint-reject", Button).disabled = self._busy or not eligible
        self.query_one("#checkpoint-apply", Button).disabled = self._busy or self._plan is None or self._stage != "preview"
        self._layout()

    @on(OptionList.OptionSelected, "#checkpoint-list")
    def _selected(self, event: OptionList.OptionSelected) -> None:
        event.stop()
        if self._busy:
            return
        index = event.option_index
        if self._stage == "catalog":
            self._record_index = index
            async def load() -> None:
                self._review = await _joined(lambda: self._service().review(self._records[index].checkpoint_id))
                self._refresh_required = False
                self._file_index, self._hunk_index, self._stage = 0, None, "files"
                self._status = "Enter inspects the selected file."
                self._render_list()
            self._launch(load)
        else:
            self._file_index, self._hunk_index, self._stage = index, None, "detail"
            self._render_view()
            self.query_one(TextArea).focus()

    def action_back(self) -> None:
        if self._busy:
            return
        self._plan = None
        if self._stage == "catalog":
            self.dismiss(None)
            return
        if self._stage == "checks":
            self._stage = self._return_stage
        else:
            self._stage = {"preview": "detail", "detail": "files", "files": "catalog"}[self._stage]
        if self._stage == "catalog":
            self._review = None
        self._render_list()
        self._render_view()
        self.query_one(TextArea if self._stage == "detail" else OptionList).focus()

    def _hunk(self, delta: int) -> None:
        if self._busy or self._stage != "detail" or self._review is None:
            return
        hunks = self._review.files[self._file_index].hunks
        if hunks:
            index = (self._hunk_index + delta) % len(hunks) if self._hunk_index is not None else (0 if delta > 0 else len(hunks) - 1)
            self._hunk_index = hunks[index].index
            self._render_view()

    def action_next_hunk(self) -> None:
        self._hunk(1)

    def action_previous_hunk(self) -> None:
        self._hunk(-1)

    def action_whole_file(self) -> None:
        if not self._busy and self._stage == "detail":
            self._hunk_index = None
            self._render_view()

    def _preview(self, decision: str) -> None:
        if self._busy or self._stage != "detail" or self._review is None or self._pending or self._refresh_required:
            return
        review, hunk = self._review, self._hunk_index
        file = review.files[self._file_index]
        if not file.restorable:
            return
        async def preview() -> None:
            plan = await _joined(lambda: self._service().preview(review.checkpoint_id, decision=decision,
                paths=[file.path] if hunk is None else None, hunks={file.path: [hunk]} if hunk is not None else None))
            if plan.revision != review.revision:
                raise ValueError("Review revision changed. Refresh and select the decision again.")
            self._plan, self._stage = plan, "preview"
            self._status = "Preview only. Apply requires idle work and rechecks current content."
            self.query_one("#checkpoint-back", Button).focus()
        self._launch(preview)

    def action_preview_accept(self) -> None:
        self._preview("accept")

    def action_preview_reject(self) -> None:
        self._preview("reject")

    def action_retain_draft(self) -> None:
        """Do not route the underlying composer's submit shortcut through review."""

    def action_apply(self) -> None:
        if self._busy or self._plan is None or self._stage != "preview":
            return
        plan = self._plan
        async def apply() -> None:
            require_idle(self.runtime, self.root)
            registry = getattr(getattr(self.runtime, "core_context", None), "tool_registry", None)
            async with AsyncExitStack() as stack:
                if registry is not None:
                    await stack.enter_async_context(registry._effective_formatter._lock)
                require_idle(self.runtime, self.root)
                def change() -> Any:
                    require_idle(self.runtime, self.root)
                    return self._service().apply(plan.plan_id)
                result = await _joined(change)
            self._stage = "detail"
            await self._reload()
            self._status = f"Applied {plan.decision}; {len(result.changed_paths)} changed file(s)." + (
                " Recorded checks are now stale." if result.invalidate_checks else " No file bytes changed.")
        self._launch(apply)

    def action_checks(self) -> None:
        if self._busy:
            return
        self._checks = ""
        async def checks() -> None:
            self._require_checks_binding()
            assert self._checks_settings is not None
            settings = self._checks_settings
            configuration = settings.verification.model_dump(mode="json")
            self._checks_policy.register_policy(_current_policy(self.runtime))
            def read() -> tuple[list[tuple[PlanRecord, dict[str, object]]], int]:
                service = PlanExecutionService(self.root, settings=settings, redactor=self._checks_policy)
                plans = service.list_plans()
                observations = []
                for plan in plans[-_CHECK_PLAN_LIMIT:]:
                    current = service.verification_status(plan.plan_id)
                    if service.get_plan(plan.plan_id) != plan:
                        raise ValueError("Check evidence changed during inspection. Refresh to inspect it again.")
                    observations.append((plan, current))
                return observations, max(0, len(plans) - _CHECK_PLAN_LIMIT)
            observations, omitted = await _joined(read)
            self._require_checks_binding()
            if settings.verification.model_dump(mode="json") != configuration:
                raise ValueError("Required check configuration changed during inspection. Refresh to inspect it again.")
            self._checks_policy.register_policy(_current_policy(self.runtime))
            lines = ["PROJECT CHECKS — not bound to the selected checkpoint or operation.",
                     "Read-only freshness observations over declared inputs; Refresh rechecks without executing checks.",
                     "Historical outcomes are retained separately. Task acceptance is not established."]
            if omitted:
                lines.append(f"{omitted} earlier plan(s) omitted; inspecting the most recent {_CHECK_PLAN_LIMIT}.")
            for plan, current in observations:
                report = plan.last_verification
                status = str(report.get("status", "unknown")) if report else "not-run"
                if status == "finished":
                    status = "recorded pass" if report and report.get("checks_passed") is True else "recorded fail"
                lines.extend([f"\n{plan.plan_id}: {plan.title}",
                              f"Current status: {current['status']} · freshness: {current['freshness']} · configuration: {current['configuration_status']}",
                              json.dumps(self._checks_policy.redact(current), ensure_ascii=True, indent=2),
                              f"Historical result: {status}",
                              json.dumps(self._checks_policy.redact(report), ensure_ascii=True, indent=2) if report else "Checks have not run."])
            if not observations:
                lines.append("No recorded project checks.")
            self._checks = self._checks_policy.text("\n".join(lines))
            self._status = "Check freshness inspected without execution. Refresh to inspect current contents again."
            self._return_stage = self._stage if self._stage != "checks" else self._return_stage
            if self._return_stage == "preview":
                self._return_stage = "detail"
            self._stage = "checks"
            self._plan = None
        self._launch(checks)

    @on(Button.Pressed)
    def _button(self, event: Button.Pressed) -> None:
        event.stop()
        actions = {"checkpoint-back": self.action_back, "checkpoint-refresh": self.action_refresh,
                   "checkpoint-checks": self.action_checks, "checkpoint-accept": self.action_preview_accept,
                   "checkpoint-reject": self.action_preview_reject, "checkpoint-apply": self.action_apply}
        action = actions.get(event.button.id or "")
        if action is not None:
            action()
