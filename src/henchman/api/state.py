"""Global state for Henchman-AI API."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from henchman.config import Settings
    from henchman.core import Agent
    from henchman.providers import ProviderRegistry


class State:
    """Global application state."""

    def __init__(self) -> None:
        self.settings: Settings | None = None
        self.provider_registry: ProviderRegistry | None = None
        self.agent: Agent | None = None
        self.api_keys: set[str] = set()
        self.metrics: dict[str, int | float] = {
            "requests_total": 0,
            "requests_successful": 0,
            "requests_failed": 0,
            "tokens_prompt": 0,
            "tokens_completion": 0,
            "tokens_total": 0,
            "tool_calls_total": 0,
            "tool_calls_successful": 0,
            "tool_calls_failed": 0,
        }


# Global state instance
state = State()
