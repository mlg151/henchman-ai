"""Inactive v1 headless wire codec; no runtime, I/O or credential authority.

Callers must project outbound evidence before encoding. Requests retain exact
execution input and deliberately exclude parameters from their representation.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Literal, cast

MAX_FRAME_BYTES = 1024 * 1024
MAX_CHUNK_BYTES = 64 * 1024
MAX_NESTING = 16
MAX_SAFE_INTEGER = (1 << 53) - 1
MAX_PROMPT_BYTES = 256 * 1024
MAX_ANSWER_BYTES = 64 * 1024

RequestMethod = Literal[
    "initialize", "run", "cancel", "permission.respond", "question.respond", "shutdown",
]
FrameKind = Literal["response", "event", "result", "error"]
_METHODS = {"initialize", "run", "cancel", "permission.respond", "question.respond", "shutdown"}
_KINDS = {"response", "event", "result", "error"}
RESULT_STATUSES = frozenset({"completed", "failed", "cancelled", "incomplete", "rejected"})
_RUNTIME_STATUSES = frozenset({"completed", "responded", "no_work_done", "stalled", "timed_out", "failed"})
_ERROR_CODES = frozenset({
    "invalid_request", "unsupported_version", "invalid_json", "nesting_limit", "frame_limit",
    "chunk_limit", "unterminated_frame", "decoder_closed", "invalid_envelope", "sequence_exhausted",
    "already_initialized", "not_initialized", "connection_mismatch", "session_mismatch",
    "request_replayed", "run_already_reserved", "run_not_reserved", "already_admitted",
    "run_mismatch", "run_finished", "stale_decision", "decision_pending", "input_unavailable",
    "cancellation_requested", "connection_closing", "result_already_claimed",
    "result_requires_admission", "invalid_result", "invalid_identity",
})
_IDENTITY = re.compile(r"[A-Za-z0-9_.:@/-]{1,128}\Z")


class ProtocolError(ValueError):
    """A stable, value-free error code, safe even for malformed secret input."""

    def __init__(self, code: str) -> None:
        self.code = code if isinstance(code, str) and code in _ERROR_CODES else "invalid_request"
        super().__init__(self.code)


def exact_integer(value: object, *, code: str = "invalid_request") -> int:
    """Require an integer representable exactly by JSON/Lua number consumers."""
    if type(value) is not int or not 1 <= value <= MAX_SAFE_INTEGER:
        raise ProtocolError(code)
    return value


def identity(value: object, *, code: str = "invalid_identity") -> str:
    """Validate an existing opaque identity; never create one."""
    if not isinstance(value, str) or _IDENTITY.fullmatch(value) is None:
        raise ProtocolError(code)
    return value


def _text(value: object, limit: int, *, nonblank: bool = False) -> None:
    if not isinstance(value, str) or (nonblank and not value.strip()):
        raise ProtocolError("invalid_request")
    if len(value.encode("utf-8")) > limit:
        raise ProtocolError("frame_limit")


def _fields(value: object, names: set[str]) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != names:
        raise ProtocolError("invalid_request")
    return value


def _params(method: RequestMethod, value: dict[str, object]) -> None:
    if method == "initialize":
        data = _fields(value, {"session", "interactive"})
        selection = data["session"]
        if not isinstance(selection, dict):
            raise ProtocolError("invalid_request")
        if selection.get("mode") == "new":
            _fields(selection, {"mode"})
        elif selection.get("mode") == "resume":
            identity(_fields(selection, {"mode", "id"})["id"], code="invalid_request")
        else:
            raise ProtocolError("invalid_request")
        capabilities = _fields(data["interactive"], {"permissions", "questions"})
        if any(type(item) is not bool for item in capabilities.values()):
            raise ProtocolError("invalid_request")
    elif method == "run":
        data = _fields(value, {"session_id", "prompt", "agent"})
        identity(data["session_id"], code="invalid_request")
        _text(data["prompt"], MAX_PROMPT_BYTES, nonblank=True)
        if data["agent"] is not None:
            identity(data["agent"], code="invalid_request")
    elif method == "cancel":
        data = _fields(value, {"run_request_id", "run_id"})
        exact_integer(data["run_request_id"])
        if data["run_id"] is not None:
            identity(data["run_id"], code="invalid_request")
    elif method in {"permission.respond", "question.respond"}:
        answer_key = "approved" if method == "permission.respond" else "answer"
        data = _fields(value, {"session_id", "run_id", "decision_id", "generation", answer_key})
        for key in ("session_id", "run_id", "decision_id"):
            identity(data[key], code="invalid_request")
        exact_integer(data["generation"])
        if answer_key == "approved":
            if type(data[answer_key]) is not bool:
                raise ProtocolError("invalid_request")
        elif data[answer_key] is not None:
            _text(data[answer_key], MAX_ANSWER_BYTES)
    else:
        _fields(value, set())


def _freeze(value: object) -> object:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(child) for key, child in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(child) for child in value)
    return value


@dataclass(frozen=True)
class Request:
    """Validated immutable client input; parameters are not display evidence."""

    id: int
    method: RequestMethod
    connection_id: str | None
    params: Mapping[str, object] = field(repr=False)

    def __post_init__(self) -> None:
        exact_integer(self.id)
        if not isinstance(self.method, str) or self.method not in _METHODS:
            raise ProtocolError("invalid_request")
        if self.method == "initialize":
            if self.connection_id is not None:
                raise ProtocolError("invalid_request")
        elif not (self.method == "shutdown" and self.connection_id is None):
            identity(self.connection_id, code="invalid_request")
        if not isinstance(self.params, Mapping):
            raise ProtocolError("invalid_request")
        data = dict(self.params)
        _json_value(data)
        _params(self.method, data)
        object.__setattr__(self, "params", _freeze(data))


def _nesting(text: str) -> None:
    depth, quoted, escaped = 0, False, False
    for char in text:
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in "[{":
            depth += 1
            if depth > MAX_NESTING:
                raise ProtocolError("nesting_limit")
        elif char in "]}":
            depth -= 1


def _pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ProtocolError("invalid_json")
        result[key] = value
    return result


def _constant(_value: str) -> object:
    raise ProtocolError("invalid_json")


def _json_value(value: object, depth: int = 0, budget: list[int] | None = None) -> None:
    """Bound traversal as well as encoded output; reject nonportable values."""
    if budget is None:
        budget = [MAX_FRAME_BYTES]

    def consume(size: int) -> None:
        budget[0] -= size
        if budget[0] < 0:
            raise ProtocolError("frame_limit")

    if isinstance(value, (dict, list)):
        if depth >= MAX_NESTING:
            raise ProtocolError("nesting_limit")
        consume(2)
        if isinstance(value, dict):
            for index, (key, child) in enumerate(value.items()):
                if not isinstance(key, str):
                    raise ProtocolError("invalid_json")
                consume(1 + bool(index))  # Colon, and commas between entries.
                _json_value(key, depth + 1, budget)
                _json_value(child, depth + 1, budget)
        else:
            for index, child in enumerate(value):
                consume(bool(index))
                _json_value(child, depth + 1, budget)
    elif isinstance(value, str):
        if len(value) > budget[0]:
            raise ProtocolError("frame_limit")
        if any(0xD800 <= ord(char) <= 0xDFFF for char in value):
            raise ProtocolError("invalid_json")
        consume(len(value.encode("utf-8")) + 2)
    elif type(value) is int:
        if value < -MAX_SAFE_INTEGER or value > MAX_SAFE_INTEGER:
            raise ProtocolError("invalid_json")
        consume(len(str(value)))
    elif type(value) is float:
        if not math.isfinite(value):
            raise ProtocolError("invalid_json")
        consume(len(str(value)))
    elif value is not None and type(value) is not bool:
        raise ProtocolError("invalid_json")
    else:
        consume(5 if value is False else 4)


def _result_payload(payload: object, run_id: str | None) -> None:
    if not isinstance(payload, dict):
        raise ProtocolError("invalid_result")
    required = {"status", "runtime_status", "task_verified", "error"}
    if not required <= payload.keys() or payload.keys() - required - {"budget", "recovery"}:
        raise ProtocolError("invalid_result")
    status, runtime = payload["status"], payload["runtime_status"]
    if not isinstance(status, str) or status not in RESULT_STATUSES or payload["task_verified"] is not False:
        raise ProtocolError("invalid_result")
    if runtime is not None and (not isinstance(runtime, str) or runtime not in _RUNTIME_STATUSES):
        raise ProtocolError("invalid_result")
    error = payload["error"]
    if error is not None:
        if not isinstance(error, dict) or set(error) != {"code", "message"}:
            raise ProtocolError("invalid_result")
        identity(error["code"], code="invalid_result")
        message = error["message"]
        if not isinstance(message, str) or len(message.encode("utf-8")) > 4096:
            raise ProtocolError("invalid_result")
    if status == "completed" and (run_id is None or runtime not in {"completed", "responded"} or error is not None):
        raise ProtocolError("invalid_result")
    if status == "rejected" and (run_id is not None or runtime is not None):
        raise ProtocolError("invalid_result")


def decode_request(raw: bytes) -> Request:
    """Decode one frame without LF; errors never quote any input values."""
    if len(raw) > MAX_FRAME_BYTES:
        raise ProtocolError("frame_limit")
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeError:
        pass
    else:
        _nesting(text)
        try:
            value = json.loads(text, object_pairs_hook=_pairs, parse_constant=_constant)
        except (ValueError, RecursionError) as exc:
            if isinstance(exc, ProtocolError):
                raise
        else:
            if not isinstance(value, dict):
                raise ProtocolError("invalid_request")
            if type(value.get("v")) is not int or value["v"] != 1:
                raise ProtocolError("unsupported_version")
            method = value.get("method")
            if not isinstance(method, str) or method not in _METHODS:
                raise ProtocolError("invalid_request")
            names = {"v", "id", "method", "params"}
            if method != "initialize":
                names.add("connection_id")
            _fields(value, names)
            return Request(value["id"], cast(RequestMethod, method), value.get("connection_id"), value["params"])
    # Raise outside the parser's exception handler: its exception retains raw
    # document text and must not become our traceback context.
    raise ProtocolError("invalid_json")


class FrameDecoder:
    """Incremental LF framing with bounded batches and a terminal error state."""

    def __init__(self) -> None:
        self._buffer = bytearray()
        self._closed = False

    @property
    def buffered_bytes(self) -> int:
        return len(self._buffer)

    def feed(self, chunk: bytes) -> list[Request]:
        """Consume at most 64 KiB; a malformed batch yields no requests."""
        if self._closed:
            raise ProtocolError("decoder_closed")
        try:
            if len(chunk) > MAX_CHUNK_BYTES:
                raise ProtocolError("chunk_limit")
            requests = []
            start = 0
            while start < len(chunk):
                end = chunk.find(b"\n", start)
                stop = end if end >= 0 else len(chunk)
                if len(self._buffer) + stop - start > MAX_FRAME_BYTES:
                    raise ProtocolError("frame_limit")
                self._buffer.extend(chunk[start:stop])
                if end < 0:
                    break
                raw = bytes(self._buffer)
                self._buffer.clear()
                requests.append(decode_request(raw))
                start = end + 1
            return requests
        except ProtocolError:
            self._closed = True
            self._buffer.clear()
            raise

    def finish(self) -> None:
        """Retire on EOF; an unfinished line is never implicitly executed."""
        if self._closed:
            raise ProtocolError("decoder_closed")
        self._closed = True
        incomplete = bool(self._buffer)
        self._buffer.clear()
        if incomplete:
            raise ProtocolError("unterminated_frame")


class ServerEncoder:
    """Order successfully encoded frames, without claiming their delivery."""

    def __init__(self) -> None:
        self._sequence = 0

    def encode(self, *, kind: FrameKind, request_id: int | None,
               session_id: str | None, run_id: str | None, payload: object) -> bytes:
        """Encode already-projected evidence, preserving literal text and LF."""
        if self._sequence >= MAX_SAFE_INTEGER:
            raise ProtocolError("sequence_exhausted")
        if not isinstance(kind, str) or kind not in _KINDS:
            raise ProtocolError("invalid_envelope")
        if request_id is not None:
            exact_integer(request_id, code="invalid_envelope")
        if session_id is not None:
            identity(session_id, code="invalid_envelope")
        if run_id is not None:
            identity(run_id, code="invalid_envelope")
            if session_id is None:
                raise ProtocolError("invalid_envelope")
        if kind == "result" and request_id is None:
            raise ProtocolError("invalid_envelope")
        frame = {"v": 1, "seq": self._sequence + 1, "kind": kind, "request_id": request_id,
                 "session_id": session_id, "run_id": run_id, "payload": payload}
        _json_value(frame)
        if kind == "result":
            _result_payload(payload, run_id)
        output = bytearray()
        encoder = json.JSONEncoder(ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        for part in encoder.iterencode(frame):
            encoded = part.encode("utf-8")
            if len(output) + len(encoded) > MAX_FRAME_BYTES:
                raise ProtocolError("frame_limit")
            output.extend(encoded)
        output.extend(b"\n")
        self._sequence += 1
        return bytes(output)
