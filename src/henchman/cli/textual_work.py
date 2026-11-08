"""Bounded, read-only inspection of already owned project work."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar, Literal

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, OptionList, Static, TextArea
from textual.widgets.option_list import Option

from henchman.advanced.task_output import open_evidence
from henchman.advanced.tasks import TaskRecord, TaskService
from henchman.agents.subagents import BackgroundSubagentManager, SubagentRecord
from henchman.cli.textual_context import _binding, _current_policy, _joined, _model, _provider_name
from henchman.core.failure_evidence import failure_evidence_redactor
from henchman.tools.builtins.tier6_tools import TaskGetTool
from henchman.tools.registry import ToolRegistry
from henchman.utils.evidence_redaction import EvidenceRedactor, EvidenceStreamRedactor
from henchman.utils.exception_evidence import exception_text

_ROWS = 200
_TEXT_BYTES = 65536
_EVIDENCE_BYTES = 32768


def _bounded(value: str, limit: int = _EVIDENCE_BYTES) -> str:
    if len(value) > limit or len(value.encode("utf-8", errors="replace")) > limit:
        return "[Evidence omitted: display limit]"
    return value


@dataclass(frozen=True)
class WorkRow:
    """An exact lookup identity, separate from its untrusted visible label."""

    kind: Literal["agent", "task"]
    identity: str
    state: str
    label: str


def bound_task_service(runtime: Any, root: Path | None = None) -> TaskService | None:
    """Return an existing project-bound owner without constructing any service.

    This is a read-path integration seam for the Workspace overview. Absence is
    unavailable, not proof of an empty task list or permission to create one.
    """
    context = getattr(runtime, "core_context", None)
    root = root if root is not None else getattr(context, "project_root", None)
    if not isinstance(root, Path):
        return None
    root = root.resolve()
    registry = getattr(context, "tool_registry", None)
    if not isinstance(registry, ToolRegistry):
        return None
    tool = registry.get("task_get")
    if not isinstance(tool, TaskGetTool):
        return None
    service = tool._task_service
    return service if isinstance(service, TaskService) and service._project_root == root else None


def _task_details(service: TaskService, identity: str) -> tuple[TaskRecord, str]:
    record = service.get_task(identity)
    if record is None:
        raise ValueError("Selected task is no longer available")
    # Read the service's validated physical path, never its display projection.
    # Do not call tail_output: inspection must not migrate an old log/index.
    if record.metadata.get("output_truncated") == "true":
        output = "[Output omitted: task capture was truncated]"
    else:
        try:
            with open_evidence(record.output_path) as source:
                payload = source.read(_EVIDENCE_BYTES + 1)
        except FileNotFoundError:
            output = "No retained output is available."
        else:
            output = ("[Output omitted: retained log exceeds 32 KiB]" if len(payload) > _EVIDENCE_BYTES
                      else payload.decode("utf-8", errors="replace"))
    current = service.get_task(identity)
    if current is None or current.revision != record.revision:
        raise ValueError("Task changed during inspection; refresh it")
    return record, output


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
    """Inspect explicit snapshots without dispatch, cancellation, or grants."""

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
    ]

    def __init__(self, runtime: Any) -> None:
        super().__init__()
        self.runtime = runtime
        context = getattr(runtime, "core_context", None)
        root = getattr(context, "project_root", None)
        session = getattr(getattr(context, "session_manager", None), "current", None)
        if not isinstance(root, Path) or session is None:
            raise ValueError("Work inspection needs a selected project session")
        assert context is not None
        self.root = root.resolve()
        if context.session_manager.compute_project_hash(self.root) != session.project_hash:
            raise ValueError("Selected session does not belong to this project")
        self.service = bound_task_service(runtime, self.root)
        manager = getattr(getattr(context, "orchestrator", None), "subagents", None)
        self.agents = manager if isinstance(manager, BackgroundSubagentManager) else None
        self._policy = _current_policy(runtime)
        self._captured = self._identity()
        self._rows: tuple[WorkRow, ...] = ()
        self._fields: tuple[tuple[str, str], ...] = ()
        self._output_interrupted = False
        self._actors: list[Any] = []
        self._stage = "list"
        self._status = "Loading owned work observations…"
        self._action_task: asyncio.Task[None] | None = None
        self._busy = False
        self._work_closing = False
        self._stale = False
        self._selection = 0

    def _identity(self) -> tuple[Any, ...]:
        context = self.runtime.core_context
        info = self.root.stat()
        return (_binding(self.runtime), Path.cwd().resolve(), self.root.resolve(), info.st_dev, info.st_ino,
                id(getattr(context.orchestrator, "subagents", None)), id(bound_task_service(self.runtime, self.root)),
                self.runtime.settings.model_dump_json())

    def _admit(self) -> None:
        if self._work_closing or self._stale or self.runtime.screen is not self or self._captured != self._identity():
            raise ValueError("Work owner, project or session changed; close and reopen inspection")

    def _refresh_policy(self) -> EvidenceRedactor:
        self._policy.register_policy(_current_policy(self.runtime))
        if self.service is not None:
            self._policy.register_policy(self.service._runtime.policy)
        for actor in self._actors:
            failure_evidence_redactor(actor, redactor=self._policy)
        return self._policy

    def _safe(self, value: str, limit: int = _EVIDENCE_BYTES, *, interrupted: bool = False) -> str:
        stream = EvidenceStreamRedactor(self._policy)
        text = stream.feed(_bounded(value, limit)) + stream.finish(interrupted=interrupted)
        return _bounded(text, limit)

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
            yield Static("Enter inspects · Esc returns to list, then closes · F5 refreshes", markup=False, id="work-hint")

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
        labels = [f"{row.kind} · {self._safe(row.identity, 512)} · {row.state} · {self._safe(row.label, 512)}" for row in self._rows]
        options = self.query_one(OptionList)
        if labels != getattr(self, "_labels", None):
            self._labels = labels
            selected = options.highlighted
            options.clear_options()
            options.add_options([Option(Text(label)) for label in labels])
            options.highlighted = min(selected or 0, len(labels) - 1) if labels else None
        chunks: list[str] = []
        size = 0
        for label, value in self._fields:
            text = self._safe(value, interrupted=label == "Retained output" and self._output_interrupted)
            chunk = f"{label}: {text}"
            length = len(chunk.encode("utf-8", errors="replace")) + 2
            if size + length > _TEXT_BYTES - 128:
                chunks.append("[Further evidence omitted: total display limit]")
                break
            chunks.append(chunk)
            size += length
        text = "\n\n".join(chunks)
        area = self.query_one(TextArea)
        if area.text != text:
            area.load_text(text)
        self.query_one("#work-status", Static).update(self._safe(self._status))
        for name in ("refresh", "inspect"):
            self.query_one("#work-" + name, Button).disabled = self._busy or self._stale or self._work_closing
        self.query_one("#work-copy", Button).disabled = not self._fields
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
            records = self.agents.list() if self.agents is not None else []
            self._actors = ([self.agents._conversations[item.conversation_id].agent for item in records[:_ROWS]]
                            if self.agents is not None else [])
            self._refresh_policy()
            rows = [WorkRow("agent", item.conversation_id, item.status, _bounded(item.role, 512)) for item in records[:_ROWS]]
            tasks = await _joined(asyncio.create_task(asyncio.to_thread(self.service.list_tasks))) if self.service is not None else []
            self._admit()
            rows.extend(WorkRow("task", item.task_id, item.status, _bounded(item.title, 512)) for item in tasks[:max(0, _ROWS - len(rows))])
            self._rows = tuple(rows)
            self._fields = ()
            self._stage = "list"
            self._selection += 1
            notices = [f"{len(rows)} observed items. Refresh is explicit; background work continues."]
            if len(records) + len(tasks) > _ROWS:
                notices.append("More items omitted by the 200-row display limit.")
            if self.agents is None:
                notices.append("Background agent owner unavailable.")
            if self.service is None:
                notices.append("Bound project task service unavailable; no storage was created.")
            self._status = " ".join(notices)
        self._run(refresh)

    def _agent_fields(self, identity: str) -> tuple[tuple[str, str], ...]:
        assert self.agents is not None
        record: SubagentRecord = self.agents.get(identity)
        self._output_interrupted = record.status != "done" or record.cancelled
        actor = self.agents._conversations[identity].agent
        if not any(item is actor for item in self._actors):
            self._actors.append(actor)
        self._refresh_policy()
        provider = getattr(actor, "provider", None)
        output = "[Output omitted: retained observation was clipped]" if record.output_truncated else _bounded(record.output)
        error = record.error or "No error recorded"
        if len(error) >= self.agents._max_output_chars:
            error = "[Error omitted: retained observation may be clipped]"
        state = record.status + (" — blocked awaiting parent input" if record.status == "waiting_for_input" else "")
        if record.cancelled:
            state += " — cancelled, not successful completion"
        return (("Conversation", record.conversation_id), ("Parent", record.parent_id), ("Role", _bounded(record.role, 512)),
                ("State", state), ("Lifetime", "process-only runtime conversation; observed completion is not task verification"),
                ("Provider", str(_provider_name(provider) or "unavailable")), ("Model", str(_model(provider) or "unavailable")),
                ("Budget authority", "No run ID is retained on this conversation snapshot. Context and usage or /usage reports the selected session's shared run; no per-child cap or bill is inferred."),
                ("Error", _bounded(error)), ("Retained output", output or "No output recorded"),
                ("Retained event kinds", ", ".join(event.type.value for event in record.events[-32:]) or "None recorded"),
                ("Evidence boundary", "Only bounded output/error and event kinds are shown. System prompts, messages and opaque continuation are not displayed."))

    def action_inspect(self) -> None:
        index = self.query_one(OptionList).highlighted
        if index is None or index >= len(self._rows):
            return
        row, selection = self._rows[index], self._selection
        async def inspect() -> None:
            self._fields = ()
            self._output_interrupted = False
            self._render_view()
            if row.kind == "agent":
                fields = self._agent_fields(row.identity)
            else:
                assert self.service is not None
                record, output = await _joined(asyncio.create_task(asyncio.to_thread(_task_details, self.service, row.identity)))
                self._output_interrupted = record.status != "completed" or bool(record.metadata.get("error"))
                context = record.operation_context
                correlation = (f"Session {context['session_id']} · Run {context['run_id']} · Agent {context['agent_id']} · Operation {context['operation_id']}"
                               if context is not None else "Unavailable; task is project-scoped, not attributed to the current run")
                fields = (("Task", record.task_id), ("State", record.status), ("Title", _bounded(record.title, 512)),
                          ("Lifetime", "Persisted project task evidence; stored PID is not execution authority or task verification"),
                          ("Revision", str(record.revision)), ("Return code", str(record.return_code) if record.return_code is not None else "unavailable"),
                          ("Correlation", correlation), ("Error", _bounded(record.metadata.get("error", "No error recorded"))),
                          ("Retained output", output), ("Outcome", "Unowned process outcome is unknown; no PID is adopted." if record.status == "outcome_unknown" else "Observed execution state only."))
            self._admit()
            if self._selection != selection or self.query_one(OptionList).highlighted != index:
                raise ValueError("Selection changed during inspection; inspect it again")
            self._fields = fields
            self._stage = "detail"
            self._status = "Captured observation. Work continues independently; Refresh reads current state."
            self._render_view()
            self.query_one(TextArea).focus()
        self._run(inspect)

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
