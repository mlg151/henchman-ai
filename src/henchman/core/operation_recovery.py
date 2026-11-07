"""Correlated operation evidence and conservative interrupted-effect recovery.

One operation ID identifies one dispatch attempt. This journal deliberately does
not retain executable parameters, infer that cancellation undid an effect, or
replay anything. Retry and resolution methods are for trusted user actions, not
model completion or restored session metadata.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
from dataclasses import asdict, dataclass, fields, replace
from typing import Any
from uuid import uuid4

from henchman.utils.evidence_redaction import EvidenceRedactor
from henchman.utils.tool_results import TOOL_RESULT_SCHEMA

_STATES = {"queued", "started", "completed", "cancelled", "outcome_unknown"}
_RESOLUTIONS = {None, "abandoned", "retried", "verified"}
_MAX_EVIDENCE = 65536
OPERATION_OUTPUT_LIMIT = 50000


class OperationRecoveryError(RuntimeError):
    """A recovery/control failure which must stop ordinary automatic dispatch."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


def _identity(value: Any) -> str:
    if not isinstance(value, str) or not value or len(value) > 256 or any(ord(c) < 32 for c in value):
        raise ValueError("Invalid operation identity")
    return value


def _digest(value: Any) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError("Invalid operation digest")
    return value


def _text(value: Any) -> str:
    if not isinstance(value, str) or len(value) > _MAX_EVIDENCE:
        raise ValueError("Invalid or oversized operation evidence")
    return value


@dataclass(frozen=True)
class OperationContext:
    """Structural correlation only; none of these fields contains tool input."""

    project_hash: str
    session_id: str
    run_id: str
    turn_id: str
    agent_id: str
    tool_call_id: str

    def __post_init__(self) -> None:
        for field in fields(self):
            _identity(getattr(self, field.name))


@dataclass(frozen=True)
class OperationResult:
    """A bounded evidence projection, never an input for replay."""

    content: str
    success: bool
    error: str | None = None
    content_truncated: bool = False
    error_truncated: bool = False
    content_sha256: str | None = None
    error_sha256: str | None = None
    content_blocks: tuple[dict[str, object], ...] = ()
    structured_content: object = None
    structured_content_present: bool = False
    metadata: dict[str, object] | None = None
    payload_truncated: bool = False
    payload_sha256: str | None = None

    def __post_init__(self) -> None:
        _text(self.content)
        if type(self.success) is not bool:
            raise ValueError("Invalid operation result")
        if self.error is not None:
            _text(self.error)
        for truncated, digest in ((self.content_truncated, self.content_sha256), (self.error_truncated, self.error_sha256), (self.payload_truncated, self.payload_sha256)):
            if type(truncated) is not bool or truncated != (digest is not None):
                raise ValueError("Invalid operation truncation provenance")
            if digest is not None:
                _digest(digest)
        if not isinstance(self.content_blocks, tuple) or any(not isinstance(item, dict) for item in self.content_blocks):
            raise ValueError("Invalid typed operation content")
        if type(self.structured_content_present) is not bool or (not self.structured_content_present and self.structured_content is not None):
            raise ValueError("Invalid structured content presence")
        if self.metadata is not None and not isinstance(self.metadata, dict):
            raise ValueError("Invalid operation metadata")


