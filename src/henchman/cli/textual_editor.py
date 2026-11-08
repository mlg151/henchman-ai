"""Explicit user-only external composition with owned terminal restoration."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, ClassVar

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static, TextArea

from henchman.cli.draft_editor import (
    DraftBinding,
    DraftEditorError,
    check_editor_control,
    edit_draft,
    join_owned,
)
from henchman.cli.evidence import runtime_evidence_redactor
from henchman.cli.workflow import idle_command


@dataclass(frozen=True)
class _Recovery:
    text: str
    binding: DraftBinding


class DraftRecoveryScreen(ModalScreen[None]):
    """A held result never replaces a newer draft without a fresh user action."""

    DEFAULT_CSS = """
    DraftRecoveryScreen { align: center middle; }
    #draft-recovery { width: 76; max-width: 96%; height: auto; max-height: 95%;
        border: solid $accent; padding: 1 2; background: $surface; }
    #draft-recovery-text { height: auto; max-height: 10; overflow-y: auto; }
    #draft-recovery-actions { height: auto; }
    """
    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [("escape", "back", "Back")]

    def __init__(self, owner: _Editor) -> None:
        super().__init__()
        self.owner = owner
        self.original = owner.app.query_one("#input", TextArea).text
        self.record = owner.recovery

    def compose(self) -> ComposeResult:
        yield Vertical(
            Static("An edited draft is held in memory. Use replaces the current draft; nothing is sent.", markup=False),
            Static("", markup=False, id="draft-recovery-text"),
            Horizontal(Button("Use edited draft", id="draft-recovery-use"),
                       Button("Discard", id="draft-recovery-discard"), Button("Back", id="draft-recovery-back"),
                       id="draft-recovery-actions"), id="draft-recovery",
        )

    def on_mount(self) -> None:
        self._project()
        self.set_interval(0.1, self._project)
        self.query_one("#draft-recovery-back", Button).focus()

    def _project(self) -> None:
        raw = self.record.text if self.record is not None else ""
        safe = runtime_evidence_redactor(self.owner.app).text(raw)
        preview = safe[:2000] + ("\n[Preview truncated]" if len(safe) > 2000 else "")
        self.query_one("#draft-recovery-text", Static).update(preview)

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        if event.button.id == "draft-recovery-use":
            try:
                if self.record is None:
                    raise DraftEditorError("Held draft is unavailable.")
                self.owner.check(self.record.binding, modal=self)
                composer = self.owner.app.query_one("#input", TextArea)
                if self.record is None or self.owner.recovery is not self.record or composer.text != self.original:
                    raise DraftEditorError("Draft changed; close and reopen this review.")
                await check_editor_control()
                composer.load_text(self.record.text)
            except DraftEditorError:
                self.owner.app.notify("The session or draft changed; edited text remains held. Return to its original session to review.", severity="warning")
                return
            self.owner.recovery = None
        elif event.button.id == "draft-recovery-discard":
            if self.owner.recovery is self.record:
                self.owner.recovery = None
        self.action_back()

    def action_back(self) -> None:
        self.dismiss(None)


class _Editor:
    def __init__(self, app: Any) -> None:
        self.app = app
        self.task: asyncio.Task[None] | None = None
        self.closed = False
        self.recovery: _Recovery | None = None
        self.close_task: asyncio.Task[None] | None = None
        self.previous_idle: object = None

    def check(self, binding: DraftBinding, *, modal: object | None = None) -> None:
        binding.check(self.app)
        if self.closed:
            raise DraftEditorError("External editor session changed or is closing.")
        if (modal is None and len(self.app.screen_stack) != 1) or (modal is not None and self.app.screen is not modal):
            raise DraftEditorError("Close the current dialog before external composition.")

    async def run(self, binding: DraftBinding) -> None:
        composer = self.app.query_one("#input", TextArea)
        original, selection = composer.text, composer.selection
        focus, read_only = self.app.focused, composer.read_only
        try:
            self.check(binding)
            with idle_command(self.app):
                composer.read_only = True
                error: BaseException | None = None
                # Textual suspend resumes its driver *after* yield rather than
                # in finally. Exit it normally even on process cancellation.
                with self.app.suspend():
                    try:
                        result = await edit_draft(original, cwd=binding.root, authorize=lambda: self.check(binding))
                    except BaseException as failure:
                        error = failure
                if error is not None:
                    raise error
                try:
                    self.check(binding)
                    if composer.text != original:
                        raise DraftEditorError("Draft changed.")
                except DraftEditorError:
                    self.recovery = _Recovery(result, binding)
                    self.app.notify("Edited text is held in memory. Use External editor again to review or discard it.", severity="warning")
                else:
                    await check_editor_control()
                    composer.load_text(result)
                    self.app.notify("Draft updated; review it before sending.")
        except asyncio.CancelledError:
            # User interruption is handled here; close() independently preserves
            # cancellation of its own caller while joining this task.
            if not self.closed:
                self.app.notify("External editor cancelled; original draft preserved.")
        except DraftEditorError as error:
            self.app.notify(str(error), severity="error")
        except Exception:
            self.app.notify("External editor unavailable or failed; original draft preserved. Check VISUAL/EDITOR, terminal and idle policy.", severity="error")
        finally:
            if getattr(self.app, "_idle_control_task", None) is asyncio.current_task():
                self.app._idle_control_task = self.previous_idle
            composer.read_only = read_only
            if composer.text == original:
                composer.selection = selection
            if not self.closed and len(self.app.screen_stack) == 1 and focus is not None:
                focus.focus()

    async def close(self) -> None:
        if self.close_task is None:
            self.closed = True
            async def finish() -> None:
                if self.task is not None and not self.task.done():
                    self.task.cancel()
                if self.task is not None:
                    await asyncio.gather(self.task, return_exceptions=True)
                self.recovery = None
            self.close_task = asyncio.create_task(finish())
        failure = await join_owned(self.close_task)
        if failure is not None:
            raise failure


def start_external_editor(app: Any) -> None:
    """Start only from the idle base composer, or explicitly review held text."""
    owner = getattr(app, "_draft_editor", None)
    if isinstance(owner, _Editor) and (owner.closed or (owner.task is not None and not owner.task.done())):
        return
    try:
        binding = DraftBinding.capture(app)
        if len(app.screen_stack) != 1 or app.query_one("#input", TextArea).read_only:
            raise DraftEditorError("Close the current dialog first.")
    except DraftEditorError:
        app.notify("External editor requires idle work and no open decision or dialog.", severity="warning")
        return
    if not isinstance(owner, _Editor):
        owner = _Editor(app)
        app._draft_editor = owner
    if owner.recovery is not None:
        app.push_screen(DraftRecoveryScreen(owner))
    else:
        owner.previous_idle = getattr(app, "_idle_control_task", None)
        owner.task = asyncio.create_task(owner.run(binding))
        app._idle_control_task = owner.task


def cancel_external_editor(app: Any) -> bool:
    """Cancel only this frontend's owned external editor, before draft clearing."""
    owner = getattr(app, "_draft_editor", None)
    if isinstance(owner, _Editor) and owner.task is not None and not owner.task.done():
        if not owner.task.cancelling():
            owner.task.cancel()
        return True
    return False


async def close_external_editor(app: Any) -> None:
    """Join the one editor owner before the frontend releases its runtime."""
    owner = getattr(app, "_draft_editor", None)
    if isinstance(owner, _Editor):
        await owner.close()
