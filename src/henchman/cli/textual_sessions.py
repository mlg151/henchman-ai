"""Project-scoped session search and explicit, idle-only restore."""

from __future__ import annotations

import asyncio
import io
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, ClassVar, TypeVar

from rich.console import Console
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, OptionList, Static, TextArea
from textual.widgets.option_list import Option

from henchman.cli.commands import CommandContext
from henchman.cli.commands.chat import _restore_session_state
from henchman.cli.session_manager import ReplSessionManager
from henchman.cli.textual_context import _binding, _current_policy, _joined
from henchman.cli.workflow import idle_command
from henchman.core.session import Session, SessionMetadata
from henchman.core.session_workflow import SessionWorkflow, WorkflowReport
from henchman.utils.evidence_redaction import EvidenceRedactor
from henchman.utils.exception_evidence import exception_text

_T = TypeVar("_T")


async def _read(action: Callable[[], _T]) -> _T:
    return await _joined(asyncio.create_task(asyncio.to_thread(action)))


def _version(session: Session) -> tuple[str, str]:
    """Use the storage layer's exact primary/backup revision before projection."""
    if session._storage_path is None or session._storage_token is None:
        raise ValueError("Saved session revision is unavailable; refresh the selection")
    return session._storage_path, session._storage_token


class _SessionDetails(TextArea):
    def action_copy(self) -> None:
        screen = self.screen
        if not isinstance(screen, SessionScreen):
            return
        previous = self.text
        screen._refresh_display()
        if previous != self.text:
            screen._status = "Credential projection changed; select the text again before copying."
            screen._refresh_display()
            return
        try:
            self.app.copy_to_clipboard(self.selected_text)
        except Exception as error:
            screen._status = exception_text(error, screen._policy)
            screen._refresh_display()


