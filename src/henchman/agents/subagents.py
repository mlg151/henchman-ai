"""Session-owned background conversations with scoped, event-driven mailboxes."""

from __future__ import annotations

import asyncio
import builtins
from collections import deque
from collections.abc import AsyncIterator, Callable, Iterable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field, replace
from typing import Any, Literal
from uuid import uuid4

from henchman.core.events import AgentEvent, EventType

SubagentStatus = Literal["running", "idle", "waiting_for_input", "errored", "done"]
_ACTOR: ContextVar[str | None] = ContextVar("henchman_subagent_actor", default=None)


def current_subagent_actor() -> str | None:
    """Return the current child identity, or None outside an explicit actor context."""
    return _ACTOR.get()


@contextmanager
def subagent_actor(conversation_id: str) -> Iterator[None]:
    """Identify the caller without trusting model-supplied sender parameters."""
    token = _ACTOR.set(conversation_id)
    try:
        yield
    finally:
        _ACTOR.reset(token)


@dataclass(frozen=True)
class SubagentRecord:
    """Immutable public snapshot of one independent conversation."""

    conversation_id: str
    parent_id: str
    role: str
    system_prompt: str
    tools: tuple[str, ...]
    status: SubagentStatus = "running"
    output: str = ""
    output_truncated: bool = False
    error: str | None = None
    cancelled: bool = False
    events: tuple[AgentEvent, ...] = ()

    def as_dict(self) -> dict[str, object]:
        """Return JSON-safe status and bounded results for management tools."""
        return {
            "conversation_id": self.conversation_id,
            "parent_id": self.parent_id,
            "role": self.role,
            "tools": list(self.tools),
            "status": self.status,
            "output": self.output,
            "output_truncated": self.output_truncated,
            "error": self.error,
            "cancelled": self.cancelled,
        }


@dataclass(frozen=True)
class SubagentNotification:
    """A child result, assistance request, or message delivered to its parent."""

    conversation_id: str
    parent_id: str
    status: SubagentStatus
    message: str
    role: str

    def as_prompt(self) -> str:
        """Represent remote work as attributed data for a subsequent parent turn."""
        return (
            f"Subagent update from {self.conversation_id} ({self.role}), "
            f"status={self.status}:\n{self.message}"
        )


@dataclass
class _Conversation:
    record: SubagentRecord
    agent: Any
    inbox: asyncio.Queue[str] = field(default_factory=asyncio.Queue)
    task: asyncio.Task[None] | None = None
    events: deque[AgentEvent] = field(default_factory=lambda: deque(maxlen=32))


