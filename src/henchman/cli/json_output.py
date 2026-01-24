"""JSON output renderer for Henchman-AI.

This module provides JSON output formatting for headless mode and scripting.
"""

from __future__ import annotations

import json
from typing import Any

from rich.console import Console

from henchman.core.events import AgentEvent


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

    def __init__(self, console: Console | None = None) -> None:
        """Initialize the JSON output renderer.

        Args:
            console: Rich console for output (optional).
        """
        self.console = console or Console()

    def render(self, event: AgentEvent) -> None:
        """Render an agent event as JSON.

        Args:
            event: The agent event to render.
        """
        output = self._event_to_dict(event)
        self.console.print(json.dumps(output, ensure_ascii=False))

    def _event_to_dict(self, event: AgentEvent) -> dict[str, Any]:
        """Convert an agent event to a dictionary.

        Args:
            event: The agent event to convert.

        Returns:
            A dictionary representation of the event.
        """
        # Convert enum to string name
        result: dict[str, Any] = {"type": event.type.name.lower()}

        if event.data is not None:
            # Handle different data types
            if isinstance(event.data, str):
                result["data"] = event.data
            elif hasattr(event.data, "__dict__"):
                result["data"] = event.data.__dict__
            elif isinstance(event.data, dict):
                result["data"] = event.data
            else:
                result["data"] = str(event.data)

        return result

    def render_stream_json(self, event: AgentEvent) -> None:
        """Render an agent event as streaming JSON (one event per line).

        Args:
            event: The agent event to render.
        """
        output = self._event_to_dict(event)
        self.console.print(json.dumps(output, ensure_ascii=False))

    def render_final_json(self, events: list[AgentEvent]) -> None:
        """Render a list of agent events as a single JSON array.

        Args:
            events: List of agent events to render.
        """
        output = [self._event_to_dict(event) for event in events]
        self.console.print(json.dumps(output, ensure_ascii=False, indent=2))
