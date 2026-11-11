"""Display projections of runtime events, separate from executable state."""

from __future__ import annotations

from typing import Any

from henchman.core.events import AgentEvent, EventType
from henchman.utils.evidence_redaction import (
    PRESERVE_IDENTITY,
    EvidenceRedactor,
    EvidenceStreamRedactor,
)
from henchman.utils.tool_results import TOOL_RESULT_SCHEMA

_DATA_FIELDS: dict[str, Any] = dict.fromkeys((
    "arguments", "result", "preview", "content", "message", "error", "code", "task", "status",
    "finish_reason", "scope", "usage", "task_verified", "success", "duration", "tokens",
    "prompt_tokens", "completion_tokens", "total_tokens", "cached_tokens",
    "cache_creation_tokens", "reasoning_tokens", "usage_source",
))
_DATA_FIELDS.update(dict.fromkeys(("id", "tool_call_id", "tool_name", "name", "from", "to", "agent", "agent_id")))
_EVENT_IDENTITIES = {
    # Tool names are provider-controlled display evidence, including unknown
    # names. Only call IDs carry request/result correlation authority here.
    EventType.TOOL_CALL_REQUEST: ("id",),
    EventType.TOOL_CALL_RESULT: ("id", "tool_call_id"),
    EventType.AGENT_DELEGATED: ("from", "to"),
    EventType.AGENT_MESSAGE: ("from", "to"),
    EventType.AGENT_STARTED: ("agent", "agent_id"),
    EventType.AGENT_COMPLETED: ("agent", "agent_id"),
}
_DATA_FIELDS["usage"] = dict.fromkeys(("prompt_tokens", "completion_tokens", "total_tokens", "cached_tokens", "cache_creation_tokens", "reasoning_tokens"))
_DATA_FIELDS["tool_result"] = TOOL_RESULT_SCHEMA
_CONTROL_VALUES = {
    "finish_reason": {"stop", "tool_calls", "length", "content_filter", "error", "interrupted", "cancelled"},
    "status": {"completed", "responded", "failed", "no_work_done", "stalled", "timed_out", "cancelled"},
    "scope": {"run", "agent", "request"},
}


def event_data(value: Any) -> Any:
    """Extract an evidence object without assigning to the original event."""
    if isinstance(value, BaseException):
        return str(value)
    if hasattr(value, "__dict__"):
        return vars(value)
    return value


class EventEvidenceRedactor:
    """Keep independent stream buffers per agent and content/thought channel."""

    def __init__(self, redactor: EvidenceRedactor, *, finish_all: bool = False) -> None:
        self.redactor = redactor
        self._finish_all = finish_all
        self._streams: dict[tuple[EventType, str | None], EvidenceStreamRedactor] = {}

    def project(self, event: AgentEvent) -> list[AgentEvent]:
        """Return display copies while leaving execution arguments untouched."""
        data = event_data(event.data)
        self.redactor.register_config(data)
        output: list[AgentEvent] = []
        if event.type in (EventType.CONTENT, EventType.THOUGHT) and isinstance(data, str):
            key = (event.type, event.source_agent)
            stream = self._streams.setdefault(key, EvidenceStreamRedactor(self.redactor))
            data = stream.feed(data)
        else:
            run_scope = isinstance(data, dict) and data.get("scope") == "run"
            if event.type == EventType.AGENT_COMPLETED and run_scope:
                output.extend(self.flush(interrupted=data.get("status") not in ("completed", "responded")))
            if event.type == EventType.FINISHED:
                reason = data.get("finish_reason") if isinstance(data, dict) else data
                output.extend(self.flush(
                    None if self._finish_all or run_scope else event.source_agent,
                    interrupted=reason not in (None, "stop", "tool_calls"),
                ))
            schema = {**_DATA_FIELDS, **dict.fromkeys(_EVENT_IDENTITIES.get(event.type, ()), PRESERVE_IDENTITY)}
            if event.type in (EventType.FINISHED, EventType.AGENT_COMPLETED) and isinstance(data, dict):
                schema.update({
                    name: PRESERVE_IDENTITY for name, allowed in _CONTROL_VALUES.items()
                    if isinstance(data.get(name), str) and data[name] in allowed
                })
            if event.type == EventType.FINISHED and isinstance(data, str) and data in _CONTROL_VALUES["finish_reason"]:
                data = self.redactor.redact(data, schema=PRESERVE_IDENTITY)
            else:
                data = self.redactor.redact(data, schema=schema)
            if event.type == EventType.TOOL_CALL_RESULT and isinstance(data, dict):
                raw = event_data(event.data)
                if isinstance(data.get("result"), str) and isinstance(raw.get("preview"), str):
                    # Producers retain full execution output and may truncate a
                    # preview through a secret. Project before truncation here.
                    data["preview"] = data["result"][:len(raw["preview"])]
        output.append(AgentEvent(event.type, data, event.source_agent))
        return output

    def flush(
        self, source_agent: str | None = None, *, interrupted: bool = True,
    ) -> list[AgentEvent]:
        """Finish one agent's channels, or all channels when no agent is given."""
        output: list[AgentEvent] = []
        for key, stream in list(self._streams.items()):
            event_type, agent_id = key
            if source_agent is not None and agent_id != source_agent:
                continue
            text = stream.finish(interrupted=interrupted)
            if text:
                output.append(AgentEvent(event_type, text, agent_id))
            del self._streams[key]
        return output