def project_operation_result(content: str, success: bool, error: str | None = None, *, redactor: EvidenceRedactor,
                             content_blocks: tuple[dict[str, object], ...] = (), structured_content: object = None,
                             structured_content_present: bool = False, metadata: dict[str, object] | None = None) -> OperationResult:
    """Project complete evidence before truncation; hash the complete projection.

    The bound includes the visible marker so applying this projection to an
    already bounded transcript is idempotent. Digests describe capture-time
    projected evidence, not provider billing, executable inputs, or raw secrets.
    """
    if type(structured_content_present) is not bool or (not structured_content_present and structured_content is not None):
        raise OperationRecoveryError("invalid_structured_content_presence")
    payload = redactor.redact({"content_blocks": list(content_blocks), "structured_content": structured_content,
                              "structured_content_present": structured_content_present, "metadata": metadata}, schema=TOOL_RESULT_SCHEMA)
    try:
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise OperationRecoveryError("invalid_typed_operation_evidence") from exc
    payload_truncated = len(encoded) > _MAX_EVIDENCE
    payload_digest = hashlib.sha256(encoded.encode()).hexdigest() if payload_truncated else None
    if payload_truncated:
        payload = {"content_blocks": [], "structured_content": None, "structured_content_present": False,
                   "metadata": {"operation_evidence": {"payload_truncated": True, "payload_sha256": payload_digest,
                                                        "structured_content_was_present": structured_content_present}}}
        content += "\n\n[... typed tool evidence unavailable: payload exceeded the recovery evidence bound]"

    def bounded(value: str) -> tuple[str, bool, str | None]:
        projected = redactor.text(value)
        if len(projected) <= OPERATION_OUTPUT_LIMIT:
            return projected, False, None
        marker = "\n\n[... operation evidence truncated]"
        return (projected[:OPERATION_OUTPUT_LIMIT - len(marker)] + marker, True,
                hashlib.sha256(projected.encode()).hexdigest())
    text, truncated, digest = bounded(content)
    error_text, error_truncated, error_digest = bounded(error) if error is not None else (None, False, None)
    return OperationResult(text, success, error_text, truncated, error_truncated, digest, error_digest,
                           tuple(payload["content_blocks"]), payload["structured_content"], payload["structured_content_present"],
                           payload["metadata"], payload_truncated, payload_digest)


@dataclass(frozen=True)
class OperationRecord:
    operation_id: str
    context: OperationContext
    tool_name: str
    effect: str
    input_digest: str
    description: str
    state: str = "queued"
    revision: int = 0
    owner_id: str | None = None
    result: OperationResult | None = None
    resolution: str | None = None
    resolution_note: str = ""
    retry_of: str | None = None

    def __post_init__(self) -> None:
        _identity(self.operation_id)
        _identity(self.tool_name)
        _digest(self.input_digest)
        _text(self.description)
        _text(self.resolution_note)
        if not isinstance(self.context, OperationContext) or self.effect not in {"read", "effectful"}:
            raise ValueError("Invalid operation definition")
        if self.state not in _STATES or type(self.revision) is not int or self.revision < 0:
            raise ValueError("Invalid operation state")
        if self.resolution not in _RESOLUTIONS:
            raise ValueError("Invalid operation resolution")
        if self.owner_id is not None:
            _identity(self.owner_id)
        if self.retry_of is not None:
            _identity(self.retry_of)
        if self.state in {"queued", "cancelled"}:
            if self.owner_id is not None or self.result is not None or self.resolution is not None:
                raise ValueError("Unstarted operation cannot have a dispatch outcome")
        elif self.owner_id is None:
            raise ValueError("Dispatched operation must have an owner")
        if (self.state == "completed") != (self.result is not None):
            raise ValueError("Only completed operations have a result")
        if self.result is not None and not isinstance(self.result, OperationResult):
            raise ValueError("Invalid operation result")
        if self.resolution is not None and self.state not in {"outcome_unknown", "completed"}:
            raise ValueError("Only uncertain/completed operations can have a resolution")
        if self.resolution == "verified" and self.state != "completed":
            raise ValueError("Verified completion must have an observed result")
        if (self.resolution is not None) != bool(self.resolution_note.strip()):
            raise ValueError("Resolution requires an evidence note")


@dataclass(frozen=True)
class DispatchPermit:
    """Runtime capability returned once; only its digest enters durable state."""

    operation_id: str
    token: str


@dataclass(frozen=True)
class RetryAuthorization:
    """Single-use explicit user authority, absent from persisted journal state."""

    operation_id: str
    expected_revision: int
    token: str
    project_hash: str
    session_id: str


