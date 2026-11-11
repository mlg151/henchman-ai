"""Immutable ordinary transcript records and a bounded, explicit DOM window.

The limit applies to finished ordinary messages. Active streams and interactive
thought/tool controls stay pinned; this is not a total memory or widget cap.
"""

from __future__ import annotations

import asyncio
import weakref
from contextlib import suppress
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any

from rich.markup import escape
from textual.content import Content
from textual.markup import MarkupError
from textual.widget import Widget
from textual.widgets import Button, Static
from textual.worker import Worker, WorkerCancelled

from henchman.cli.evidence import runtime_evidence_redactor

if TYPE_CHECKING:
    from collections.abc import Iterator

    from henchman.cli.textual_widgets import ChatMessage, ChatPane
    from henchman.utils.evidence_redaction import EvidenceRedactor

ORDINARY_WINDOW = 128


@dataclass(frozen=True, slots=True)
class MessageSnapshot:
    row_id: int
    prefix: str
    content: str
    trusted: bool
    markdown: bool
    output_mode: str
    hidden: bool


@dataclass(frozen=True, slots=True)
class TranscriptRow:
    row_id: int
    kind: str
    content: str
    tool_activity: Any = None


class HistoryButton(Button):
    """A page control whose action does not move focus out of the composer."""

    def __init__(self, window: TranscriptWindow, *, previous: bool) -> None:
        super().__init__(id="transcript-earlier" if previous else "transcript-later")
        self._window = weakref.ref(window)
        self._previous = previous

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        if (window := self._window()) is not None:
            window.page(-1 if self._previous else 1)