class SessionScreen(ModalScreen[None]):
    """Search saved metadata; inspection and filtering never select a session."""

    DEFAULT_CSS = """
    SessionScreen { background: $surface; }
    #sessions-dialog { width: 100%; height: 100%; padding: 0 1; }
    #sessions-title { height: 1; text-style: bold; }
    #sessions-status { height: 3; }
    #sessions-search { height: 3; }
    #sessions-list { height: 1fr; }
    #sessions-details { height: 1fr; }
    #sessions-actions, #sessions-confirm { height: 3; }
    #sessions-actions Button, #sessions-confirm Button { min-width: 8; width: 1fr; margin: 0; }
    #sessions-hint { height: 1; }
    """
    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        Binding("escape", "cancel", "Back", priority=True),
        Binding("f5", "refresh", "Refresh", priority=True),
        Binding("ctrl+enter", "inspect", "Inspect", priority=True),
    ]

    def __init__(self, sessions: list[SessionMetadata] | None = None, *, runtime: Any = None) -> None:
        super().__init__()
        self.runtime = runtime
        self._sessions = sessions or []
        self._policy = _current_policy(runtime) if runtime is not None else EvidenceRedactor()
        self._busy = False
        self._sessions_closing = False
        self._stale = False
        self._action_task: asyncio.Task[None] | None = None
        self._ids: list[str] = []
        self._candidate: Session | None = None
        self._candidate_version: tuple[str, str] | None = None
        self._selection_generation = 0
        self._candidate_generation: int | None = None
        self._highlighted_identity: str | None = None
        self._confirming = False
        self._resume_completed = False
        self._details = "Select a saved session and press Enter to inspect. No session has been changed."
        self._status = "Saved session metadata only. Composer draft is neither submitted nor saved."
        self.manager: ReplSessionManager | None = None
        self.workflow: SessionWorkflow | None = None
        self.root: Path | None = None
        self.project_hash: str | None = None
        self._captured: tuple[Any, ...] | None = None
        if runtime is not None:
            context = getattr(runtime, "core_context", None)
            manager = getattr(context, "session_manager", None)
            root = getattr(context, "project_root", None)
            if not isinstance(manager, ReplSessionManager) or not isinstance(root, Path) or manager.current is None:
                raise ValueError("No selected project session is available")
            self.manager, self.workflow, self.root = manager, manager.workflow_runtime, root.resolve()
            self.project_hash = manager.compute_project_hash(self.root)
            if manager.current.project_hash != self.project_hash:
                raise ValueError("Selected session does not belong to this runtime project")
            self._captured = self._identity()

    def _identity(self) -> tuple[Any, ...]:
        assert self.root is not None
        info = self.root.stat()
        return (_binding(self.runtime), id(self.runtime.settings), id(self.manager), id(self.workflow),
                Path.cwd().resolve(), self.root.resolve(), info.st_dev, info.st_ino,
                self.runtime.settings.model_dump_json())

    def _admit(self) -> None:
        if self.runtime is None or self._sessions_closing or self._stale or not self.runtime.is_running:
            raise ValueError("Session selection is unavailable; close and reopen Sessions")
        answer = getattr(getattr(self.runtime, "_tool_prompts", None), "_answer", None)
        if self.runtime.screen is not self or (isinstance(answer, asyncio.Future) and not answer.done()):
            raise ValueError("Finish the pending decision before changing sessions")
        if self._identity() != self._captured:
            raise ValueError("Runtime, project or session changed; close and reopen Sessions")

    def _safe(self, text: str, limit: int = 65536) -> str:
        if self.runtime is not None:
            self._policy.register_policy(_current_policy(self.runtime))
        if len(text) > limit:
            return "[Session evidence omitted by the display limit]"
        safe = self._policy.text(text)
        return safe if len(safe.encode("utf-8", errors="replace")) <= limit else "[Session evidence omitted by the display limit]"

    def _build_entries(self) -> list[tuple[str, str]]:
        return [(f"{self._safe(item.tag or '(untagged)', 512)} · {self._safe(item.id, 512)}\n"
                 f"{self._safe(item.last_updated, 128)} · {item.message_count} messages", item.id)
                for item in self._sessions]

    def compose(self) -> ComposeResult:
        with Vertical(id="sessions-dialog"):
            yield Static("Project sessions", markup=False, id="sessions-title")
            yield Static(self._status, markup=False, id="sessions-status")
            yield Input(placeholder="Search saved ID or tag in this project", max_length=512, id="sessions-search")
            yield OptionList(id="sessions-list")
            yield _SessionDetails(self._details, read_only=True, soft_wrap=True, id="sessions-details")
            with Horizontal(id="sessions-actions"):
                yield Button("Back", id="sessions-back")
                yield Button("Refresh", id="sessions-refresh")
                yield Button("Inspect", id="sessions-inspect")
                yield Button("Resume…", id="sessions-resume")
            with Horizontal(id="sessions-confirm"):
                yield Button("Save current + resume", id="sessions-save-resume")
                yield Button("Resume without save", id="sessions-without-save")
                yield Button("Keep current", id="sessions-keep")
            yield Static("Enter inspects · Tab selects actions · F5 refreshes · Esc Back", markup=False, id="sessions-hint")

    def on_mount(self) -> None:
        self.query_one(Input).focus()
        self._refresh_display()
        if self.runtime is not None:
            self.action_refresh()
        else:
            self._filter()
        self.set_interval(0.5, self._refresh_display)

    def _refresh_display(self) -> None:
        if not self.is_mounted:
            return
        self._filter()
        self.query_one("#sessions-status", Static).update(self._safe(self._status))
        area = self.query_one(TextArea)
        safe = self._safe(self._details)
        if area.text != safe:
            area.load_text(safe)
        self.query_one("#sessions-confirm").display = self._confirming
        disabled = self._busy or self._sessions_closing or self._stale or self.runtime is None
        for name in ("refresh", "inspect", "resume", "save-resume", "without-save"):
            self.query_one("#sessions-" + name, Button).disabled = disabled or (name in {"resume", "save-resume", "without-save"} and self._candidate is None)

    def _filter(self) -> None:
        query = self.query_one(Input).value.casefold()
        options = self.query_one(OptionList)
        highlighted = options.highlighted
        selected = self._ids[highlighted] if highlighted is not None and highlighted < len(self._ids) else None
        entries = [(label, identity) for label, identity in self._build_entries() if query in label.casefold()]
        visible = entries[:200]
        labels = [label for label, _ in visible]
        if labels != getattr(self, "_labels", None):
            self._labels = labels
            self._ids = [identity for _, identity in visible]
            options.clear_options()
            options.add_options([Option(Text(label)) for label in labels])
            if self._ids:
                options.highlighted = self._ids.index(selected) if selected in self._ids else 0
        count = f"{len(entries)} matching persisted sessions in this project"
        if len(entries) > 200:
            count += " · showing first 200; narrow search for omitted matches"
        self.query_one("#sessions-title", Static).update(count)
        self._track_selection()

    def _selected_identity(self) -> str | None:
        index = self.query_one(OptionList).highlighted
        return self._ids[index] if index is not None and index < len(self._ids) else None

    def _invalidate_selection(self) -> None:
        self._selection_generation += 1
        self._candidate = None
        self._candidate_generation = None
        self._confirming = False
        self._details = "Selection changed. Inspect the selected saved session before resuming."

    def _track_selection(self) -> None:
        selected = self._selected_identity()
        if selected != self._highlighted_identity:
            self._highlighted_identity = selected
            self._invalidate_selection()

    def _admit_selection(self, identity: str, generation: int) -> None:
        self._admit()
        if self._selection_generation != generation or self._selected_identity() != identity:
            raise ValueError("Session selection changed during the read; inspect it again")

    def on_input_changed(self, event: Input.Changed) -> None:
        event.stop()
        self._invalidate_selection()
        self._refresh_display()

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        event.stop()
        self._track_selection()
        self._refresh_display()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        event.stop()
        self.action_inspect()

    def _run(self, action: Callable[[], Awaitable[None]]) -> None:
        if self._busy or self._sessions_closing:
            return
        self._busy = True
        async def owned() -> None:
            try:
                await action()
            except asyncio.CancelledError:
                raise
            except Exception as error:
                self._policy.register_policy(_current_policy(self.runtime))
                self._status = exception_text(error, self._policy)
            finally:
                self._busy = False
                self._refresh_display()
        self._action_task = asyncio.create_task(owned())
        self._refresh_display()

    def action_refresh(self) -> None:
        async def refresh() -> None:
            self._admit()
            assert self.manager is not None
            manager = self.manager
            records = await _read(lambda: manager.list_sessions(self.project_hash))
            self._admit()
            self._sessions = records
            self._candidate = None
            self._confirming = False
            self._status = "Persisted metadata loaded. Current save freshness is unverified; composer draft stays local."
        self._run(refresh)

    def _recovery(self, report: WorkflowReport) -> str:
        if report.failure_reason == "process_history_unavailable":
            return "Recovery: process-only history is unavailable after reload; no empty recovered queue is assumed."
        if report.failure_reason:
            raise ValueError("Session recovery authority is unavailable")
        return (f"Recovery: {report.persistence}; {len(report.state.inputs)} recorded inputs; "
                f"{len(report.blocking_input_ids)} unresolved effects.\n"
                f"Goal requires explicit resume: {'yes' if report.goal_requires_resume else 'no'}.\n"
                "Resuming a session never sends queued inputs or resumes a goal.")

    async def _load_selected(self, identity: str, generation: int) -> tuple[Session, WorkflowReport]:
        assert self.manager is not None and self.workflow is not None
        self._admit_selection(identity, generation)
        manager, workflow = self.manager, self.workflow
        session = await _read(lambda: manager.load(identity, project_hash=self.project_hash))
        self._admit_selection(identity, generation)
        if session.id != identity or session.project_hash != self.project_hash:
            raise ValueError("Saved session identity changed")
        report = await _read(lambda: workflow.inspect_session(session))
        self._admit_selection(identity, generation)
        return session, report

    def action_inspect(self) -> None:
        selected = self.query_one(OptionList).highlighted
        if selected is None or selected >= len(self._ids):
            return
        identity = self._ids[selected]
        generation = self._selection_generation
        async def inspect() -> None:
            self._admit()
            self._candidate = None
            self._confirming = False
            session, report = await self._load_selected(identity, generation)
            recovery = self._recovery(report)
            storage_notice = f"Storage recovery: {session.recovery_notice}\n\n" if session.recovery_notice else ""
            assert self.manager is not None
            self._details = (f"Persisted session\nProject: {session.project_hash}\nSession: {session.id}\n"
                             f"Tag: {session.tag or '(untagged)'}\nUpdated: {session.last_updated}\nMessages: {len(session.messages)}\n\n"
                             f"{storage_notice}{recovery}\n\nCurrent autosave: {'on' if self.manager.auto_save else 'off'}. "
                             "Current in-memory changes may be unsaved. Composer draft is separate and will be preserved.")
            self._candidate, self._candidate_version = session, _version(session)
            self._candidate_generation = generation
            self._status = "Inspection did not select or modify this session. Resume requires a separate explicit action."
        self._run(inspect)

    def _confirm(self) -> None:
        try:
            self._admit()
            if self._candidate is None or self._busy:
                return
            if self.manager is not None and self.manager.current is not None and self._candidate.id == self.manager.current.id:
                raise ValueError("This is already the current session; its unsaved live history was preserved")
            self._confirming = True
            self._status = "Save current session before switching? Neither option submits your composer draft."
        except (ValueError, OSError) as error:
            self._status = exception_text(error, self._policy)
        self._refresh_display()

    def _activate(self, *, save: bool) -> None:
        async def activate() -> None:
            self._admit()
            if not self._confirming or self._candidate is None:
                raise ValueError("Inspect and confirm the selected session first")
            assert self.manager is not None
            manager = self.manager
            identity, version = self._candidate.id, self._candidate_version
            generation = self._candidate_generation
            if generation is None:
                raise ValueError("Inspect the selected session again")
            self._admit_selection(identity, generation)
            with idle_command(self.runtime):
                loaded, report = await self._load_selected(identity, generation)
                self._recovery(report)
                if _version(loaded) != version:
                    self._candidate = None
                    raise ValueError("Saved session changed after inspection; inspect it again")
                if save:
                    previous = self.manager.current
                    await _read(lambda: manager.save(previous))
                    self._admit_selection(identity, generation)
                    loaded, report = await self._load_selected(identity, generation)
                    self._recovery(report)
                    if _version(loaded) != version:
                        self._candidate = None
                        raise ValueError("Saved session changed while saving current session; inspect it again")
                self._admit_selection(identity, generation)
                task = asyncio.current_task()
                if task is not None and task.cancelling():
                    await asyncio.sleep(0)
                # No await between this final guard and the shared activation.
                ctx = CommandContext(console=Console(file=io.StringIO()), repl=self.runtime,
                                     session_manager=self.manager.session_manager, project_hash=self.project_hash)
                _restore_session_state(ctx, self.manager.session_manager, loaded, identity)
                if self.manager.current is not loaded or self.manager.session_manager.current is not loaded:
                    raise ValueError("Session activation was not acknowledged")
                self._captured = self._identity()
                self._resume_completed = True
                self._candidate = None
                self._confirming = False
                self._status = ("Current session saved. " if save else "Previous session was not saved by this action. ") + "Resumed selected session; queued inputs and goals remain held. Composer draft preserved."
                from henchman.cli.textual_widgets import ChatPane

                try:
                    self.runtime.screen_stack[0].query_one(ChatPane).add_system_message(
                        self._safe(f"Resumed session {loaded.tag or '(untagged)'} ({loaded.id}). Earlier visible rows belong to the previous session; saved history is restored to the active agent."),
                        literal=True,
                    )
                except Exception:
                    self._status += " Transcript boundary display unavailable; session activation succeeded."
        self._run(activate)

    def on_screen_suspend(self) -> None:
        self._stale = True
        if self._action_task is not None and not self._action_task.done():
            self._action_task.cancel()

    async def on_unmount(self) -> None:
        self._sessions_closing = True
        if self._action_task is not None and not self._action_task.done():
            task = self._action_task
            task.cancel()
            async def settle() -> None:
                await asyncio.gather(task, return_exceptions=True)
            await _joined(asyncio.create_task(settle()))

    async def action_cancel(self) -> None:
        if self._confirming and not self._busy:
            self._confirming = False
            self._refresh_display()
            return
        await self.on_unmount()
        if self.is_mounted:
            self.dismiss(None)

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        action = event.button.id
        if action == "sessions-back":
            await self.action_cancel()
        elif action == "sessions-refresh":
            self.action_refresh()
        elif action == "sessions-inspect":
            self.action_inspect()
        elif action == "sessions-resume":
            self._confirm()
        elif action in {"sessions-save-resume", "sessions-without-save"}:
            self._activate(save=action == "sessions-save-resume")
        elif action == "sessions-keep":
            self._confirming = False
            self._refresh_display()


def open_session_browser(runtime: Any) -> None:
    """Open a captured project selection without displacing a pending decision."""
    if len(runtime.screen_stack) != 1 or getattr(runtime._tool_prompts, "_answer", None) is not None:
        runtime.notify("Close the current dialog first; F4 returns to a pending decision.", markup=False)
        return
    focused = runtime.focused
    def restore_focus(_value: None) -> None:
        if focused is not None and focused.is_mounted:
            focused.focus()
    try:
        runtime.push_screen(SessionScreen(runtime=runtime), restore_focus)
    except (ValueError, OSError) as error:
        runtime.notify(exception_text(error, _current_policy(runtime)), severity="error", markup=False)
