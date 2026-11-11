"""Owned display lifecycle state; no execution or approval authority."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

PromptKind = Literal["question", "approval"]
Outcome = Literal["idle", "cancelled", "failed"]


@dataclass(frozen=True)
class ActivitySnapshot:
    label: str
    decision_action: bool = False


class ActivityState:
    """Only a matching owner can settle its worker or prompt display state."""

    def __init__(self, changed: Callable[[], None]) -> None:
        self._changed = changed
        self._owner: object | None = None
        self._cancel_owner: object | None = None
        self._terminal = "Idle"
        self._closing = False
        self._failed = False
        self._prompt_owner: object | None = None
        self._prompt_kind: PromptKind | None = None
        self._prompt_ready = False
        self._prompt_retiring = False
        self._queued = 0

    def begin(self) -> object:
        owner = object()
        self._owner = owner
        self._cancel_owner = None
        self._terminal = "Idle"
        self._failed = False
        self._changed()
        return owner

    def cancel(self, owner: object) -> None:
        if owner is self._owner:
            self._cancel_owner = owner
            self._changed()

    def finish(self, owner: object, outcome: Outcome) -> None:
        if owner is self._owner:
            self._owner = self._cancel_owner = None
            if outcome == "idle" and self._failed:
                outcome = "failed"
            self._terminal = {"idle": "Idle", "cancelled": "Cancelled", "failed": "Stopped with error"}[outcome]
            self._changed()

    def record_failure(self, owner: object) -> None:
        if owner is self._owner:
            self._failed = True

    def shutdown(self) -> None:
        self._closing = True
        self._changed()

    def queued(self, count: int) -> None:
        self._queued = max(0, count)
        self._changed()

    def prompt(self, owner: object, kind: PromptKind, *, ready: bool) -> None:
        self._prompt_owner = owner
        self._prompt_kind = kind
        self._prompt_ready = ready
        self._prompt_retiring = False
        self._changed()

    def retire_prompt(self, owner: object) -> None:
        if owner is self._prompt_owner:
            self._prompt_ready = False
            self._prompt_retiring = True
            self._changed()

    def clear_prompt(self, owner: object) -> None:
        if owner is self._prompt_owner:
            self._prompt_owner = self._prompt_kind = None
            self._prompt_ready = self._prompt_retiring = False
            self._changed()

    def snapshot(self) -> ActivitySnapshot:
        if self._closing:
            return ActivitySnapshot("Closing…")
        if self._owner is not None and self._cancel_owner is self._owner:
            return ActivitySnapshot("Cancelling…")
        queued = f" · {self._queued} queued decision{'s' if self._queued != 1 else ''}" if self._queued else ""
        if self._prompt_kind is not None and not self._prompt_retiring:
            noun = "answer" if self._prompt_kind == "question" else "approval"
            label = f"Waiting for {noun}" if self._prompt_ready else "Opening decision dialog…"
            action = "Answer question" if self._prompt_kind == "question" else "Review approval"
            return ActivitySnapshot(label + (f" · F4: {action}" if self._prompt_ready else "") + queued, self._prompt_ready)
        if self._prompt_retiring and self._queued:
            return ActivitySnapshot("Close the current dialog to continue" + queued, True)
        if self._queued:
            return ActivitySnapshot("Opening decision dialog…" + queued)
        if self._owner is not None:
            return ActivitySnapshot("Running")
        return ActivitySnapshot(self._terminal)


def activity_for(runtime: Any) -> ActivityState:
    """Attach display state without constructing runtime services or reading disk."""
    state = getattr(runtime, "_activity_state", None)
    if not isinstance(state, ActivityState):
        state = ActivityState(lambda: refresh_activity(runtime))
        runtime._activity_state = state
    return state


def refresh_activity(runtime: Any) -> None:
    from henchman.cli.textual_widgets import StatusBar

    if getattr(runtime, "is_running", False) is not True:
        return
    query = getattr(runtime, "query", None)
    if callable(query):
        snapshot = activity_for(runtime).snapshot()
        for bar in query(StatusBar):
            bar.activity_text = snapshot.label
            bar.decision_action = snapshot.decision_action