class RetryAuthority:
    """Runtime-owned token vault shared across a durable handle's transactions."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._tokens: dict[str, tuple[int, RetryAuthorization]] = {}

    def issue(self, operation_id: str, revision: int, *, project_hash: str, session_id: str) -> RetryAuthorization:
        authorization = RetryAuthorization(operation_id, revision, uuid4().hex, project_hash, session_id)
        with self._lock:
            self._tokens[authorization.token] = (os.getpid(), authorization)
        return authorization

    def consume(self, authorization: RetryAuthorization) -> None:
        with self._lock:
            expected = self._tokens.pop(authorization.token, None)
        if expected != (os.getpid(), authorization):
            raise OperationRecoveryError("invalid_retry_authorization")


@dataclass(frozen=True)
class RecoveryReport:
    records: tuple[OperationRecord, ...]
    blocking_operation_ids: tuple[str, ...]


class OperationJournal:
    """Thread-safe process journal; durable adapters use its explicit state codec."""

    def __init__(self, project_hash: str, session_id: str, *, owner_id: str | None = None,
                 redactor: EvidenceRedactor | None = None,
                 retry_authority: RetryAuthority | None = None) -> None:
        self.project_hash = _identity(project_hash)
        self.session_id = _identity(session_id)
        self._owner_id = _identity(owner_id) if owner_id is not None else uuid4().hex
        self._redactor = redactor if redactor is not None else EvidenceRedactor()
        self._authority = retry_authority if retry_authority is not None else RetryAuthority()
        self._records: dict[str, OperationRecord] = {}
        self._claims: dict[str, str] = {}
        self._lock = threading.RLock()

    @property
    def owner_id(self) -> str:
        return f"{os.getpid()}:{self._owner_id}"

    def _project(self, record: OperationRecord) -> OperationRecord:
        result = record.result
        if result is not None:
            projected = project_operation_result(result.content, result.success, result.error, redactor=self._redactor,
                                                 content_blocks=result.content_blocks, structured_content=result.structured_content,
                                                 structured_content_present=result.structured_content_present, metadata=result.metadata)
            result = replace(projected, content_truncated=result.content_truncated or projected.content_truncated,
                             error_truncated=result.error_truncated or projected.error_truncated,
                             content_sha256=projected.content_sha256 or result.content_sha256,
                             error_sha256=projected.error_sha256 or result.error_sha256,
                             payload_truncated=result.payload_truncated or projected.payload_truncated,
                             payload_sha256=projected.payload_sha256 or result.payload_sha256)
        return replace(record, description=self._redactor.text(record.description), result=result,
                       resolution_note=self._redactor.text(record.resolution_note))

    def _get(self, operation_id: str) -> OperationRecord:
        try:
            return self._project(self._records[operation_id])
        except KeyError as exc:
            raise OperationRecoveryError("missing_operation") from exc

    def _write(self, record: OperationRecord) -> OperationRecord:
        record = self._project(record)
        self._records[record.operation_id] = record
        return record

    def queue(self, context: OperationContext, *, tool_name: str, effect: str,
              input_digest: str, description: str = "", operation_id: str | None = None) -> OperationRecord:
        """Record intent without retaining executable arguments or authorizing it."""
        if (context.project_hash, context.session_id) != (self.project_hash, self.session_id):
            raise OperationRecoveryError("session_mismatch")
        record = self._project(OperationRecord(operation_id if operation_id is not None else uuid4().hex, context, tool_name,
                                               effect, input_digest, description))
        with self._lock:
            existing = self._records.get(record.operation_id)
            if existing is not None:
                previous = self._project(existing)
                definition = ("context", "tool_name", "effect", "input_digest", "description")
                if any(getattr(previous, key) != getattr(record, key) for key in definition):
                    raise OperationRecoveryError("conflicting_operation")
                return previous
            return self._write(record)

    def _blocked(self, record: OperationRecord) -> bool:
        return record.effect == "effectful" and record.resolution is None and (
            record.state == "outcome_unknown"
            or (record.state == "started" and record.owner_id != self.owner_id)
        )

    def start(self, operation_id: str) -> DispatchPermit | None:
        """Grant one dispatch, or None for an attempt already started/cancelled."""
        with self._lock:
            record = self._get(operation_id)
            if record.state != "queued":
                return None
            if record.effect == "effectful" and any(self._blocked(item) for item in self._records.values()):
                raise OperationRecoveryError("unresolved_operation")
            token = uuid4().hex
            self._claims[operation_id] = hashlib.sha256(token.encode()).hexdigest()
            self._write(replace(record, state="started", owner_id=self.owner_id, revision=record.revision + 1))
            return DispatchPermit(operation_id, token)

    def finish(self, permit: DispatchPermit, result: OperationResult) -> OperationRecord:
        """Reconcile a correlated observed result, including a late completion."""
        with self._lock:
            record = self._get(permit.operation_id)
            if self._claims.get(permit.operation_id) != hashlib.sha256(permit.token.encode()).hexdigest():
                raise OperationRecoveryError("invalid_permit")
            projected = self._project(replace(record, state="completed", result=result))
            if record.state == "completed":
                if record.result != projected.result:
                    raise OperationRecoveryError("conflicting_result")
                return record
            if record.state not in {"started", "outcome_unknown"}:
                raise OperationRecoveryError("invalid_completion")
            return self._write(replace(projected, revision=record.revision + 1))

    def cancel(self, operation_id: str) -> OperationRecord:
        with self._lock:
            record = self._get(operation_id)
            if record.state not in {"queued", "started"}:
                return record
            state = "cancelled" if record.state == "queued" else "outcome_unknown"
            return self._write(replace(record, state=state, revision=record.revision + 1))

    def report(self) -> RecoveryReport:
        with self._lock:
            return RecoveryReport(tuple(self._project(item) for item in self._records.values()),
                                  tuple(item.operation_id for item in self._records.values() if self._blocked(item)))

    def recover(self) -> RecoveryReport:
        """Foreign starts become unknown; this makes no claim their process stopped."""
        with self._lock:
            for record in tuple(self._records.values()):
                if record.state == "started" and record.owner_id != self.owner_id:
                    self._write(replace(record, state="outcome_unknown", revision=record.revision + 1))
            return self.report()

    def _unresolved(self, operation_id: str, expected_revision: int) -> OperationRecord:
        record = self._get(operation_id)
        if type(expected_revision) is not int or record.revision != expected_revision:
            raise OperationRecoveryError("stale_revision")
        if record.state != "outcome_unknown" or record.resolution is not None:
            raise OperationRecoveryError("operation_not_unresolved")
        return record

    def resolve(self, operation_id: str, *, expected_revision: int, decision: str,
                note: str, result: OperationResult | None = None) -> OperationRecord:
        """Apply a trusted user's observed completion or acknowledgement of ambiguity."""
        _text(note)
        if not note.strip() or decision not in {"abandon", "completed"}:
            raise ValueError("Resolution requires a decision and evidence note")
        if (decision == "completed") != (result is not None):
            raise ValueError("Verified completion requires a result")
        with self._lock:
            record = self._unresolved(operation_id, expected_revision)
            return self._write(replace(record, revision=record.revision + 1,
                                       state="completed" if result is not None else "outcome_unknown",
                                       result=result, resolution="verified" if result is not None else "abandoned",
                                       resolution_note=note))

    def authorize_retry(self, operation_id: str, *, expected_revision: int) -> RetryAuthorization:
        """Capture explicit user intent in memory; this is not a model-facing method."""
        with self._lock:
            record = self._unresolved(operation_id, expected_revision)
            return self._authority.issue(operation_id, record.revision,
                                         project_hash=self.project_hash, session_id=self.session_id)

    def retry(self, authorization: RetryAuthorization, *, operation_id: str | None = None,
              note: str) -> OperationRecord:
        """Consume one runtime authority to queue a new attempt, preserving history."""
        self._authority.consume(authorization)
        if (authorization.project_hash, authorization.session_id) != (self.project_hash, self.session_id):
            raise OperationRecoveryError("retry_session_mismatch")
        _text(note)
        if not note.strip():
            raise ValueError("Retry requires an explicit user evidence note")
        with self._lock:
            record = self._unresolved(authorization.operation_id, authorization.expected_revision)
            next_id = _identity(operation_id) if operation_id is not None else uuid4().hex
            if next_id in self._records:
                raise OperationRecoveryError("conflicting_operation")
            queued = OperationRecord(next_id, record.context, record.tool_name, record.effect,
                                     record.input_digest, record.description, retry_of=record.operation_id)
            self._write(replace(record, resolution="retried", resolution_note=note, revision=record.revision + 1))
            return self._write(queued)

    def export_state(self) -> dict[str, Any]:
        """Versioned source state, excluding executable inputs and runtime authorities."""
        with self._lock:
            return {"version": 1, "project_hash": self.project_hash, "session_id": self.session_id,
                    "operations": [{"record": asdict(self._project(record)),
                                    "claim_hash": self._claims.get(record.operation_id)}
                                   for record in self._records.values()]}

    @classmethod
    def from_state(cls, state: dict[str, Any], *, owner_id: str | None = None,
                   redactor: EvidenceRedactor | None = None,
                   retry_authority: RetryAuthority | None = None) -> OperationJournal:
        """Strictly restore state; callers validate its external integrity/identity too."""
        try:
            if set(state) != {"version", "project_hash", "session_id", "operations"}:
                raise ValueError("Unexpected state fields")
            if type(state["version"]) is not int or state["version"] != 1 or not isinstance(state["operations"], list):
                raise ValueError("Unsupported state version")
            journal = cls(state["project_hash"], state["session_id"], owner_id=owner_id,
                          redactor=redactor, retry_authority=retry_authority)
            for entry in state["operations"]:
                if set(entry) != {"record", "claim_hash"}:
                    raise ValueError("Unexpected operation fields")
                raw = dict(entry["record"])
                if set(raw) != {field.name for field in fields(OperationRecord)}:
                    raise ValueError("Incomplete operation state")
                raw["context"] = OperationContext(**raw["context"])
                if raw["result"] is not None:
                    if "content_blocks" in raw["result"]:
                        raw["result"]["content_blocks"] = tuple(raw["result"]["content_blocks"])
                    raw["result"] = OperationResult(**raw["result"])
                record = OperationRecord(**raw)
                if (record.context.project_hash, record.context.session_id) != (journal.project_hash, journal.session_id):
                    raise ValueError("State session mismatch")
                if record.operation_id in journal._records:
                    raise ValueError("Duplicate operation")
                claim = entry["claim_hash"]
                if (claim is not None) != (record.owner_id is not None):
                    raise ValueError("Invalid dispatch claim")
                if claim is not None:
                    journal._claims[record.operation_id] = _digest(claim)
                journal._write(record)
            seen: set[str] = set()
            retried: set[str] = set()
            for record in journal._records.values():
                if record.retry_of is not None:
                    previous = journal._records.get(record.retry_of)
                    definition = ("context", "tool_name", "effect", "input_digest", "description")
                    if (previous is None or previous.resolution != "retried"
                            or record.retry_of not in seen or record.retry_of in retried
                            or any(getattr(previous, key) != getattr(record, key) for key in definition)):
                        raise ValueError("Invalid retry lineage")
                    retried.add(record.retry_of)
                seen.add(record.operation_id)
            if retried != {item.operation_id for item in journal._records.values() if item.resolution == "retried"}:
                raise ValueError("Missing retry attempt")
            return journal
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise OperationRecoveryError("invalid_state") from exc
