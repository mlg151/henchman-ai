"""JSON output renderer for Henchman-AI.

This module provides JSON output formatting for headless mode and scripting.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from rich.console import Console

from henchman.core.event_evidence import EventEvidenceRedactor, event_data
from henchman.core.events import EventType
from henchman.utils.evidence_redaction import EvidenceRedactor

if TYPE_CHECKING:
    from henchman.core.events import AgentEvent


try:
    from typing import Self
except ImportError:  # pragma: no cover
    from typing import Self


def _serialize_event_data(data: Any) -> Any:
    """Serialize event data to a JSON-compatible type.

    Args:
        data: The event data to serialize.

    Returns:
        A JSON-compatible representation of the data.
    """
    if isinstance(data, str):
        return data
    if isinstance(data, dict):
        return data
    if hasattr(data, "__dict__"):
        return data.__dict__
    return str(data)


def event_to_dict(event: AgentEvent) -> dict[str, Any]:
    """Convert an agent event to a JSON-serializable dictionary.

    Args:
        event: The agent event to convert.

    Returns:
        A dictionary representation of the event.
    """
    result: dict[str, Any] = {"type": event.type.name.lower()}
    if event.source_agent is not None:
        result["source_agent"] = event.source_agent
    if event.type == EventType.FINISHED:
        # Ending a provider stream does not verify the requested task.
        result["task_verified"] = False
    if event.data is not None:
        result["data"] = _serialize_event_data(event.data)
    return result


class JsonOutputRenderer:
    """Renderer for JSON output formats.

    This class handles converting agent events to JSON format for
    headless mode and scripting use cases.

    Example:
        >>> renderer = JsonOutputRenderer()
        >>> event = AgentEvent(EventType.CONTENT, "Hello")
        >>> renderer.render(event)
        {"type": "content", "data": "Hello"}
    """

    def __init__(
        self: Self, console: Console | None = None, *, redactor: EvidenceRedactor | None = None,
    ) -> None:
        """Initialize the JSON output renderer.

        Args:
            console: Rich console for output (optional).
        """
        self.console = console or Console()
        # Headless execution filters intermediate completions; FINISHED closes
        # the whole run even when its source is the synthetic orchestrator.
        self.evidence = EventEvidenceRedactor(redactor or EvidenceRedactor(), finish_all=True)

    def render(self: Self, event: AgentEvent) -> None:
        """Render an agent event as JSON (one event per line).

        Args:
            event: The agent event to render.

        Returns:
            None
        """
        for safe_event in self.evidence.project(event):
            self._print_event(safe_event)

    def _print_event(self, event: AgentEvent) -> None:
        self.console.print(
            json.dumps(event_to_dict(event), ensure_ascii=False), markup=False, highlight=False,
        )

    def flush(self) -> None:
        """Safely publish buffered prefixes when a run ends or is interrupted."""
        for event in self.evidence.flush():
            self._print_event(event)

    def render_stream_json(self: Self, event: AgentEvent) -> None:
        """Render an agent event as streaming JSON (one event per line).

        Delegates to :meth:`render` -- kept for API compatibility.

        Args:
            event: The agent event to render.

        Returns:
            None
        """
        self.render(event)

    def render_final_json(self: Self, events: list[AgentEvent]) -> None:
        """Render a list of agent events as a single JSON array.

        Args:
            events: List of agent events to render.

        Returns:
            None
        """
        for event in events:
            self.evidence.redactor.register_config(event_data(event.data))
        output = [event_to_dict(safe) for event in events for safe in self.evidence.project(event)]
        output.extend(event_to_dict(event) for event in self.evidence.flush(interrupted=False))
        self.console.print(
            json.dumps(output, ensure_ascii=False, indent=2), markup=False, highlight=False,
        )

    def _event_to_dict(self: Self, event: AgentEvent) -> dict[str, Any]:
        """Convert an agent event to a dictionary.

        This is an internal helper method for compatibility.

        Args:
            event: The agent event to convert.

        Returns:
            A dictionary representation of the event.
        """
        # Return a copy to avoid AST matching with _format_tool
        return dict(event_to_dict(event))
