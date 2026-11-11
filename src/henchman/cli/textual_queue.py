"""Revision-bound user queue controls over the shared workflow service."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any, ClassVar, Literal, TypeVar

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, OptionList, Static, TextArea
from textual.widgets.option_list import Option

from henchman.cli.evidence import runtime_evidence_redactor, runtime_exception_text
from henchman.core.session_workflow import QueueControlView, SessionWorkflow
from henchman.core.workflow_state import QueuedInput, WorkflowError

_T = TypeVar("_T")


async def _read_owned(read: Callable[[], _T]) -> _T:
    worker = asyncio.create_task(asyncio.to_thread(read))
    cancelled: asyncio.CancelledError | None = None
    while not worker.done():
        try:
            await asyncio.shield(worker)
        except asyncio.CancelledError as error:
            cancelled = cancelled or error
        except BaseException:
            break
    if cancelled is not None:
        try:
            worker.result()
        except BaseException:
            cancelled.add_note("Queue inspection also failed during joined cleanup")
        raise cancelled
    return worker.result()


class QueueScreen(ModalScreen[None]):
    """Inspect saved intent; only explicit current Send can grant eligibility."""

    DEFAULT_CSS = """
    QueueScreen { background: $surface; }
    #queue-dialog { width: 100%; height: 100%; padding: 0 1; }
    #queue-title { height: 1; text-style: bold; }
    #queue-summary { height: 2; }
    #queue-status { height: 3; color: $warning; }
    #queue-body { height: 1fr; }
    #queue-list { width: 32; height: 1fr; border: solid $accent; }
    #queue-content { width: 1fr; height: 1fr; }
    #queue-actions { height: 3; }
    #queue-actions Button { min-width: 6; width: 1fr; margin: 0; padding: 0; }
    #queue-hints { height: 1; }
    QueueScreen.narrow #queue-list { width: 1fr; }
    """
    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        Binding("escape", "back", "Back", priority=True),
        Binding("f5", "refresh", "Refresh", priority=True),
        Binding("ctrl+enter", "save", "Save edit", priority=True),
    ]

    def __init__(self, runtime: Any, workflow: SessionWorkflow) -> None:
        super().__init__()
        self.runtime, self.workflow = runtime, workflow
        self._view: QueueControlView | None = None
        self._ids: list[str] = []
        self._selected_id: str | None = None
        self._stage = "list"
        self._status = "Loading saved inputs…"
        self._busy = False
        self._queue_closing = False
        self._refresh_required = False
        self._action_task: asyncio.Task[None] | None = None
        self._edit_seed = ""
        self._option_labels: list[str] = []

    def compose(self) -> ComposeResult:
        with Vertical(id="queue-dialog"):
            yield Static("Saved input queue", markup=False, id="queue-title")
            yield Static("", markup=False, id="queue-summary")
            yield Static("", markup=False, id="queue-status")
            with Horizontal(id="queue-body"):
                yield OptionList(id="queue-list")
                yield TextArea(read_only=True, soft_wrap=True, show_line_numbers=False, id="queue-content")
            with Horizontal(id="queue-actions"):
                for label, name in [("Back", "back"), ("Refresh", "refresh"), ("Edit", "edit"),
                                    ("Remove…", "remove"), ("Up", "up"), ("Down", "down"), ("Send", "send"),
                                    ("Save", "save"), ("Remove", "confirm-remove"),
                                    ("Discard", "discard"), ("Keep edit", "keep")]:
                    yield Button(label, id=f"queue-{name}")
            yield Static("Enter inspect · Tab actions · F5 refresh · Esc Back", markup=False, id="queue-hints")

    def on_mount(self) -> None:
        self.action_refresh()
        self.query_one(OptionList).focus()
        self.set_interval(0.25, self._project_current)

    def on_resize(self) -> None:
        if self.is_mounted:
            self._layout()

    async def on_unmount(self) -> None:
        self._queue_closing = True
        if self._action_task is not None and not self._action_task.done():
            self._action_task.cancel()
            await asyncio.gather(self._action_task, return_exceptions=True)

    def on_screen_suspend(self) -> None:
        """A new decision invalidates old controls even if it closes quickly."""
        self._refresh_required = True
        if self._action_task is not None and not self._action_task.done():
            self._action_task.cancel()

    def _admit(self) -> None:
        prompts = getattr(self.runtime, "_tool_prompts", None)
        answer = getattr(prompts, "_answer", None)
        task = getattr(self.runtime, "current_agent_task", None)
        if (self._queue_closing or not self.runtime.is_running or self.runtime.screen is not self
            or self.runtime._workflow() is not self.workflow or getattr(prompts, "_closed", False)
            or (isinstance(answer, asyncio.Future) and not answer.done())
            or (isinstance(task, asyncio.Task) and task.cancelling())):
            raise WorkflowError("queue_controls_changed")

    def _safe(self, text: str) -> str:
        raw = runtime_evidence_redactor(self.runtime).text(text).encode("utf-8", errors="replace")
        return raw[:65536].decode("utf-8", errors="ignore") + ("\n[Display omitted beyond 64 KiB]" if len(raw) > 65536 else "")

    def _admit_control(self) -> None:
        self._admit()
        if self._refresh_required:
            raise WorkflowError("queue_controls_changed")

    def _record(self) -> QueuedInput | None:
        return next((item for item in self._view.report.state.inputs if item.id == self._selected_id), None) if self._view else None

    def _disposition(self, item: QueuedInput) -> str:
        assert self._view is not None
        if item.state == "queued":
            if item.kind == "goal":
                return "Goal continuation · use /goal resume"
            if self._view.report.failure_reason:
                return "Held · workflow storage error"
            if self._view.report.blocking_input_ids:
                return "Held · unresolved earlier effects"
            return "Queued next turn" if (item.id, item.revision) in self._view.eligible else "Held · explicit Send required"
        if item.state == "started" and item.id == self._view.active_input_id:
            return "Currently dispatched"
        if item.state == "outcome_unknown":
            return "Uncertain effects" + (" · abandoned" if item.resolution else " · inspect /recovery")
        if item.state == "completed":
            return f"Completed input · {item.outcome} (not requirements acceptance)"
        return "Removed before dispatch"

    def _option_label(self, index: int, item: QueuedInput) -> str:
        preview = self._safe(item.preview).replace("\n", " ")
        return f"{index + 1}. {self._disposition(item)}\n{preview[:160]}" + ("…" if len(preview) > 160 else "")

    async def _load(self) -> None:
        view = await _read_owned(self.workflow.queue_view)
        self._admit()
        self._view = view
        self._refresh_required = False
        records = sorted(view.report.state.inputs, key=lambda item: item.order)
        self._ids = [item.id for item in records]
        if self._selected_id not in self._ids:
            self._selected_id = self._ids[0] if self._ids else None
        options = self.query_one(OptionList)
        options.clear_options()
        self._option_labels = [self._option_label(i, item) for i, item in enumerate(records)]
        options.add_options([Option(Text(label)) for label in self._option_labels])
        if self._selected_id is not None:
            options.highlighted = self._ids.index(self._selected_id)
        if self._status == "Loading saved inputs…":
            self._status = "Snapshot of current input; Refresh updates it. Opening the queue grants no permission."
        self._render_view()

    def _launch(self, action: Callable[[], Awaitable[None]]) -> None:
        if self._busy or self._queue_closing:
            return
        self._busy = True
        self._render_view()

        async def owned() -> None:
            try:
                await action()
            except asyncio.CancelledError:
                self._refresh_required = True
                self._status = "Action interrupted; inspect current storage state before another decision."
                raise
            except Exception as error:
                self._refresh_required = True
                self._status = self._safe(runtime_exception_text(self.runtime, error)) + ". Refresh before another decision. A committed change is not rolled back."
            finally:
                self._busy = False
                if self.is_mounted and not self._queue_closing:
                    self._render_view()

        self._action_task = asyncio.create_task(owned())

    def action_refresh(self) -> None:
        if self._stage in {"edit", "discard-edit"}:
            self._status = "Keep or discard the unsaved edit before refreshing."
            self._render_view()
            return
        self._launch(self._load)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if self._busy or event.option_index >= len(self._ids):
            return
        self._selected_id = self._ids[event.option_index]
        self._stage = "detail"
        self._status = "Edit and reorder leave input held. Send explicitly allows a future turn."
        self._render_view()
        self.query_one("#queue-content", TextArea).focus()

    def _project_current(self) -> None:
        if self._queue_closing or not self.is_mounted:
            return
        if self._view is not None:
            records = {item.id: item for item in self._view.report.state.inputs}
            for index, identity in enumerate(self._ids):
                item = records[identity]
                label = self._option_label(index, item)
                if label != self._option_labels[index]:
                    self.query_one(OptionList).replace_option_prompt_at_index(index, Text(label))
                    self._option_labels[index] = label
        if self._stage in {"edit", "discard-edit"}:
            editor = self.query_one("#queue-content", TextArea)
            if editor.text == self._edit_seed and self._safe(self._edit_seed) != self._edit_seed:
                editor.load_text("")
                self._edit_seed = ""
                self._status = "Saved text became credential-sensitive. Enter a complete replacement; no masked preview will be saved."
                self._render_view()
        else:
            self._render_view()

    def _render_view(self) -> None:
        if not self.is_mounted:
            return
        view, record = self._view, self._record()
        summary = f"{len(self._ids)} saved inputs · {view.report.persistence} persistence" if view else "No queue snapshot"
        self.query_one("#queue-summary", Static).update(summary + "\nComposer remains an unsent draft. Queue changes never answer approvals.")
        self.query_one("#queue-status", Static).update(self._safe("Working; Back cancels and joins storage…" if self._busy else self._status))
        editor = self.query_one("#queue-content", TextArea)
        editing = self._stage in {"edit", "discard-edit"}
        editor.read_only = self._stage != "edit"
        if not editing:
            content = "Select an input to inspect. No input is dispatched by opening this screen."
            if record is not None:
                content = f"{self._disposition(record)}\nKind: {record.kind}\n\n{record.preview}"
                if record.availability != "complete":
                    content += "\n\nOriginal text unavailable in evidence. Edit requires a complete replacement."
                if record.state == "outcome_unknown":
                    content += "\n\nInspect /recovery and background tasks; this screen cannot replay or abandon uncertain effects."
                if self._stage == "remove":
                    content = "Remove this undispatched input? This does not undo earlier effects.\n\n" + content
            safe = self._safe(content)
            if editor.text != safe:
                editor.load_text(safe)
        available = bool(record and record.state == "queued" and not self._refresh_required and view and not view.busy)
        for button in self.query(Button):
            name = (button.id or "").removeprefix("queue-")
            button.display = name in {"back", "refresh"} or (
                self._stage == "detail" and name in {"edit", "remove", "up", "down", "send"}
                or self._stage == "edit" and name == "save"
                or self._stage == "remove" and name == "confirm-remove"
                or self._stage == "discard-edit" and name in {"discard", "keep"})
            button.disabled = self._busy and name != "back" or (name not in {"back", "refresh", "discard", "keep"} and not available)
            if record and name in {"send", "edit", "save"} and (record.kind == "goal" or not record.role_available):
                button.disabled = True
            if record and view and name in {"up", "down"}:
                pending = sorted((item for item in view.report.state.inputs if item.state == "queued"), key=lambda item: item.order)
                if record not in pending or pending.index(record) == (0 if name == "up" else len(pending) - 1):
                    button.disabled = True
        self._layout()

    def _layout(self) -> None:
        narrow = self.size.width < 100
        self.set_class(narrow, "narrow")
        self.query_one(OptionList).display = not narrow or self._stage == "list"
        self.query_one("#queue-content", TextArea).display = not narrow or self._stage != "list"

    def action_edit(self) -> None:
        record = self._record()
        if self._busy or self._refresh_required or record is None or record.state != "queued" or record.kind == "goal" or not record.role_available:
            return
        try:
            self._admit_control()
        except WorkflowError:
            self._refresh_required = True
            self._status = "Queue controls changed. Refresh before editing."
            self._render_view()
            return
        policy = runtime_evidence_redactor(self.runtime)
        self._edit_seed = record.text if record.text is not None and policy.text(record.text) == record.text else ""
        self._stage = "edit"
        self._status = "Save replaces the complete input and leaves it held. Back preserves the composer draft."
        self.query_one("#queue-content", TextArea).load_text(self._edit_seed)
        self._render_view()
        self.query_one("#queue-content", TextArea).focus()

    def _change(self, action: Literal["send", "edit", "drop", "move"], *, text: str | None = None, position: int | None = None) -> None:
        record, view = self._record(), self._view
        if self._refresh_required or record is None or view is None:
            return

        async def mutate() -> None:
            await self.workflow.control_queue(view, record.id, record.revision, action, text=text, position=position, guard=self._admit_control)
            self._stage = "detail"
            self._status = ({"send": "Send recorded for a future turn.",
                             "drop": "Input removed before dispatch. Earlier effects are unchanged."}
                            .get(action, "Change saved; input stays held until explicit Send."))
            if action == "send":
                self.runtime._schedule_queue_dispatch(self.workflow)
            await self._load()

        self._launch(mutate)

    def action_save(self) -> None:
        if self._stage == "edit":
            self._change("edit", text=self.query_one("#queue-content", TextArea).text)

    def action_send(self) -> None:
        if self._stage == "detail":
            self._change("send")

    def action_move(self, offset: int) -> None:
        record = self._record()
        if record is None or self._view is None or self._stage != "detail":
            return
        pending = sorted((item for item in self._view.report.state.inputs if item.state == "queued"), key=lambda item: item.order)
        if record not in pending:
            return
        position = pending.index(record) + offset
        if 0 <= position < len(pending):
            self._change("move", position=position)

    def action_remove(self) -> None:
        if not self._busy and not self._refresh_required and self._stage == "detail":
            self._stage = "remove"
            self._render_view()
            self.query_one("#queue-back", Button).focus()

    def action_confirm_remove(self) -> None:
        if self._stage == "remove":
            self._change("drop")

    async def action_back(self) -> None:
        if self._busy:
            self._queue_closing = True
            if self._action_task is not None:
                self._action_task.cancel()
                await asyncio.gather(self._action_task, return_exceptions=True)
            self.dismiss()
        elif self._stage == "edit":
            self._stage = "discard-edit"
            self._render_view()
            self.query_one("#queue-keep", Button).focus()
        elif self._stage in {"remove", "discard-edit"}:
            self._stage = "detail" if self._stage == "remove" else "edit"
            self._render_view()
        elif self._stage == "detail":
            self._stage = "list"
            self._render_view()
            self.query_one(OptionList).focus()
        else:
            self._queue_closing = True
            self.dismiss()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        name = (event.button.id or "").removeprefix("queue-")
        if name == "back":
            await self.action_back()
        elif name == "refresh":
            self.action_refresh()
        elif name == "edit":
            self.action_edit()
        elif name == "save":
            self.action_save()
        elif name == "send":
            self.action_send()
        elif name in {"up", "down"}:
            self.action_move(-1 if name == "up" else 1)
        elif name == "remove":
            self.action_remove()
        elif name == "confirm-remove":
            self.action_confirm_remove()
        elif name in {"keep", "discard"}:
            self._stage = "edit" if name == "keep" else "detail"
            self._render_view()
