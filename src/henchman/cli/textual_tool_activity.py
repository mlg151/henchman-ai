"""Bounded, display-only tool observations and keyboard evidence inspection."""

from __future__ import annotations

import hashlib
import json
import time
from collections import OrderedDict
from contextlib import suppress
from dataclasses import dataclass, field
from typing import Any, ClassVar
from uuid import uuid4

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, TextArea

from henchman.cli.evidence import runtime_evidence_redactor
from henchman.utils.evidence_redaction import (
    PRESERVE_IDENTITY,
    EvidenceRedactor,
    EvidenceStreamRedactor,
)
from henchman.utils.tool_results import tool_message_content

MAX_ENTRY_BYTES = 32 * 1024
MAX_CALL_BYTES = 64 * 1024
MAX_EVIDENCE_BYTES = 2 * 1024 * 1024
MAX_ENTRIES = 16
MAX_TOOL_VIEW_BYTES = 64 * 1024
MAX_TOOL_VIEW_CALLS = 64
MAX_TOOL_VIEW_LINES = 1000


def _project(text: str, policy: EvidenceRedactor, *, clipped: bool = False) -> str:
    stream = EvidenceStreamRedactor(policy)
    return stream.feed(text) + stream.finish(interrupted=clipped)


def _bounded(text: str, policy: EvidenceRedactor, limit: int) -> tuple[str, bool]:
    safe = policy.text(text)
    raw = safe.encode("utf-8", errors="replace")
    return raw[:limit].decode("utf-8", errors="ignore"), len(raw) > limit


def _label(value: Any, policy: EvidenceRedactor) -> str:
    safe, clipped = _bounded(str(value or "unknown"), policy, 256)
    return _project(safe, policy, clipped=clipped).replace("\n", " ") + ("…" if clipped else "")


def _current_label(value: str, policy: EvidenceRedactor) -> str:
    return _project(value[:-1], policy, clipped=True) + "…" if value.endswith("…") else policy.text(value)


@dataclass
class EvidenceEntry:
    number: int
    kind: str
    text: str
    clipped: bool


@dataclass
class ToolActivity:
    """An observation is neither a dispatch permit nor task verification."""

    key: str
    stream_key: str
    agent: str
    call: str
    name: str
    target: str = ""
    requested_at: float | None = None
    elapsed: float | None = None
    requests: int = 0
    results: int = 0
    outcome: str = "Requested"
    entries: list[EvidenceEntry] = field(default_factory=list)
    omitted: bool = False
    observed: int = 0
    revision: int = 0

    @property
    def bytes_retained(self) -> int:
        return sum(len(entry.text.encode()) for entry in self.entries)

    def append(self, kind: str, text: str, policy: EvidenceRedactor) -> None:
        self.observed += 1
        safe, clipped = _bounded(text, policy, MAX_ENTRY_BYTES)
        self.entries.append(EvidenceEntry(self.observed, kind, safe, clipped))
        while len(self.entries) > MAX_ENTRIES or self.bytes_retained > MAX_CALL_BYTES:
            self.entries.pop(0)
            self.omitted = True

    def summary(self, policy: EvidenceRedactor) -> str:
        target = f" · {_current_label(self.target, policy)}" if self.target else ""
        return f"{self.outcome} · {_current_label(self.name, policy)}{target} · {_current_label(self.agent, policy)}"

    def evidence(self, policy: EvidenceRedactor) -> str:
        duration = f"{self.elapsed:.3f}s request-to-result (includes waits)" if self.elapsed is not None else "unknown"
        lines = [f"Tool: {_current_label(self.name, policy)}", f"Agent: {_current_label(self.agent, policy)}", f"Call: {_current_label(self.call, policy)}",
                 f"Outcome: {self.outcome}",
                 f"Elapsed: {duration}", "Requirements acceptance is not established."]
        if not self.requests:
            lines.append("Request not observed; request timing and arguments are unavailable.")
        if self.results > 1 or self.requests > 1:
            lines.append("Multiple results or requests share this identity; outcome is unknown.")
        if self.outcome == "Interrupted":
            lines.append("Stream closed with no final result; effects may have occurred.")
        if self.omitted:
            lines.append("Earlier evidence omitted by the display retention limit.")
        for entry in self.entries:
            lines.extend((f"\n{entry.number}. {entry.kind}", _project(entry.text, policy, clipped=entry.clipped)))
            if entry.clipped:
                lines.append("[Remaining evidence omitted by the display size limit.]")
        return policy.text("\n".join(lines))


