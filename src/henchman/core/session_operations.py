"""Bind durable tool effects to saved assistant requests and observed results."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from copy import deepcopy
from dataclasses import asdict, dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

from henchman.config.schema import Settings
from henchman.core.operation_bindings import (
    OperationBinding,
    OperationConversation,
    SessionOperationState,
)
from henchman.core.operation_recovery import (
    OperationContext,
    OperationJournal,
    OperationRecord,
    OperationRecoveryError,
    RecoveryReport,
    project_operation_result,
)
from henchman.core.runtime_operations import OperationInvocation, tool_result_from_operation
from henchman.core.runtime_workflow import correlate_workflow
from henchman.core.session_data import Session
from henchman.core.session_models import SessionMessage
from henchman.ops.operation_store import OperationStore, PersistentOperationJournal
from henchman.providers.base import Message, ToolCall
from henchman.utils.tool_results import tool_result_from_payload, tool_result_payload

if TYPE_CHECKING:
    from henchman.core.agent import Agent

Journal = OperationJournal | PersistentOperationJournal


def input_digest(params: dict[str, object]) -> str:
    try:
        encoded = json.dumps(params, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise OperationRecoveryError("unserializable_operation_input") from exc
    return hashlib.sha256(encoded.encode()).hexdigest()


@dataclass
class OperationRun:
    runtime: SessionRunOperations
    session: Session
    journal: Journal
    run_id: str
    primary_agent: Agent | None = None
    session_start: int = 0
    _sources: list[tuple[Agent, list[Message], str | None]] = field(default_factory=list, repr=False)
    _primary_offsets: dict[int, int] = field(default_factory=dict, repr=False)

    def bind_call(self, call: ToolCall, *, agent_id: str, assistant_index: int,
                  conversation_id: str | None = None) -> OperationInvocation:
        state = self.session.operations
        assert state is not None
        for binding in state.bindings:
            if (binding.conversation_id, binding.assistant_index, binding.context.agent_id, binding.context.tool_call_id) == (conversation_id, assistant_index, agent_id, call.id):
                return OperationInvocation(self, binding)
        context = OperationContext(self.session.project_hash, self.session.id, self.run_id, uuid4().hex, agent_id, call.id)
        return OperationInvocation(self, OperationBinding(uuid4().hex, context, assistant_index, conversation_id))

    def capture_agent(self, agent: Agent) -> tuple[list[SessionMessage], int, str | None]:
        actor = agent.identity.id if agent.identity is not None else "tech_lead"
        source = agent.current_turn_messages
        for known_agent, known_source, conversation_id in self._sources:
            if known_agent is agent and known_source is source:
                return self._capture_source(agent, source, conversation_id)
        conversation_id = None if agent is self.primary_agent else f"{self.run_id}:{actor}:{uuid4().hex}"
        if agent is self.primary_agent:
            self._primary_offsets[id(source)] = self.session_start + sum(
                len(known_source) for known_agent, known_source, _ in self._sources
                if known_agent is self.primary_agent
            )
        # Retain the list itself: a reused specialist replaces its current turn
        # list, but late tool responses still belong to the earlier turn.
        self._sources.append((agent, source, conversation_id))
        return self._capture_source(agent, source, conversation_id)

    def _capture_source(self, agent: Agent, source: list[Message], conversation_id: str | None) -> tuple[list[SessionMessage], int, str | None]:
        messages = [SessionMessage(**deepcopy(asdict(message))) for message in source]
        if agent is self.primary_agent:
            transcript: list[SessionMessage] = []
            for known_agent, known_source, _ in self._sources:
                if known_agent is not self.primary_agent:
                    continue
                if self._primary_offsets[id(known_source)] != self.session_start + len(transcript):
                    raise OperationRecoveryError("primary_turn_history_changed")
                transcript.extend(SessionMessage(**deepcopy(asdict(item))) for item in known_source)
            self.session.messages[self.session_start:] = transcript
            return messages, self._primary_offsets[id(source)], None
        assert conversation_id is not None
        state = self.session.operations
        assert state is not None
        others = tuple(item for item in state.conversations if item.id != conversation_id)
        self.session.operations = replace(state, conversations=(*others, OperationConversation(conversation_id, tuple(messages))))
        return messages, 0, conversation_id

    def capture_call(self, agent: Agent, call: ToolCall) -> OperationInvocation:
        messages, offset, conversation_id = self.capture_agent(agent)
        matches = [index for index, message in enumerate(messages) if message.role == "assistant"
                   and any(item.get("id") == call.id and item.get("name") == call.name for item in message.tool_calls or [])]
        if not matches:
            raise OperationRecoveryError("missing_assistant_correlation")
        message = messages[matches[-1]]
        message.tool_calls = [asdict(call) if item.get("id") == call.id else item for item in message.tool_calls or []]
        actor = agent.identity.id if agent.identity is not None else "tech_lead"
        return self.bind_call(call, agent_id=actor, assistant_index=offset + matches[-1], conversation_id=conversation_id)


class SessionRunOperations:
    """Session JSON is advisory; a journal record missing from a backup blocks it.

    Process journals have no restart guarantee. Durable journals are discovered
    independently of restored references/settings so a backup or policy downgrade
    cannot replace known effects with a fresh authority.
    """

    def __init__(self, settings: Settings, current: Callable[[], Session | None],
                 save: Callable[[Session], None], path: Path | None) -> None:
        self.settings = settings
        self.current = current
        self.save = save
        self.path = path
        self._active: dict[tuple[str, str], tuple[Session, Journal]] = {}
        self._fallback_session: Session | None = None
        self._inflight: dict[str, OperationInvocation] = {}

    @classmethod
    def for_process(cls, settings: Settings) -> SessionRunOperations:
        """Standalone runtime authority with no implicit database or session writes."""
        if settings.operations.persistence == "durable":
            raise OperationRecoveryError("durable_operation_session_required")
        now = datetime.now(UTC).isoformat()
        session = Session(uuid4().hex, "process", now, now)
        return cls(settings, lambda: session, lambda _session: None, None)

    def _session(self) -> Session:
        session = self.current()
        if session is None:
            if self.settings.operations.persistence == "durable":
                raise OperationRecoveryError("operation_session_required")
            if self._fallback_session is None:
                now = datetime.now(UTC).isoformat()
                self._fallback_session = Session(uuid4().hex, "process", now, now)
            return self._fallback_session
        return session

    def _save(self, session: Session) -> None:
        if session is self._fallback_session:
            return
        try:
            self.save(session)
        except Exception as exc:
            raise OperationRecoveryError("session_save_failed") from exc

    def _journal(self, session: Session) -> Journal:
        key = (session.project_hash, session.id)
        state = session.operations
        reference = state.reference if state is not None else None
        existing = OperationStore.existing_reference(self.path, *key) if self.path is not None and session is not self._fallback_session else None
        if reference is not None:
            if (reference.project_hash, reference.session_id) != key:
                raise OperationRecoveryError("session_mismatch")
            if existing != reference:
                raise OperationRecoveryError("missing_or_changed_operation_store")
        previous = self._active.get(key)
        if previous is not None:
            old_session, journal = previous
            if isinstance(journal, PersistentOperationJournal):
                if existing != journal.reference:
                    raise OperationRecoveryError("missing_or_changed_operation_store")
            elif existing is not None:
                raise OperationRecoveryError("conflicting_operation_authority")
            if old_session is not session:
                # A restored object cannot claim that a prior runtime's task is
                # still locally controlled, even when its PID has not changed.
                for record in journal.report().records:
                    if record.state == "started":
                        journal.cancel(record.operation_id)
            self._active[key] = (session, journal)
            return journal
        if existing is not None or self.settings.operations.persistence == "durable":
            if self.path is None:
                raise OperationRecoveryError("durable_operation_session_required")
            store = OperationStore(self.path, expected_store_id=existing.store_id if existing else None,
                                   redactor=session.evidence_redactor)
            journal = store.open_session(*key, create=existing is None)
            journal.recover()
        else:
            if state is not None and set(state.observed_ids) != {item.operation_id for item in state.bindings}:
                raise OperationRecoveryError("process_operation_history_unavailable")
            journal = OperationJournal(*key, redactor=session.evidence_redactor)
            # Completed process history is not durable replay authority.
            session.operations = None
        self._active[key] = (session, journal)
        return journal

    @staticmethod
    def _state(journal: Journal) -> SessionOperationState:
        return SessionOperationState("durable", journal.reference) if isinstance(journal, PersistentOperationJournal) else SessionOperationState("process")

    def begin(self, *, agent: Agent | None = None, user_input: str | None = None) -> OperationRun:
        session = self._session()
        journal = self._journal(session)
        self._reconcile(session, journal)
        start = len(session.messages)
        if session.messages and user_input is not None and session.messages[-1].role == "user" and session.messages[-1].content == user_input:
            start -= 1
        return OperationRun(self, session, journal, uuid4().hex, agent, start)

    def finish(self, run: OperationRun, *, failed: bool) -> None:
        if failed:
            for invocation in tuple(self._inflight.values()):
                if invocation.run is run:
                    invocation.cancel()
        for agent, source, conversation_id in run._sources:
            run._capture_source(agent, source, conversation_id)
        if failed:
            self._save(run.session)
        else:
            self._reconcile(run.session, run.journal)

    def report(self) -> RecoveryReport:
        session = self._session()
        return self._journal(session).report()

    @property
    def current_session(self) -> Session | None:
        return self.current() or self._fallback_session

    def recovery_report(self) -> RecoveryReport | None:
        """Classify existing attempts without creating storage or an empty journal."""
        session = self.current_session
        if session is None:
            return None
        key = (session.project_hash, session.id)
        existing = OperationStore.existing_reference(self.path, *key) if self.path is not None else None
        reference = session.operations.reference if session.operations is not None else None
        if reference is not None and existing != reference:
            raise OperationRecoveryError("missing_or_changed_operation_store")
        cached = self._active.get(key)
        if cached is not None:
            journal = cached[1]
            if isinstance(journal, PersistentOperationJournal) and journal.reference != existing:
                raise OperationRecoveryError("missing_or_changed_operation_store")
            if isinstance(journal, OperationJournal) and existing is not None:
                raise OperationRecoveryError("conflicting_operation_authority")
        elif existing is not None:
            assert self.path is not None
            journal = OperationStore(self.path, expected_store_id=existing.store_id,
                                     redactor=session.evidence_redactor).resume_session(existing)
            self._active[key] = (session, journal)
        else:
            return None
        for record in journal.report().records:
            if record.state == "started" and record.operation_id not in self._inflight:
                journal.cancel(record.operation_id)
        return journal.recover()

    def _user_target(self, operation_id: str, revision: int) -> tuple[Session, Journal, OperationRecord, OperationBinding]:
        session = self._session()
        journal = self._journal(session)
        record = next((item for item in journal.report().records if item.operation_id == operation_id), None)
        if record is None:
            raise OperationRecoveryError("missing_operation")
        if type(revision) is not int or record.revision != revision:
            raise OperationRecoveryError("stale_revision")
        bindings = session.operations.bindings if session.operations is not None else ()
        binding = next((item for item in bindings if item.operation_id == operation_id), None)
        if binding is None or binding.context != record.context:
            raise OperationRecoveryError("saved_request_unavailable_restore_transcript_or_start_new_session")
        self._assistant(session, binding, record.tool_name)
        return session, journal, record, binding

    @staticmethod
    def _content(record: OperationRecord) -> str:
        if record.result is not None:
            return record.result.content
        if record.resolution == "abandoned":
            return f"Operation outcome remains unknown; the user abandoned further recovery. {record.resolution_note}"
        return "Operation was interrupted before dispatch; no effect was started."

    @staticmethod
    def _set_messages(session: Session, binding: OperationBinding, messages: list[SessionMessage]) -> None:
        if binding.conversation_id is None:
            session.messages = messages
        else:
            state = session.operations
            assert state is not None
            session.operations = replace(state, conversations=tuple(
                OperationConversation(item.id, tuple(messages)) if item.id == binding.conversation_id else item
                for item in state.conversations))

    def _response_positions(self, session: Session, binding: OperationBinding) -> tuple[list[SessionMessage], list[int]]:
        messages = self._messages(session, binding)
        tail = messages[binding.assistant_index + 1:]
        end = next((index for index, item in enumerate(tail) if item.role != "tool"), len(tail))
        positions = [binding.assistant_index + 1 + index for index, item in enumerate(tail[:end])
                     if item.tool_call_id == binding.context.tool_call_id]
        if len(positions) > 1:
            raise OperationRecoveryError("ambiguous_result_correlation")
        return messages, positions

    def resolve_user(self, operation_id: str, revision: int, *, decision: str, note: str) -> OperationRecord:
        """Explicit revision-checked user resolution; never called by model tools."""
        session, journal, record, binding = self._user_target(operation_id, revision)
        messages, positions = self._response_positions(session, binding)
        if not positions and any(item.role != "tool" for item in messages[binding.assistant_index + 1:]):
            raise OperationRecoveryError("historical_request_requires_manual_transcript_recovery")
        old_state, old_messages = session.operations, deepcopy(session.messages)
        if not (decision == "completed" and record.state == "completed") and not (
            decision == "abandon" and record.resolution == "abandoned"
        ):
            result = project_operation_result(f"User verified completion: {note}", True, redactor=session.evidence_redactor) if decision == "completed" else None
            record = journal.resolve(operation_id, expected_revision=revision, decision=decision, note=note, result=result)
        try:
            messages = list(messages)
            response = SessionMessage("tool", content=self._content(record), tool_call_id=record.context.tool_call_id,
                                      tool_result=tool_result_payload(tool_result_from_operation(record.result)) if record.result is not None else None)
            if positions:
                messages[positions[0]] = response
            else:
                messages.append(response)
            self._set_messages(session, binding, messages)
            self._reconcile(session, journal)
            self._save(session)
        except BaseException:
            session.operations, session.messages = old_state, old_messages
            raise
        return record

    def retry_request(self, operation_id: str, revision: int) -> ToolCall:
        """Read an intact saved request; redacted/changed parameters cannot replay."""
        session, _journal, record, binding = self._user_target(operation_id, revision)
        if record.state != "outcome_unknown" or record.resolution is not None:
            raise OperationRecoveryError("operation_not_unresolved")
        message = self._assistant(session, binding, record.tool_name)
        call = next(item for item in message.tool_calls or [] if item.get("id") == record.context.tool_call_id)
        params = deepcopy(call.get("arguments"))
        if not isinstance(params, dict) or input_digest(params) != record.input_digest:
            raise OperationRecoveryError("saved_retry_input_unavailable")
        messages = self._messages(session, binding)
        if any(item.role != "tool" for item in messages[binding.assistant_index + 1:]):
            raise OperationRecoveryError("historical_request_requires_manual_transcript_recovery")
        return ToolCall(record.context.tool_call_id, record.tool_name, params)

    def authorize_user_retry(self, operation_id: str, revision: int, call: ToolCall) -> OperationInvocation:
        """Consume runtime-only authority after current registry authorization."""
        session, journal, record, binding = self._user_target(operation_id, revision)
        if call.name != record.tool_name or call.id != record.context.tool_call_id or input_digest(call.arguments) != record.input_digest:
            raise OperationRecoveryError("saved_retry_input_unavailable")
        token = journal.authorize_retry(operation_id, expected_revision=revision)
        next_record = journal.retry(token, note="Explicit user retry under current tool policy")
        old_state, old_messages = session.operations, deepcopy(session.messages)
        assert old_state is not None
        new_binding = replace(binding, operation_id=next_record.operation_id)
        try:
            messages, positions = self._response_positions(session, binding)
            messages = deepcopy([item for index, item in enumerate(messages) if index not in positions])
            assistant = messages[binding.assistant_index]
            assistant.tool_calls = [asdict(call) if item.get("id") == call.id else item
                                    for item in assistant.tool_calls or []]
            self._set_messages(session, binding, messages)
            state = session.operations
            assert state is not None
            session.operations = replace(state, bindings=(*state.bindings, new_binding))
            self._save(session)
        except BaseException:
            session.operations, session.messages = old_state, old_messages
            raise
        return OperationInvocation(OperationRun(self, session, journal, record.context.run_id), new_binding)

    def finish_user_retry(self, invocation: OperationInvocation) -> None:
        journal = invocation.run.journal
        record = next(item for item in journal.report().records if item.operation_id == invocation.binding.operation_id)
        if record.state == "queued":
            journal.cancel(record.operation_id)
        self._reconcile(invocation.run.session, journal)

    @staticmethod
    def _messages(session: Session, binding: OperationBinding) -> list[SessionMessage]:
        if binding.conversation_id is None:
            return session.messages
        state = session.operations
        if state is not None:
            for conversation in state.conversations:
                if conversation.id == binding.conversation_id:
                    return list(conversation.messages)
        raise OperationRecoveryError("missing_operation_conversation")

    @classmethod
    def _assistant(cls, session: Session, binding: OperationBinding, tool_name: str) -> SessionMessage:
        messages = cls._messages(session, binding)
        if binding.assistant_index >= len(messages):
            raise OperationRecoveryError("missing_assistant_correlation")
        message = messages[binding.assistant_index]
        calls = message.tool_calls or []
        matches = [call for call in calls if call.get("id") == binding.context.tool_call_id and call.get("name") == tool_name]
        if message.role != "assistant" or len(matches) != 1:
            raise OperationRecoveryError("ambiguous_assistant_correlation")
        return message

    def _reconcile(self, session: Session, journal: Journal) -> None:
        report = journal.report()
        state = session.operations or self._state(journal)
        records = {record.operation_id: record for record in report.records}
        bindings = {binding.operation_id: binding for binding in state.bindings}
        if set(records) != set(bindings):
            raise OperationRecoveryError("transcript_behind_journal" if set(records) - set(bindings) else "missing_operation_history")
        for operation_id in state.observed_ids:
            record = records[operation_id]
            if record.state not in {"completed", "cancelled"} and record.resolution is None:
                raise OperationRecoveryError("unresolved_operation")
        if report.blocking_operation_ids:
            raise OperationRecoveryError("unresolved_operation")
        old_state, old_messages = session.operations, deepcopy(session.messages)
        try:
            observed = list(state.observed_ids)
            conversations = {item.id: deepcopy(list(item.messages)) for item in state.conversations}
            for operation_id, record in records.items():
                binding = bindings[operation_id]
                if binding.context != record.context:
                    raise OperationRecoveryError("operation_context_mismatch")
                self._assistant(session, binding, record.tool_name)
                if record.state == "started":
                    if operation_id in self._inflight:
                        continue
                    record = journal.cancel(operation_id)
                if record.state == "outcome_unknown" and record.resolution == "retried":
                    if operation_id not in observed:
                        observed.append(operation_id)
                    continue
                if record.state == "queued":
                    record = journal.cancel(operation_id)
                if record.state not in {"completed", "cancelled"} and record.resolution != "abandoned":
                    raise OperationRecoveryError("unresolved_operation")
                content = self._content(record)
                expected_payload = tool_result_payload(tool_result_from_operation(record.result)) if record.result is not None else None
                messages = session.messages if binding.conversation_id is None else conversations[binding.conversation_id]
                tail = messages[binding.assistant_index + 1:]
                end = next((index for index, message in enumerate(tail) if message.role != "tool"), len(tail))
                responses = [message for message in tail[:end] if message.tool_call_id == record.context.tool_call_id]
                if len(responses) > 1:
                    raise OperationRecoveryError("ambiguous_result_correlation")
                if not responses:
                    if operation_id in observed:
                        raise OperationRecoveryError("missing_observed_result")
                    if any(message.role != "tool" for message in tail):
                        raise OperationRecoveryError("ambiguous_result_correlation")
                    messages.append(SessionMessage("tool", content=content, tool_call_id=record.context.tool_call_id,
                                                   tool_result=expected_payload))
                else:
                    try:
                        saved = tool_result_from_payload(responses[0].content or "", responses[0].tool_result)
                        projected = project_operation_result(saved.content, saved.success, saved.error, redactor=session.evidence_redactor,
                                                             content_blocks=saved.content_blocks, structured_content=saved.structured_content,
                                                             structured_content_present=saved.structured_content_present, metadata=saved.metadata)
                    except ValueError as exc:
                        raise OperationRecoveryError("conflicting_saved_result_payload") from exc
                    if (projected.content != content or (projected.content_truncated and record.result is not None
                                                        and projected.content_sha256 != record.result.content_sha256)):
                        raise OperationRecoveryError("conflicting_saved_result")
                    actual_payload = tool_result_payload(tool_result_from_operation(projected))
                    if actual_payload != expected_payload:
                        if responses[0].tool_result is None and operation_id not in observed:
                            responses[0].tool_result = deepcopy(expected_payload)
                        else:
                            raise OperationRecoveryError("conflicting_saved_result_payload")
                    if record.result is not None and (
                        (projected.error_truncated and projected.error_sha256 != record.result.error_sha256)
                        or (projected.payload_truncated and projected.payload_sha256 != record.result.payload_sha256)
                    ):
                        raise OperationRecoveryError("conflicting_saved_result_payload")
                if operation_id not in observed:
                    observed.append(operation_id)
            session.operations = replace(state, observed_ids=tuple(observed), conversations=tuple(
                OperationConversation(key, tuple(messages)) for key, messages in conversations.items()))
            if session.operations != old_state or session.messages != old_messages:
                self._save(session)
        except BaseException:
            session.operations, session.messages = old_state, old_messages
            raise

    def prepare(self, invocation: OperationInvocation, name: str, params: dict[str, object], effect: str) -> OperationRecord:
        run, binding = invocation.run, invocation.binding
        session = run.session
        self._assistant(session, binding, name)
        record = run.journal.queue(binding.context, tool_name=name, effect=effect,
                                   input_digest=input_digest(params), operation_id=binding.operation_id)
        state = session.operations
        assert state is not None
        if not any(item.operation_id == binding.operation_id for item in state.bindings):
            session.operations = replace(state, bindings=(*state.bindings, binding))
            try:
                self._save(session)
            except BaseException:
                session.operations = state
                raise
        correlate_workflow(session, operation_run_id=run.run_id, operation_id=record.operation_id)
        return record