class TranscriptWindow:
    """Own immutable records, with references only to mounted or pending rows."""

    def __init__(self, pane: ChatPane) -> None:
        self._pane = weakref.ref(pane)
        self.records: dict[int, MessageSnapshot | str] = {}
        self.widgets: dict[int, Static] = {}
        self.pending: dict[int, Static] = {}
        self.pinned: set[int] = set()
        self._next_id = 0
        self._epoch = 0
        self._queued = False
        self._dirty = False
        self._syncing = False
        self._closed = False
        self._worker: Worker[None] | None = None
        self._close_task: asyncio.Task[None] | None = None
        self._start: int | None = None
        self._reveal: int | None = None
        self.highlight = ""
        self._controls: list[Widget] = []
        self._control_map: dict[tuple[Any, ...], Widget] = {}
        self._control_labels: dict[tuple[Any, ...], str] = {}

    @property
    def pane(self) -> ChatPane:
        pane = self._pane()
        if pane is None:
            raise RuntimeError("Transcript owner is unavailable")
        return pane

    def add(self, widget: Static, *, active: bool = False) -> None:
        from henchman.cli.textual_widgets import ChatMessage

        row_id = self._next_id
        self._next_id += 1
        widget._transcript_row_id = row_id  # type: ignore[attr-defined]
        widget._transcript_owner = weakref.ref(self)  # type: ignore[attr-defined]
        widget._transcript_epoch = self._epoch  # type: ignore[attr-defined]
        if isinstance(widget, ChatMessage):
            self.records[row_id] = self._snapshot(widget, row_id)
        else:
            self.records[row_id] = type(widget).__name__
            active = True
        if active:
            self.pinned.add(row_id)
        self.pending[row_id] = widget
        # A burst can contain thousands of rows before the message loop yields.
        # Never retain all those unmounted Widget graphs in a deferred callback.
        ordinary = [key for key in self.pending if key not in self.pinned]
        for key in ordinary[:-ORDINARY_WINDOW]:
            self.pending.pop(key)
        self.schedule()

    @staticmethod
    def _snapshot(widget: ChatMessage, row_id: int) -> MessageSnapshot:
        return MessageSnapshot(row_id, widget._prefix, widget._content_text,
                               widget._trusted, widget._is_markdown,
                               widget._output_mode, not widget.display)

    def update_content(self, widget: ChatMessage, content: str, *, append: bool) -> bool:
        row_id = getattr(widget, "_transcript_row_id", -1)
        record = self.records.get(row_id)
        if getattr(widget, "_transcript_epoch", -1) != self._epoch or not isinstance(record, MessageSnapshot):
            return False
        updated = replace(record, content=record.content + content if append else content)
        self.records[row_id] = updated
        policy = runtime_evidence_redactor(self.pane.app)
        self._project_widget(widget, updated, policy)
        self.schedule()
        return True

    def finish(self, widget: ChatMessage) -> None:
        row_id = getattr(widget, "_transcript_row_id", -1)
        record = self.records.get(row_id)
        if isinstance(record, MessageSnapshot):
            self.records[row_id] = replace(record, markdown=widget._is_markdown)
        self.pinned.discard(row_id)
        self.schedule()

    def discard(self, widget: Static) -> None:
        widget.display = False
        if not self.owns(widget):
            return
        row_id = getattr(widget, "_transcript_row_id", -1)
        self.records.pop(row_id, None)
        self.widgets.pop(row_id, None)
        self.pending.pop(row_id, None)
        self.pinned.discard(row_id)
        if self.pane._reading_anchor is not None and self.pane._reading_anchor[0] is widget:
            self.pane._reading_anchor = None
        self.schedule()

    def owns(self, widget: Widget) -> bool:
        """Check the exact row identity, including mounts already in progress."""
        key = getattr(widget, "_transcript_row_id", -1)
        return (not self._closed and getattr(widget, "_transcript_epoch", -1) == self._epoch
                and key in self.records
                and (self.widgets.get(key) is widget or self.pending.get(key) is widget))

    def owned_widgets(self) -> tuple[Static, ...]:
        """Include rows awaiting mount without retaining an extra widget cache."""
        return tuple(dict.fromkeys((*self.widgets.values(), *self.pending.values())))

    def clear(self) -> None:
        self._epoch += 1
        self.records.clear()
        self.widgets.clear()
        self.pending.clear()
        self.pinned.clear()
        self._controls.clear()
        self._control_map.clear()
        self._control_labels.clear()
        self._start = None
        self._reveal = None
        self.schedule()

    def ordinary(self) -> list[int]:
        return [key for key, record in self.records.items()
                if isinstance(record, MessageSnapshot) and key not in self.pinned]

    def _bounds(self, ordinary: list[int]) -> tuple[int, int]:
        start = max(0, len(ordinary) - ORDINARY_WINDOW) if self._start is None else self._start
        start = min(start, max(0, len(ordinary) - 1))
        return start, min(len(ordinary), start + ORDINARY_WINDOW)

    def hold(self) -> None:
        if self._start is None:
            self._start = self._bounds(self.ordinary())[0]

    def can_page(self, direction: int) -> bool:
        ordinary = self.ordinary()
        start, end = self._bounds(ordinary)
        return start > 0 if direction < 0 else end < len(ordinary)

    def page(self, direction: int) -> None:
        ordinary = self.ordinary()
        start, _ = self._bounds(ordinary)
        self.pane.hold_reading_position()
        self._start = max(0, min(max(0, len(ordinary) - ORDINARY_WINDOW), start + direction * ORDINARY_WINDOW))
        selected = ordinary[self._start:self._start + ORDINARY_WINDOW]
        self._reveal = selected[0] if selected else None
        self.schedule()

    def live(self) -> None:
        self._start = None
        self._reveal = None
        self.schedule()

    def reveal(self, row_id: int) -> None:
        if row_id not in self.records:
            return
        self.pane.hold_reading_position()
        ordinary = self.ordinary()
        if row_id in ordinary:
            index = ordinary.index(row_id)
            self._start = min(index, max(0, len(ordinary) - ORDINARY_WINDOW))
        self._reveal = row_id
        self.schedule()

    def rows(self, *, reverse: bool = False) -> Iterator[TranscriptRow]:
        policy = runtime_evidence_redactor(self.pane.app)
        keys: Iterator[int] = iter(self.records.keys())
        if reverse:
            keys = reversed(self.records.keys())
        for key in keys:
            record = self.records[key]
            if isinstance(record, MessageSnapshot):
                content = (self._trusted_projection(record.content, policy, markup=False)
                           if record.trusted else policy.text(record.content))
                yield TranscriptRow(key, "ChatMessage", content)
            elif (widget := self.widgets.get(key) or self.pending.get(key)) is not None:
                activity = getattr(widget, "activity", None)
                content = activity.evidence(policy) if activity is not None else policy.text(getattr(widget, "_content_text", ""))
                yield TranscriptRow(key, record, content, activity)

    def schedule(self) -> None:
        self._dirty = True
        pane = self.pane
        if self._alive() and not self._queued:
            self._queued = True
            pane.call_later(self._start_sync)

    def _alive(self) -> bool:
        return not self._closed and self.pane.is_mounted and self.pane.app.is_running

    def _start_sync(self) -> None:
        if self._alive():
            self._worker = self.pane.run_worker(self._sync, group="transcript-window", exit_on_error=True)
        else:
            self._queued = False

    async def close(self) -> None:
        """Retire and join the sole owned render worker before pane disposal."""
        if self._close_task is None:
            self._closed = True
            self._epoch += 1
            self._dirty = False
            worker = self._worker

            async def settle() -> None:
                if worker is not None:
                    if not worker.is_cancelled:
                        worker.cancel()
                    with suppress(WorkerCancelled):
                        await worker.wait()

            self._close_task = asyncio.create_task(settle())
        cancelled = None
        while not self._close_task.done():
            try:
                await asyncio.shield(self._close_task)
            except asyncio.CancelledError as error:
                cancelled = cancelled or error
            except BaseException:
                if not self._close_task.done():
                    raise
        try:
            self._close_task.result()
        except BaseException:
            if cancelled is not None:
                cancelled.add_note("Transcript cleanup also failed")
                raise cancelled from None
            raise
        if cancelled is not None:
            raise cancelled

    def project_row(self, widget: ChatMessage) -> None:
        """Recheck epoch and credentials at the actual widget mount boundary."""
        key = getattr(widget, "_transcript_row_id", -1)
        record = self.records.get(key)
        if not self.owns(widget) or not isinstance(record, MessageSnapshot):
            widget.display = False
            return
        self._project_widget(widget, record, runtime_evidence_redactor(self.pane.app))

    def project(self) -> None:
        """Refresh only mounted ordinary rows with the current held policy."""
        if not self.pane.is_mounted:
            return
        policy = runtime_evidence_redactor(self.pane.app)
        for key, widget in self.widgets.items():
            record = self.records.get(key)
            if isinstance(record, MessageSnapshot):
                self._project_widget(widget, record, policy)

    @staticmethod
    def _trusted_projection(value: str, policy: EvidenceRedactor, *, markup: bool = True) -> str:
        projected = policy.text(value)
        try:
            plain = Content.from_markup(value).plain
        except MarkupError:
            return escape(projected) if markup else projected
        projected_plain = policy.text(plain)
        if not markup:
            return projected_plain
        if projected == value and projected_plain == plain:
            return value
        return escape(projected_plain)

    def _project_widget(self, widget: Any, record: MessageSnapshot, policy: Any) -> None:
        # Retain valid unchanged markup. When credential projection changes
        # either visible text or hidden link metadata, emit safe literal text.
        prefix = self._trusted_projection(record.prefix, policy)
        content = self._trusted_projection(record.content, policy) if record.trusted else policy.text(record.content)
        markdown = record.markdown and not self.highlight
        if (widget._prefix, widget._content_text, widget._is_markdown, widget._highlight_term) == (prefix, content, markdown, self.highlight):
            return
        widget._transcript_projecting = True
        try:
            widget._prefix, widget._content_text = prefix, content
            widget._is_markdown, widget._highlight_term = markdown, self.highlight
            widget._update_renderable()
        finally:
            widget._transcript_projecting = False

    async def _sync(self) -> None:
        from henchman.cli.textual_widgets import ChatMessage

        pane = self.pane
        epoch = self._epoch
        self._syncing = True
        try:
            while self._dirty and self._alive():
                self._dirty = False
                # Discard can run while mount is awaiting its child callbacks.
                # Those rows are no longer in our maps, but still need joining
                # out of the DOM before planning any new order.
                retired = [widget for widget in pane.children
                           if (owner := getattr(widget, "_transcript_owner", None)) is not None
                           and owner() is self and not self.owns(widget)]
                if retired:
                    await pane.remove_children(retired)
                    if epoch != self._epoch or not self._alive():
                        return
                    if self._dirty:
                        continue
                ordinary = self.ordinary()
                start, end = self._bounds(ordinary)
                selected = set(ordinary[start:end]) | self.pinned
                # A focused row or held anchor is never silently discarded.
                for key, widget in self.widgets.items():
                    if widget.has_focus or widget.has_focus_within:
                        selected.add(key)
                if pane._reading_anchor is not None:
                    anchor, _ = pane._reading_anchor
                    key = getattr(anchor, "_transcript_row_id", -1)
                    if self._reveal is None and not pane.follow_live and key in self.records:
                        selected.add(key)
                remove = [key for key in self.widgets if key not in selected]
                if remove:
                    await pane.remove_children([self.widgets.pop(key) for key in remove])
                    if epoch != self._epoch or not self._alive():
                        return
                if self._dirty:
                    continue
                for key in self.records:
                    if key not in selected or key in self.widgets:
                        continue
                    record = self.records[key]
                    candidate = self.pending.pop(key, None)
                    if candidate is None and isinstance(record, MessageSnapshot):
                        candidate = ChatMessage(record.prefix, record.content, trusted=record.trusted,
                                             output_mode=record.output_mode)
                        candidate._is_markdown = record.markdown
                        candidate.display = not record.hidden
                        candidate._transcript_owner = weakref.ref(self)
                        candidate._transcript_row_id = key
                        candidate._transcript_epoch = epoch
                    if candidate is not None:
                        self.widgets[key] = candidate
                self.pending = {key: widget for key, widget in self.pending.items() if key in self.pinned}
                self.project()
                to_mount = [widget for widget in self.widgets.values() if widget.parent is not pane]
                if to_mount:
                    await pane.mount(*to_mount)
                    if epoch != self._epoch or not self._alive():
                        await pane.remove_children([item for item in to_mount if item.parent is pane])
                        return
                    if self._dirty:
                        continue
                ordered: list[Widget] = []
                controls: dict[tuple[Any, ...], Widget] = {}
                labels: dict[tuple[Any, ...], str] = {}
                focused_control = pane.app.focused in self._controls

                def control(key: tuple[Any, ...], label: str, *, current: dict[tuple[Any, ...], Widget] = controls,
                            current_labels: dict[tuple[Any, ...], str] = labels) -> Widget:
                    item = self._control_map.get(key)
                    if item is None:
                        item = HistoryButton(self, previous=key[0] == "previous") if key[0] in {"previous", "later"} else Static(label)
                    if key not in self._control_map or self._control_labels.get(key) != label:
                        if isinstance(item, Button):
                            item.label = label
                        elif isinstance(item, Static):
                            item.update(label)
                    current[key] = item
                    current_labels[key] = label
                    return item

                if start:
                    ordered.append(control(("previous",), f"Earlier messages ({start} retained)"))
                gap: list[int] = []
                for key in self.records:
                    if key not in self.widgets:
                        gap.append(key)
                        continue
                    if gap:
                        ordered.append(control(("gap", gap[0], gap[-1]), f"{len(gap)} ordinary messages retained outside this page"))
                        gap = []
                    ordered.append(self.widgets[key])
                if gap:
                    ordered.append(control(("gap", gap[0], gap[-1]), f"{len(gap)} ordinary messages retained outside this page"))
                if end < len(ordinary):
                    ordered.append(control(("later",), f"Later messages ({len(ordinary) - end} retained)"))
                stale = [widget for key, widget in self._control_map.items() if key not in controls]
                if stale:
                    self._control_map = {key: widget for key, widget in self._control_map.items() if key in controls}
                    await pane.remove_children(stale)
                    if epoch != self._epoch or not self._alive():
                        return
                    if self._dirty:
                        continue
                self._control_map = controls
                self._control_labels = labels
                self._controls = list(controls.values())
                new_controls = [item for item in self._controls if item.parent is not pane]
                if new_controls:
                    await pane.mount(*new_controls)
                    if epoch != self._epoch or not self._alive():
                        await pane.remove_children([item for item in new_controls if item.parent is pane])
                        return
                    if self._dirty:
                        continue
                if focused_control and pane.app.focused is None:
                    target = next((item for item in self._controls if isinstance(item, Button)), pane)
                    target.focus(scroll_visible=False)
                if list(pane.children) != ordered:
                    for index, ordered_widget in enumerate(ordered):
                        if index == 0:
                            pane.move_child(ordered_widget, before=0)
                        else:
                            pane.move_child(ordered_widget, after=ordered[index - 1])
                if self._reveal is not None and (revealed := self.widgets.get(self._reveal)) is not None:
                    self._reveal = None
                    pane._reading_anchor = (revealed, 0)
                pane.refresh_reading_position()
        finally:
            self._syncing = False
            self._queued = False
            if self._dirty and self._alive():
                self.schedule()
