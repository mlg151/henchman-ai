"""Typed, advisory transcript correlation; journal storage remains authoritative."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from henchman.core.operation_recovery import OperationContext, _identity
from henchman.core.session_models import SessionMessage, message_from_dict


@dataclass(frozen=True)
class OperationSessionReference:
    store_id: str
    project_hash: str
    session_id: str
    version: int = 1

    def __post_init__(self) -> None:
        for value in (self.store_id, self.project_hash, self.session_id):
            _identity(value)
        if type(self.version) is not int or self.version != 1:
            raise ValueError("Unsupported operation reference version")


@dataclass(frozen=True)
class OperationBinding:
    operation_id: str
    context: OperationContext
    assistant_index: int
    conversation_id: str | None = None

    def __post_init__(self) -> None:
        _identity(self.operation_id)
        if not isinstance(self.context, OperationContext):
            raise ValueError("Invalid operation context")
        if type(self.assistant_index) is not int or self.assistant_index < 0:
            raise ValueError("Invalid assistant correlation")
        if self.conversation_id is not None:
            _identity(self.conversation_id)


@dataclass(frozen=True)
class OperationConversation:
    """Specialist evidence kept out of the primary provider's conversation."""

    id: str
    messages: tuple[SessionMessage, ...]

    def __post_init__(self) -> None:
        _identity(self.id)
        if not isinstance(self.messages, tuple) or any(not isinstance(item, SessionMessage) for item in self.messages):
            raise ValueError("Invalid operation conversation")


@dataclass(frozen=True)
class SessionOperationState:
    persistence: str
    reference: OperationSessionReference | None = None
    bindings: tuple[OperationBinding, ...] = ()
    observed_ids: tuple[str, ...] = ()
    conversations: tuple[OperationConversation, ...] = ()

    def __post_init__(self) -> None:
        if self.persistence not in {"process", "durable"}:
            raise ValueError("Invalid operation persistence")
        if (self.persistence == "durable") != isinstance(self.reference, OperationSessionReference):
            raise ValueError("Invalid operation reference")
        if not isinstance(self.bindings, tuple) or any(not isinstance(item, OperationBinding) for item in self.bindings):
            raise ValueError("Invalid operation bindings")
        ids = {item.operation_id for item in self.bindings}
        if len(ids) != len(self.bindings):
            raise ValueError("Duplicate operation bindings")
        if not isinstance(self.observed_ids, tuple) or any(not isinstance(item, str) for item in self.observed_ids):
            raise ValueError("Invalid observed operation identities")
        if len(set(self.observed_ids)) != len(self.observed_ids) or not set(self.observed_ids) <= ids:
            raise ValueError("Invalid observed operation history")
        if self.reference is not None and any(
            (item.context.project_hash, item.context.session_id) != (self.reference.project_hash, self.reference.session_id)
            for item in self.bindings
        ):
            raise ValueError("Operation binding scope mismatch")
        if not isinstance(self.conversations, tuple) or any(not isinstance(item, OperationConversation) for item in self.conversations):
            raise ValueError("Invalid operation conversations")
        conversation_ids = {item.id for item in self.conversations}
        if len(conversation_ids) != len(self.conversations) or any(
            item.conversation_id is not None and item.conversation_id not in conversation_ids for item in self.bindings
        ):
            raise ValueError("Invalid operation conversation binding")

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["bindings"] = list(value["bindings"])
        value["observed_ids"] = list(value["observed_ids"])
        value["conversations"] = [{"id": item.id, "messages": [message.to_dict() for message in item.messages]}
                                  for item in self.conversations]
        return value

    @classmethod
    def from_dict(cls, value: Any) -> SessionOperationState:
        if not isinstance(value, dict) or set(value) != {"persistence", "reference", "bindings", "observed_ids", "conversations"}:
            raise ValueError("Invalid operation session state")
        if not isinstance(value["bindings"], list) or not isinstance(value["observed_ids"], list):
            raise ValueError("Invalid operation session state")
        try:
            reference = OperationSessionReference(**value["reference"]) if value["reference"] is not None else None
            bindings = tuple(OperationBinding(item["operation_id"], OperationContext(**item["context"]), item["assistant_index"], item["conversation_id"])
                             for item in value["bindings"] if set(item) == {"operation_id", "context", "assistant_index", "conversation_id"})
            if len(bindings) != len(value["bindings"]):
                raise ValueError("Invalid operation binding fields")
            conversations = tuple(OperationConversation(item["id"], tuple(message_from_dict(message) for message in item["messages"]))
                                  for item in value["conversations"] if set(item) == {"id", "messages"})
            if len(conversations) != len(value["conversations"]):
                raise ValueError("Invalid operation conversation fields")
            return cls(value["persistence"], reference, bindings, tuple(value["observed_ids"]), conversations)
        except (KeyError, TypeError) as exc:
            raise ValueError("Invalid operation session state") from exc
