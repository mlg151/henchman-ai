"""Shared evaluation observations and runtime outcomes."""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from henchman.core.events import AgentEvent


class EventObserver:
    """Invoke an optional observer while distinguishing its failures from runtime errors."""

    def __init__(self, callback: Callable[[AgentEvent], None] | None) -> None:
        self.callback = callback
        self.failed = False

    def __call__(self, event: AgentEvent) -> None:
        if self.callback is None:
            return
        try:
            self.callback(event)
        except BaseException:
            self.failed = True
            raise


@dataclass
class ToolLog:
    """One observed tool request and its correlated execution result."""

    tool_name: str
    arguments: dict[str, Any]
    result: str
    success: bool
    timestamp: datetime = field(default_factory=datetime.now)
    source_agent: str | None = None
    tool_call_id: str | None = None
    request_index: int | None = None
    result_index: int | None = None


@dataclass
class EvalResult:
    """Runtime outcome; success alone does not establish task correctness."""

    prompt: str
    final_response: str
    tool_logs: list[ToolLog]
    events: list[AgentEvent]
    duration_ms: float
    tokens_in: int | None
    tokens_out: int | None
    success: bool
    error: str | None = None
    diagnostics: list[str] = field(default_factory=list)
