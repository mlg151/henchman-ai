"""Bounded inspection and explicit interruption of owned project tasks."""
from __future__ import annotations

import asyncio
from typing import Any, ClassVar

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, OptionList, Static, TextArea
from textual.widgets.option_list import Option

from henchman.cli.inspection_runtime import _current_policy, _joined
from henchman.cli.work_inspection import (
    _EVIDENCE_BYTES,
    _ROWS,
    WorkInspection,
    WorkRow,
    _task_details,
)
from henchman.cli.work_inspection import (
    bound_task_service as bound_task_service,
)
from henchman.utils.evidence_redaction import EvidenceRedactor
from henchman.utils.exception_evidence import exception_text


class _WorkDetails(TextArea):
    def action_copy(self) -> None:
        screen = self.screen
        if isinstance(screen, WorkInspector):
            previous = self.text
            screen._render_view()
            if self.text != previous:
                screen._status = "Credential projection changed; select the text again before copying."
                screen._render_view()
                return
            screen._copy(self.selected_text)


class WorkInspector(ModalScreen[None]):
    """Inspect work and stop an explicitly selected, locally owned task."""

    DEFAULT_CSS = """
    WorkInspector { background: $surface; }
    #work-dialog { width: 100%; height: 100%; padding: 0 1; }
    #work-title { height: 1; text-style: bold; }
    #work-status { height: 3; }
    #work-body { height: 1fr; }
    #work-list { width: 38; height: 1fr; border: solid $accent; }
    #work-detail { width: 1fr; height: 1fr; }
    #work-actions { height: 3; }
    #work-actions Button { min-width: 9; width: 1fr; margin: 0; }
    #work-hint { height: 1; }
    WorkInspector.narrow #work-list { width: 1fr; }
    """
    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        Binding("escape", "back", "Back", priority=True),
        Binding("f5", "refresh", "Refresh", priority=True),
        Binding("f6", "stop_task", "Stop task", priority=True),
    ]

    def __init__(self, runtime: Any) -> None:
        super().__init__()
        self.runtime = runtime
        self._inspection = WorkInspection(runtime)
        self.root = self._inspection.root
        self.service = self._inspection.service
        self.agents = self._inspection.agents
        self._policy = self._inspection._policy
        self._captured = self._identity()
        self._rows: tuple[WorkRow, ...] = ()
        self._fields: tuple[tuple[str, str], ...] = ()
        self._output_interrupted = False
        self._stage = "list"
        self._status = "Loading owned work observations…"
        self._action_task: asyncio.Task[None] | None = None
        self._busy = False
        self._work_closing = False
        self._stale = False
        self._selection = 0
        self._stop_target: tuple[str, int, int, int] | None = None

    def _identity(self) -> tuple[Any, ...]:
        return self._inspection.identity()

    def _admit(self) -> None:
        if self._work_closing or self._stale or self.runtime.screen is not self or self._captured != self._identity():
            raise ValueError("Work owner, project or session changed; close and reopen inspection")

    def _refresh_policy(self) -> EvidenceRedactor:
        return self._inspection._refresh_policy()

    def _safe(self, value: str, limit: int = _EVIDENCE_BYTES, *, interrupted: bool = False) -> str:
        return self._inspection.safe(value, limit, interrupted=interrupted)

    def compose(self) -> ComposeResult:
        with Vertical(id="work-dialog"):
            yield Static("Tasks and agents · observed state, not task verification", markup=False, id="work-title")
            yield Static(self._status, markup=False, id="work-status")
            with Horizontal(id="work-body"):
                yield OptionList(id="work-list")
                yield _WorkDetails(read_only=True, soft_wrap=True, id="work-detail")
            with Horizontal(id="work-actions"):
                yield Button("Back", id="work-back")
                yield Button("Refresh", id="work-refresh")
                yield Button("Inspect", id="work-inspect")
                yield Button("Copy", id="work-copy")
                yield Button("Stop task", id="work-stop")
            yield Static("Enter inspects · Esc goes back · F5 refreshes · F6 stops selected task", markup=False, id="work-hint")

    def on_mount(self) -> None:
        self.query_one(OptionList).focus()
        self.action_refresh()
        self.set_interval(0.5, self._render_view)

    def on_resize(self) -> None:
        if self.is_mounted:
            self._layout()

    def _layout(self) -> None:
        narrow = self.size.width < 100
        self.set_class(narrow, "narrow")
        self.query_one(OptionList).display = not narrow or self._stage == "list"
        self.query_one(TextArea).display = not narrow or self._stage == "detail"

    def _render_view(self) -> None:
        if not self.is_mounted:
            return
        self._refresh_policy()
        labels = self._inspection.labels(self._rows)
        options = self.query_one(OptionList)
        if labels != getattr(self, "_labels", None):
            self._labels = labels
            selected = options.highlighted
            options.clear_options()
            options.add_options([Option(Text(label)) for label in labels])
            options.highlighted = min(selected or 0, len(labels) - 1) if labels else None
        text = self._inspection.details(self._fields, interrupted=self._output_interrupted)
        area = self.query_one(TextArea)
        if area.text != text:
            area.load_text(text)
        self.query_one("#work-status", Static).update(self._safe(self._status))
        for name in ("refresh", "inspect"):
            self.query_one("#work-" + name, Button).disabled = self._busy or self._stale or self._work_closing
        self.query_one("#work-copy", Button).disabled = not self._fields
        target = self._stop_target
        self.query_one("#work-stop", Button).disabled = (
            self._busy or self._stale or self._work_closing or self._stage != "detail"
            or target is None or target[2] != options.highlighted or target[3] != self._selection
        )
        self._layout()

    def _run(self, action: Any) -> None:
        if self._busy or self._work_closing:
            return
        self._busy = True
        async def owned() -> None:
            try:
                self._admit()
                await action()
            except asyncio.CancelledError:
                raise
            except Exception as error:
                self._status = exception_text(error, self._refresh_policy())
            finally:
                self._busy = False
                self._render_view()
        self._action_task = asyncio.create_task(owned())
        self._render_view()

    def action_refresh(self) -> None:
        async def refresh() -> None:
            rows, notice = await self._inspection.catalog(limit=_ROWS)
            self._admit()
            self._rows = rows
            self._fields = ()
            self._stop_target = None
            self._stage = "list"
            self._selection += 1
            self._status = notice
        self._run(refresh)

    def action_inspect(self) -> None:
        index = self.query_one(OptionList).highlighted
        if index is None or index >= len(self._rows):
            return
        row, selection = self._rows[index], self._selection
        async def inspect() -> None:
            self._fields = ()
            self._stop_target = None
            self._output_interrupted = False
            self._render_view()
            fields, self._output_interrupted = await self._inspection.inspect(row.kind, row.identity, task_reader=_task_details)
            self._admit()
            if self._selection != selection or self.query_one(OptionList).highlighted != index:
                raise ValueError("Selection changed during inspection; inspect it again")
            self._fields = fields
            self._stage = "detail"
            values = dict(fields)
            if (row.kind == "task" and (values.get("State") == "running"
                or (values.get("State") == "outcome_unknown" and self.service is not None
                    and self.service._owns_live_process(row.identity)))):
                self._stop_target = (row.identity, int(values["Revision"]), index, selection)
            self._status = "Captured observation. Work continues independently; Refresh reads current state."
            self._render_view()
            self.query_one(TextArea).focus()
        self._run(inspect)

    def action_stop_task(self) -> None:
        target = self._stop_target
        if target is None:
            return
        identity, revision, index, selection = target

        def selection_current() -> None:
            self._admit()
            if (self._stage != "detail" or self._stop_target != target
                or self._selection != selection or self.query_one(OptionList).highlighted != index):
                raise ValueError("Selection changed; inspect the task again")

        async def stop() -> None:
            selection_current()
            self._status = "Checking task ownership before stopping."
            self._render_view()

            def requested() -> None:
                self._status = "Stop requested; checking owner, then waiting for cleanup."
                self._render_view()

            result = await self._inspection.interrupt_task(
                identity, expected_revision=revision, selection_current=selection_current, on_requested=requested,
            )
            self._stop_target = None
            self._fields = (("Task", identity), ("State", result.status))
            self._output_interrupted = result.status != "completed"
            self._status = (
                "Task stopped; owned process and capture cleanup completed."
                if result.status == "stopped"
                else f"Stop request settled with state {result.status}; refresh for details."
            )

        self._run(stop)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        event.stop()
        self.action_inspect()

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        event.stop()
        self._selection += 1

    def _copy(self, text: str) -> None:
        try:
            self._admit()
            self.runtime.copy_to_clipboard(text)
            self._status = "Clipboard transfer requested; terminal receipt is unconfirmed."
        except Exception as error:
            self._status = exception_text(error, self._refresh_policy())
        self._render_view()

    def action_copy(self) -> None:
        self._render_view()
        self._copy(self.query_one(TextArea).text)

    def on_screen_suspend(self) -> None:
        self._stale = True
        if self._action_task is not None and not self._action_task.done():
            self._action_task.cancel()

    async def on_unmount(self) -> None:
        self._work_closing = True
        if self._action_task is not None and not self._action_task.done():
            task = self._action_task
            task.cancel()
            async def settle() -> None:
                await asyncio.gather(task, return_exceptions=True)
            await _joined(asyncio.create_task(settle()))

    async def action_back(self) -> None:
        if self._stage == "detail" and not self._busy:
            self._stage = "list"
            self._layout()
            self.query_one(OptionList).focus()
            return
        await self.on_unmount()
        if self.is_mounted:
            self.dismiss(None)

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        if event.button.id == "work-back":
            await self.action_back()
        elif event.button.id == "work-refresh":
            self.action_refresh()
        elif event.button.id == "work-inspect":
            self.action_inspect()
        elif event.button.id == "work-copy":
            self.action_copy()
        elif event.button.id == "work-stop":
            self.action_stop_task()


def open_work_inspector(runtime: Any) -> None:
    """Open the captured current project without displacing a pending decision."""
    prompt = getattr(getattr(runtime, "_tool_prompts", None), "_answer", None)
    if len(runtime.screen_stack) != 1 or prompt is not None:
        runtime.notify("Close the current dialog first; F4 returns to a pending decision.", markup=False)
        return
    focused = runtime.focused
    def restore_focus(_value: None) -> None:
        if focused is not None and focused.is_mounted:
            focused.focus()
    try:
        runtime.push_screen(WorkInspector(runtime), restore_focus)
    except (OSError, ValueError) as error:
        runtime.notify(exception_text(error, _current_policy(runtime)), severity="error", markup=False)