class ToolActivityStore:
    """Retain correlation with transcript rows, bounding their payload evidence."""

    def __init__(self) -> None:
        self.records: dict[str, ToolActivity] = {}
        self.changed: set[str] = set()
        self._retained: OrderedDict[str, ToolActivity] = OrderedDict()
        self._bytes = 0
        self.revision = 0

    def observe(self, message: Any, policy: EvidenceRedactor, *, request: bool) -> ToolActivity:
        self.changed = set()
        self.revision += 1
        data = message.tool_call if request else message.result
        identity = getattr(data, "id", None) if request else data.get("tool_call_id") if isinstance(data, dict) else None
        name = getattr(data, "name", None) if request else data.get("tool_name") if isinstance(data, dict) else None
        stream = message.stream_id or "uncorrelated"
        agent = message.source_agent
        # Without a call ID, separate arrivals cannot safely be merged.
        key = hashlib.sha256(json.dumps([stream, agent, identity if isinstance(identity, str) and identity else uuid4().hex]).encode()).hexdigest()
        record = self.records.get(key)
        if record is None:
            record = ToolActivity(key, hashlib.sha256(stream.encode()).hexdigest(),
                                  _label(agent, policy), _label(identity, policy), _label(name, policy))
            self.records[key] = record
        record.revision = self.revision
        previous_bytes = record.bytes_retained
        if request:
            args = getattr(data, "arguments", None)
            if isinstance(args, str):
                with suppress(ValueError):
                    args = json.loads(args)
            safe = policy.redact(args)
            record.requests += 1
            if record.requests == 1 and not record.results:
                record.requested_at = time.monotonic()
            if isinstance(safe, dict):
                for field_name in ("path", "file_path", "filename", "file", "command", "url"):
                    target = safe.get(field_name)
                    if isinstance(target, str):
                        record.target = _label(target, policy)
                        break
            record.append("Request arguments", json.dumps(safe, ensure_ascii=False, indent=2), policy)
        else:
            record.results += 1
            success = data.get("success") if isinstance(data, dict) else None
            record.outcome = "Succeeded" if success is True else "Failed" if success is False else "Unknown"
            if record.requested_at is not None and record.results == 1:
                record.elapsed = max(0.0, time.monotonic() - record.requested_at)
            safe = policy.redact(data, schema={"result": None, "tool_result": None, "tool_call_id": None,
                                              "tool_name": None, "success": PRESERVE_IDENTITY if type(success) is bool else None})
            if isinstance(safe, dict) and isinstance(safe.get("tool_result"), dict):
                try:
                    safe["tool_result"] = json.loads(tool_message_content(None, safe["tool_result"]))
                except ValueError:
                    safe["tool_result"] = "Typed evidence is unavailable: invalid projected payload."
            if isinstance(safe, dict) and isinstance(safe.get("result"), str):
                record.append("Result output", safe.pop("result"), policy)
            record.append("Result details", json.dumps(safe, ensure_ascii=False, indent=2), policy)
        if record.requests > 1 or record.results > 1:
            record.outcome = "Unknown"
        self.changed.add(key)
        self._bytes += record.bytes_retained - previous_bytes
        self._retained[key] = record
        self._retained.move_to_end(key)
        while self._bytes > MAX_EVIDENCE_BYTES and self._retained:
            oldest, item = self._retained.popitem(last=False)
            self._bytes -= item.bytes_retained
            item.entries.clear()
            item.omitted = True
            self.changed.add(oldest)
        return record

    def close(self, stream: str) -> None:
        self.changed = set()
        identity = hashlib.sha256(stream.encode()).hexdigest()
        for record in self.records.values():
            if record.stream_key == identity and not record.results:
                record.outcome = "Interrupted"
                self.changed.add(record.key)

    def clear(self) -> None:
        """Clear canonical payloads too, including records held by open inspectors."""
        for record in self.records.values():
            record.entries.clear()
            record.omitted = True
        self.records.clear()
        self._retained.clear()
        self.changed.clear()
        self._bytes = 0
        self.revision += 1

    def tool_view(self, policy: EvidenceRedactor, minimum_revision: int = 0) -> str:
        """Project a bounded recent view, never an independent accumulating log."""
        frames: list[str] = []
        size = 0
        omitted = len(self.records) > len(self._retained)
        for record in reversed(self._retained.values()):
            if record.revision < minimum_revision:
                break
            if len(frames) >= MAX_TOOL_VIEW_CALLS or size >= MAX_TOOL_VIEW_BYTES:
                omitted = True
                break
            # Bound displayed columns before RichLog expands tabs; otherwise
            # its rendered-line cap can silently discard our omission notice.
            rendered = record.evidence(policy).expandtabs(8)
            raw = rendered.encode()
            remaining = MAX_TOOL_VIEW_BYTES - size
            if len(raw) > remaining:
                rendered = raw[:remaining].decode("utf-8", errors="ignore")
                omitted = True
            frames.append(rendered)
            size += min(len(raw), remaining)
        if not frames:
            return ""
        body = "\n\n────────\n\n".join(reversed(frames))
        lines = body.splitlines()
        if len(lines) > MAX_TOOL_VIEW_LINES:
            body = "\n".join(lines[:MAX_TOOL_VIEW_LINES])
            omitted = True
        header = "Recent tool evidence — inspect a call in Chat for retained details."
        if omitted:
            header += "\nSome earlier or oversized evidence is omitted from this bounded view."
        return header + "\n\n" + body


class ToolEvidenceScreen(ModalScreen[None]):
    """Read-only evidence; Escape/Back return to the originating transcript row."""

    DEFAULT_CSS = """
    ToolEvidenceScreen { align: center middle; }
    #tool-evidence-dialog { width: 95%; height: 90%; border: solid $accent; background: $surface; padding: 0 1; }
    #tool-evidence { height: 1fr; }
    #tool-evidence-back { height: 3; }
    """
    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [("escape", "back", "Back")]

    def __init__(self, record: ToolActivity) -> None:
        super().__init__()
        self.record = record

    def compose(self) -> ComposeResult:
        with Vertical(id="tool-evidence-dialog"):
            yield Label("Tool evidence · read only · Esc: Back", markup=False)
            yield TextArea(self.record.evidence(runtime_evidence_redactor(self.app)), read_only=True, id="tool-evidence")
            yield Button("Back", id="tool-evidence-back")

    def on_mount(self) -> None:
        self.query_one(TextArea).focus()
        self.set_interval(0.5, self.refresh_evidence)

    def refresh_evidence(self) -> None:
        area = self.query_one(TextArea)
        text = self.record.evidence(runtime_evidence_redactor(self.app))
        if area.text != text:
            area.load_text(text)

    def action_back(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "tool-evidence-back":
            self.action_back()