class BackgroundSubagentManager:
    """Own workers and queues while callers retain provider and tool-loop wiring.

    Factories receive role, custom system prompt, validated tool names, and a
    unique conversation ID. Runners consume the resulting agent and one message.
    A conversation runs at most one message at a time and retains its agent
    history across follow-ups. Tool authorization remains in the supplied runner.
    """

    def __init__(
        self,
        factory: Callable[[str, str, list[str], str], Any],
        runner: Callable[[Any, str], AsyncIterator[AgentEvent]],
        *,
        available_tools: Callable[[str], Iterable[str]],
        parent_id: str = "tech_lead",
        max_output_chars: int = 32768,
    ) -> None:
        """Initialize one runtime's independent conversations and notifications."""
        if max_output_chars < 1:
            raise ValueError("max_output_chars must be positive")
        self.parent_id = parent_id
        self._factory = factory
        self._runner = runner
        self._available_tools = available_tools
        self._max_output_chars = max_output_chars
        self._conversations: dict[str, _Conversation] = {}
        self._notifications: dict[str, asyncio.Queue[SubagentNotification]] = {}
        self._cancelling: set[str] = set()
        self._closed = False

    @property
    def actor_id(self) -> str:
        """Return the execution context's caller, defaulting to the primary."""
        return _ACTOR.get() or self.parent_id

    def is_subagent(self) -> bool:
        """Return whether this call originates from an owned child worker."""
        return self.actor_id in self._conversations

    def _descendant(self, conversation_id: str, ancestor: str) -> bool:
        current = self._conversations.get(conversation_id)
        while current is not None:
            if current.record.parent_id == ancestor:
                return True
            current = self._conversations.get(current.record.parent_id)
        return False

    def _require_access(self, conversation_id: str, *, control: bool = False) -> _Conversation:
        actor = self.actor_id
        if (
            actor != self.parent_id
            and not self._descendant(conversation_id, actor)
            and (control or conversation_id != actor)
        ):
            raise PermissionError(
                "Subagents may access only their own conversation and descendants"
            )
        try:
            return self._conversations[conversation_id]
        except KeyError as exc:
            raise ValueError(f"Unknown subagent conversation: {conversation_id}") from exc

    def _scope(self) -> set[str]:
        if self.is_subagent():
            return set(self._conversations[self.actor_id].record.tools) & set(
                self._available_tools(self.actor_id)
            )
        if self.actor_id != self.parent_id:
            raise PermissionError("Unknown subagent caller")
        return set(self._available_tools(self.actor_id))

    def _is_cancelling(self, conversation_id: str) -> bool:
        return any(
            conversation_id == ancestor or self._descendant(conversation_id, ancestor)
            for ancestor in self._cancelling
        )

    def spawn(
        self,
        task: str,
        *,
        role: str,
        system_prompt: str,
        tools: list[str],
    ) -> SubagentRecord:
        """Start a distinct conversation immediately within the caller's scope."""
        if self._closed:
            raise RuntimeError("Subagent manager is closed")
        if self._is_cancelling(self.actor_id):
            raise RuntimeError("This subagent tree is being cancelled")
        if not all(
            isinstance(value, str) and value.strip() for value in (task, role, system_prompt)
        ):
            raise ValueError("task, role, and system_prompt must be non-empty strings")
        if not isinstance(tools, list) or not all(
            isinstance(name, str) and name.strip() for name in tools
        ):
            raise ValueError("tools must be an explicit list of non-empty tool names")
        scope = self._scope()
        if self.is_subagent() and "invoke_subagent" not in scope:
            raise PermissionError("This subagent cannot launch other subagents")
        disallowed = set(tools) - scope
        if disallowed:
            raise ValueError(
                f"Requested tools outside caller scope: {', '.join(sorted(disallowed))}"
            )
        asyncio.get_running_loop()
        conversation_id = f"subagent-{uuid4().hex}"
        tools = list(dict.fromkeys(tools))
        agent = self._factory(role, system_prompt, tools, conversation_id)
        record = SubagentRecord(conversation_id, self.actor_id, role, system_prompt, tuple(tools))
        conversation = _Conversation(record=record, agent=agent)
        conversation.inbox.put_nowait(task)
        self._conversations[conversation_id] = conversation
        self._start_worker(conversation)
        return record

    def get(self, conversation_id: str) -> SubagentRecord:
        """Inspect an accessible conversation without mutating its history."""
        return self._require_access(conversation_id).record

    def list(self) -> list[SubagentRecord]:
        """List conversations controlled by this caller in stable creation order."""
        return [
            conversation.record
            for conversation_id, conversation in self._conversations.items()
            if self.actor_id == self.parent_id or self._descendant(conversation_id, self.actor_id)
        ]

    def has_running_work(self, parent_id: str | None = None) -> bool:
        """Check owned work without polling or awaiting a provider response."""
        parent_id = self._notification_parent(parent_id)
        return any(
            self._descendant(conversation_id, parent_id)
            and conversation.record.status in ("running", "idle", "waiting_for_input")
            for conversation_id, conversation in self._conversations.items()
        )

    async def send_message(self, conversation_id: str, message: str) -> SubagentRecord | None:
        """Queue a follow-up, or notify the sender's parent without impersonation."""
        if self._closed:
            raise RuntimeError("Subagent manager is closed")
        if self._is_cancelling(conversation_id) or self._is_cancelling(self.actor_id):
            raise RuntimeError("This subagent tree is being cancelled")
        if not isinstance(message, str) or not message.strip():
            raise ValueError("message must be a non-empty string")
        if self.is_subagent():
            source = self._conversations[self.actor_id]
            if conversation_id in ("parent", source.record.parent_id):
                self._publish(source, message)
                return None
        conversation = self._require_access(conversation_id)
        conversation.inbox.put_nowait(message)
        if conversation.task is None or conversation.task.done():
            conversation.record = replace(
                conversation.record,
                status="idle",
                cancelled=False,
                error=None,
            )
            self._start_worker(conversation)
        return conversation.record

    async def request_input(self, question: str) -> str:
        """Suspend a child tool call until its parent provides an actual answer."""
        if not self.is_subagent():
            raise PermissionError("Only a running subagent can request parent input")
        if not isinstance(question, str) or not question.strip():
            raise ValueError("question must be a non-empty string")
        conversation = self._conversations[self.actor_id]
        conversation.record = replace(conversation.record, status="waiting_for_input")
        self._publish(conversation, question)
        answer = await conversation.inbox.get()
        conversation.record = replace(conversation.record, status="running")
        return answer

    async def cancel(self, conversation_id: str) -> SubagentRecord:
        """Cancel and join a controlled worker and all of its descendants."""
        conversation = self._require_access(conversation_id, control=True)
        self._cancelling.add(conversation_id)
        try:
            for descendant in reversed(tuple(self._conversations.values())):
                if self._descendant(descendant.record.conversation_id, conversation_id):
                    await self._cancel_one(descendant)
            await self._cancel_one(conversation)
        finally:
            self._cancelling.discard(conversation_id)
        return conversation.record

    async def _cancel_one(self, conversation: _Conversation) -> None:
        """Join an already-authorized worker without permitting a late restart."""
        task = conversation.task
        active = task is not None and not task.done()
        if active:
            assert task is not None
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        while not conversation.inbox.empty():
            conversation.inbox.get_nowait()
        if active or conversation.record.status not in ("done", "errored"):
            conversation.record = replace(conversation.record, status="done", cancelled=True)
            self._publish(conversation, "Subagent cancelled.")

    async def close(self) -> None:
        """Prevent new work and cancel/join every worker before runtime shutdown."""
        if self.actor_id != self.parent_id:
            raise PermissionError("Only the primary may close the subagent runtime")
        self._closed = True
        await self.cancel_all()

    async def cancel_all(self) -> None:
        """Cancel and join controlled workers while keeping the manager reusable."""
        conversation_ids = [record.conversation_id for record in self.list()]
        actor = self.actor_id
        self._cancelling.add(actor)
        try:
            for conversation_id in reversed(conversation_ids):
                await self._cancel_one(self._conversations[conversation_id])
        finally:
            self._cancelling.discard(actor)

    def clear_notifications(self) -> None:
        """Discard queued updates when the primary intentionally resets its session."""
        if self.actor_id != self.parent_id:
            raise PermissionError("Only the primary may reset subagent notifications")
        self._notifications.clear()

    def _notification_parent(self, parent_id: str | None) -> str:
        parent_id = self.actor_id if parent_id is None else parent_id
        if parent_id != self.actor_id and self.actor_id != self.parent_id:
            raise PermissionError("Cannot consume another agent's notifications")
        return parent_id

    def _queue(self, parent_id: str | None = None) -> asyncio.Queue[SubagentNotification]:
        parent_id = self._notification_parent(parent_id)
        return self._notifications.setdefault(parent_id, asyncio.Queue())

    async def wait_for_notification(self, parent_id: str | None = None) -> SubagentNotification:
        """Await the next parent update without a polling loop."""
        return await self._queue(parent_id).get()

    def drain_notifications(
        self, parent_id: str | None = None
    ) -> builtins.list[SubagentNotification]:
        """Consume currently queued updates synchronously at a safe turn boundary."""
        queue = self._queue(parent_id)
        notifications: builtins.list[SubagentNotification] = []
        while not queue.empty():
            notifications.append(queue.get_nowait())
        return notifications

    def pop_notifications(
        self, parent_id: str | None = None
    ) -> builtins.list[SubagentNotification]:
        """Compatibility alias for draining queued updates."""
        return self.drain_notifications(parent_id)

    def _publish(self, conversation: _Conversation, message: str) -> None:
        record = conversation.record
        notification = SubagentNotification(
            record.conversation_id,
            record.parent_id,
            record.status,
            message[: self._max_output_chars],
            record.role,
        )
        queue = self._notifications.setdefault(record.parent_id, asyncio.Queue())
        queue.put_nowait(notification)

    def _start_worker(self, conversation: _Conversation) -> None:
        conversation.task = asyncio.create_task(self._worker(conversation))

    async def _worker(self, conversation: _Conversation) -> None:
        with subagent_actor(conversation.record.conversation_id):
            try:
                while not conversation.inbox.empty():
                    prompt = conversation.inbox.get_nowait()
                    conversation.record = replace(
                        conversation.record,
                        status="running",
                        output="",
                        output_truncated=False,
                        error=None,
                        cancelled=False,
                    )
                    from .orchestrator_execution import closing_event_stream

                    async with closing_event_stream(
                        self._runner(conversation.agent, prompt)
                    ) as events:
                        async for event in events:
                            self._record_event(conversation, event)
                    status: SubagentStatus = "errored" if conversation.record.error else "done"
                    conversation.record = replace(conversation.record, status=status)
                    if status == "errored":
                        self._discard_pending(conversation)
                    self._publish(
                        conversation, conversation.record.error or conversation.record.output
                    )
                    if status == "errored":
                        break
            except asyncio.CancelledError:
                conversation.record = replace(conversation.record, status="done", cancelled=True)
                raise
            except Exception as exc:
                self._discard_pending(conversation)
                conversation.record = replace(
                    conversation.record,
                    status="errored",
                    error=f"{type(exc).__name__}: {exc}"[: self._max_output_chars],
                )
                self._publish(conversation, conversation.record.error or "Subagent failed")

    @staticmethod
    def _discard_pending(conversation: _Conversation) -> None:
        """Prevent messages queued before an error from replaying after recovery."""
        while not conversation.inbox.empty():
            conversation.inbox.get_nowait()

    def _record_event(self, conversation: _Conversation, event: AgentEvent) -> None:
        text = str(event.data or "")
        conversation.events.append(
            AgentEvent(
                event.type,
                text[: min(4096, self._max_output_chars)],
                source_agent=conversation.record.conversation_id,
            )
        )
        record = conversation.record
        output = record.output
        truncated = record.output_truncated
        error = record.error
        if event.type == EventType.CONTENT:
            combined = output + text
            output = combined[: self._max_output_chars]
            truncated = truncated or len(combined) > self._max_output_chars
        elif event.type == EventType.ERROR:
            error = text[: self._max_output_chars]
        conversation.record = replace(
            record,
            output=output,
            output_truncated=truncated,
            error=error,
            events=tuple(conversation.events),
        )
