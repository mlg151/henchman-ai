"""Bounded snapshots of existing work owners, shared by terminal frontends."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from henchman.advanced.task_output import open_evidence
from henchman.advanced.tasks import TaskRecord, TaskService
from henchman.agents.subagents import BackgroundSubagentManager, SubagentRecord
from henchman.cli.inspection_runtime import (
    _binding,
    _context,
    _current_policy,
    _joined,
    _model,
    _provider_name,
)
from henchman.core.failure_evidence import failure_evidence_redactor
from henchman.tools.builtins.tier6_tools import TaskGetTool
from henchman.tools.registry import ToolRegistry
from henchman.utils.evidence_redaction import EvidenceRedactor, EvidenceStreamRedactor

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
    context = _context(runtime)
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
            output = (
                "[Output omitted: retained log exceeds 32 KiB]"
                if len(payload) > _EVIDENCE_BYTES
                else payload.decode("utf-8", errors="replace")
            )
    current = service.get_task(identity)
    if current is None or current.revision != record.revision:
        raise ValueError("Task changed during inspection; refresh it")
    return record, output


class WorkInspection:
    """Read existing owners without dispatch, persistence, recovery or grants."""

    def __init__(self, runtime: Any) -> None:
        self.runtime = runtime
        context = _context(runtime)
        root = getattr(context, "project_root", None)
        manager = getattr(context, "session_manager", None)
        session = getattr(manager, "current", None)
        if not isinstance(root, Path) or manager is None or session is None:
            raise ValueError("Work inspection needs a selected project session")
        self.root = root.resolve()
        if manager.compute_project_hash(self.root) != session.project_hash:
            raise ValueError("Selected session does not belong to this project")
        self.session = session
        self.service = bound_task_service(runtime, self.root)
        agents = getattr(getattr(context, "orchestrator", None), "subagents", None)
        self.agents = agents if isinstance(agents, BackgroundSubagentManager) else None
        self._policy = _current_policy(runtime)
        self._actors: list[Any] = []
        self._output_interrupted = False
        self._captured = self.identity()

    def identity(self) -> tuple[Any, ...]:
        context = _context(self.runtime)
        info = self.root.stat()
        return (
            _binding(self.runtime),
            Path.cwd().resolve(),
            self.root.resolve(),
            info.st_dev,
            info.st_ino,
            id(getattr(getattr(context, "orchestrator", None), "subagents", None)),
            id(bound_task_service(self.runtime, self.root)),
            self.runtime.settings.model_dump_json(),
        )

    def admit(self) -> None:
        if self._captured != self.identity():
            raise ValueError("Work owner, project or session changed; reopen inspection")

    def _refresh_policy(self) -> EvidenceRedactor:
        self._policy.register_policy(_current_policy(self.runtime))
        if self.service is not None:
            self._policy.register_policy(self.service._runtime.policy)
        for actor in self._actors:
            failure_evidence_redactor(actor, redactor=self._policy)
        return self._policy

    def safe(self, value: str, limit: int = _EVIDENCE_BYTES, *, interrupted: bool = False) -> str:
        stream = EvidenceStreamRedactor(self._policy)
        text = stream.feed(_bounded(value, limit)) + stream.finish(interrupted=interrupted)
        return _bounded(text, limit)

    def labels(self, rows: tuple[WorkRow, ...]) -> list[str]:
        self._refresh_policy()
        return [
            f"{row.kind} · {self.safe(row.identity, 512)} · {row.state} · {self.safe(row.label, 512)}"
            for row in rows
        ]

    def details(self, fields: tuple[tuple[str, str], ...], *, interrupted: bool) -> str:
        self._refresh_policy()
        chunks: list[str] = []
        size = 0
        for label, value in fields:
            text = self.safe(value, interrupted=label == "Retained output" and interrupted)
            chunk = f"{label}: {text}"
            length = len(chunk.encode("utf-8", errors="replace")) + 2
            if size + length > _TEXT_BYTES - 128:
                chunks.append("[Further evidence omitted: total display limit]")
                break
            chunks.append(chunk)
            size += length
        return "\n\n".join(chunks)

    def catalog_text(self, rows: tuple[WorkRow, ...], notice: str) -> str:
        lines = ["Tasks and agents · observed state, not task verification", self.safe(notice)]
        size = sum(len(line.encode()) + 1 for line in lines)
        for label in self.labels(rows):
            length = len(label.encode("utf-8", errors="replace")) + 1
            if size + length > _TEXT_BYTES - 128:
                lines.append("[Further items omitted: total display limit]")
                break
            lines.append(label)
            size += length
        return "\n".join(lines)

    async def catalog(self, *, limit: int = _ROWS) -> tuple[tuple[WorkRow, ...], str]:
        self.admit()
        limit = max(0, min(limit, _ROWS))
        records = self.agents.list() if self.agents is not None else []
        self._actors = (
            [self.agents._conversations[item.conversation_id].agent for item in records[:limit]]
            if self.agents is not None
            else []
        )
        self._refresh_policy()
        rows = [
            WorkRow("agent", item.conversation_id, item.status, _bounded(item.role, 512))
            for item in records[:limit]
        ]
        tasks = (
            await _joined(asyncio.create_task(asyncio.to_thread(self.service.list_tasks)))
            if self.service is not None
            else []
        )
        self.admit()
        rows.extend(
            WorkRow("task", item.task_id, item.status, _bounded(item.title, 512))
            for item in tasks[: max(0, limit - len(rows))]
        )
        notices = [f"{len(rows)} observed items. Refresh is explicit; background work continues."]
        if len(records) + len(tasks) > limit:
            notices.append("More items omitted by the 200-row display limit.")
        if self.agents is None:
            notices.append("Background agent owner unavailable.")
        if self.service is None:
            notices.append("Bound project task service unavailable; no storage was created.")
        return tuple(rows), " ".join(notices)

    def agent_fields(self, identity: str) -> tuple[tuple[str, str], ...]:
        assert self.agents is not None
        record: SubagentRecord = self.agents.get(identity)
        self._output_interrupted = record.status != "done" or record.cancelled
        actor = self.agents._conversations[identity].agent
        if not any(item is actor for item in self._actors):
            self._actors.append(actor)
        self._refresh_policy()
        provider = getattr(actor, "provider", None)
        output = (
            "[Output omitted: retained observation was clipped]"
            if record.output_truncated
            else _bounded(record.output)
        )
        error = record.error or "No error recorded"
        if len(error) >= self.agents._max_output_chars:
            error = "[Error omitted: retained observation may be clipped]"
        state = record.status + (
            " — blocked awaiting parent input" if record.status == "waiting_for_input" else ""
        )
        if record.cancelled:
            state += " — cancelled, not successful completion"
        return (
            ("Conversation", record.conversation_id),
            ("Parent", record.parent_id),
            ("Role", _bounded(record.role, 512)),
            ("State", state),
            (
                "Lifetime",
                "process-only runtime conversation; observed completion is not task verification",
            ),
            ("Provider", str(_provider_name(provider) or "unavailable")),
            ("Model", str(_model(provider) or "unavailable")),
            (
                "Budget authority",
                "No run ID is retained on this conversation snapshot. Context and usage or /usage reports the selected session's shared run; no per-child cap or bill is inferred.",
            ),
            ("Error", _bounded(error)),
            ("Retained output", output or "No output recorded"),
            (
                "Retained event kinds",
                ", ".join(event.type.value for event in record.events[-32:]) or "None recorded",
            ),
            (
                "Evidence boundary",
                "Only bounded output/error and event kinds are shown. System prompts, messages and opaque continuation are not displayed.",
            ),
        )

    async def inspect(
        self,
        kind: Literal["agent", "task"],
        identity: str,
        *,
        task_reader: Callable[[TaskService, str], tuple[TaskRecord, str]] = _task_details,
    ) -> tuple[tuple[tuple[str, str], ...], bool]:
        self.admit()
        if (
            not identity
            or len(identity) > 512
            or any(ord(character) < 32 for character in identity)
        ):
            raise ValueError("Invalid exact work identity")
        if kind == "agent":
            if self.agents is None:
                raise ValueError("Background agent owner unavailable")
            fields = self.agent_fields(identity)
        elif kind == "task":
            if self.service is None:
                raise ValueError("Bound project task service unavailable")
            record, output = await _joined(
                asyncio.create_task(asyncio.to_thread(task_reader, self.service, identity))
            )
            self._output_interrupted = record.status != "completed" or bool(
                record.metadata.get("error")
            )
            context = record.operation_context
            correlation = (
                f"Session {context['session_id']} · Run {context['run_id']} · Agent {context['agent_id']} · Operation {context['operation_id']}"
                if context is not None
                else "Unavailable; task is project-scoped, not attributed to the current run"
            )
            fields = (
                ("Task", record.task_id),
                ("State", record.status),
                ("Title", _bounded(record.title, 512)),
                (
                    "Lifetime",
                    "Persisted project task evidence; stored PID is not execution authority or task verification",
                ),
                ("Revision", str(record.revision)),
                (
                    "Return code",
                    str(record.return_code) if record.return_code is not None else "unavailable",
                ),
                ("Correlation", correlation),
                ("Error", _bounded(record.metadata.get("error", "No error recorded"))),
                ("Retained output", output),
                (
                    "Outcome",
                    (
                        "Unowned process outcome is unknown; no PID is adopted."
                        if record.status == "outcome_unknown"
                        else "Observed execution state only."
                    ),
                ),
            )
        else:
            raise ValueError("Unknown work kind")
        self.admit()
        return fields, self._output_interrupted
