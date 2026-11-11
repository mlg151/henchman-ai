"""Strict, non-rendered provider continuation envelopes and replay boundaries.

Profiles qualify only the existing native Messages and compatible Chat APIs.
Their signatures are opaque; this module checks local integrity and binding,
not the provider's cryptographic signature or cross-model compatibility.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass, field, replace
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from henchman.providers.base import Message, ModelProvider
    from henchman.utils.evidence_redaction import EvidenceRedactor

_PROFILES = {
    "anthropic": "anthropic.messages.v1",
    "openrouter": "openrouter.reasoning_details.v1",
    "deepseek": "deepseek.reasoning_content.v1",
}
_MAX_BYTES = 4 * 1024 * 1024


class ProviderContinuationError(RuntimeError):
    """Required continuation is unavailable or incompatible; never retry it."""

    def __init__(self, reason: str, *, continuation: dict[str, Any] | None = None) -> None:
        self.continuation = continuation
        self.reason = reason
        super().__init__(f"Provider continuation prevented dispatch: {reason}")


def _validate_json_bounds(value: Any) -> tuple[int, int]:
    """Bound allocation before encoding; depth also rejects cyclic structures."""
    stack = [(value, 0)]
    nodes = 0
    size = 0
    while stack:
        item, depth = stack.pop()
        nodes += 1
        if depth > 64 or nodes > 65536:
            raise ProviderContinuationError("continuation_too_complex")
        size += 2
        if isinstance(item, str):
            if len(item) > _MAX_BYTES:
                raise ProviderContinuationError("continuation_too_large")
            try:
                size += len(item.encode())
            except UnicodeError as exc:
                raise ProviderContinuationError("invalid_continuation") from exc
        elif isinstance(item, dict):
            if len(item) > 65536 or any(not isinstance(key, str) for key in item):
                raise ProviderContinuationError("invalid_continuation")
            stack.extend((nested, depth + 1) for pair in item.items() for nested in pair)
        elif isinstance(item, list):
            if len(item) > 65536:
                raise ProviderContinuationError("continuation_too_complex")
            stack.extend((nested, depth + 1) for nested in item)
        elif item is None or isinstance(item, bool):
            pass
        elif isinstance(item, int):
            if item.bit_length() > 14000:
                raise ProviderContinuationError("invalid_continuation")
        elif isinstance(item, float):
            if not math.isfinite(item):
                raise ProviderContinuationError("invalid_continuation")
        else:
            raise ProviderContinuationError("invalid_continuation")
        if size > _MAX_BYTES:
            raise ProviderContinuationError("continuation_too_large")

    return nodes, size


def _json(value: Any) -> str:
    _validate_json_bounds(value)
    try:
        encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (ValueError, TypeError, RecursionError) as exc:
        raise ProviderContinuationError("invalid_continuation") from exc
    if len(encoded.encode()) > _MAX_BYTES:
        raise ProviderContinuationError("continuation_too_large")
    return encoded


class ContinuationAccumulator:
    """Bound opaque fragments before copying arrays or concatenating text.

    Fragment framing counts toward the limit, conservatively bounding both
    retained bytes and node count even when many tiny deltas are returned.
    """

    def __init__(self) -> None:
        self._bytes = 0
        self._nodes = 0

    def add(self, value: Any) -> None:
        nodes, _size = _validate_json_bounds(value)
        size = len(_json(value).encode())
        if self._bytes + size > _MAX_BYTES:
            raise ProviderContinuationError("continuation_too_large")
        if self._nodes + nodes > 65536:
            raise ProviderContinuationError("continuation_too_complex")
        self._bytes += size
        self._nodes += nodes


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def effective_continuation_model(provider: ModelProvider, options: dict[str, Any] | None = None) -> str:
    """Resolve the model sent by the adapter, including explicit body overrides."""
    defaults = getattr(provider, "request_defaults", None)
    values = {**(defaults if isinstance(defaults, dict) else {}), **(options or {})}
    extra = values.get("extra_body") or {}
    if not isinstance(extra, dict):
        raise ProviderContinuationError("unverifiable_continuation_request")
    model = extra.get("model", values.get("model", getattr(provider, "default_model", None)))
    if not isinstance(model, str) or not model or len(model) > 1024:
        raise ProviderContinuationError("unverifiable_continuation_binding")
    return model


def continuation_binding(provider: ModelProvider, *, model: str | None = None) -> dict[str, str]:
    """Bind to the actual adapter, configured alias, effective model and account.

    Only a digest of endpoint and credential identity is retained. A replacement
    key deliberately invalidates reuse; account equivalence is not inferred.
    """
    profile = _PROFILES.get(provider.name)
    if profile is None:
        raise ProviderContinuationError("unsupported_continuation_profile")
    name = getattr(provider, "_accounting_provider_name", None) or provider.name
    selected = model if model is not None else effective_continuation_model(provider)
    endpoint = getattr(getattr(provider, "_client", None), "base_url", None)
    if endpoint is None:
        endpoint = getattr(provider, "base_url", "")
    if not isinstance(name, str) or not name or not isinstance(selected, str) or not selected or len(name) > 1024 or len(selected) > 1024 or not endpoint:
        raise ProviderContinuationError("unverifiable_continuation_binding")
    key = getattr(getattr(provider, "_client", None), "api_key", None)
    if not isinstance(key, str):
        key = getattr(provider, "api_key", None)
    headers = getattr(getattr(provider, "_client", None), "default_headers", None)
    account_headers = {str(name).lower(): value for name, value in headers.items()
                       if str(name).lower() in {"authorization", "x-api-key", "api-key"}} if isinstance(headers, dict) else {}
    scope = _json([str(endpoint).rstrip("/"), key, account_headers])
    return {"provider": name, "model": selected, "profile": profile, "scope_sha256": _digest(scope)}


def _validate_payload(profile: str, payload: Any) -> None:
    if profile == _PROFILES["deepseek"]:
        if not isinstance(payload, str):
            raise ProviderContinuationError("invalid_continuation")
        return
    if not isinstance(payload, list) or not payload or any(not isinstance(item, dict) for item in payload):
        raise ProviderContinuationError("invalid_continuation")
    for block in payload:
        kind = block.get("type")
        if profile == _PROFILES["anthropic"]:
            if kind == "thinking":
                if not isinstance(block.get("thinking"), str) or not isinstance(block.get("signature"), str) or not block["signature"]:
                    raise ProviderContinuationError("incomplete_continuation")
            elif kind == "redacted_thinking":
                if not isinstance(block.get("data"), str) or not block["data"]:
                    raise ProviderContinuationError("incomplete_continuation")
            elif kind == "text":
                if not isinstance(block.get("text"), str):
                    raise ProviderContinuationError("invalid_continuation")
            elif kind == "tool_use":
                if not all(isinstance(block.get(key), str) and block[key] for key in ("id", "name")) or not isinstance(block.get("input"), dict):
                    raise ProviderContinuationError("invalid_continuation")
            else:
                raise ProviderContinuationError("unsupported_continuation_block")
        elif profile == _PROFILES["openrouter"]:
            if not isinstance(kind, str):
                raise ProviderContinuationError("invalid_continuation")
            field = {"reasoning.text": "text", "reasoning.summary": "summary", "reasoning.encrypted": "data"}.get(kind)
            if field is None or not isinstance(block.get(field), str):
                raise ProviderContinuationError("unsupported_continuation_block")
            for key in ("id", "format", "signature"):
                if block.get(key) is not None and not isinstance(block[key], str):
                    raise ProviderContinuationError("invalid_continuation")
            if "index" in block and (type(block["index"]) is not int or block["index"] < 0):
                raise ProviderContinuationError("invalid_continuation")


@dataclass(frozen=True)
class ContinuationEnvelope:
    """Versioned immutable serialized payload, distinct from visible reasoning."""

    provider: str
    model: str
    profile: str
    scope_sha256: str
    payload_json: str | None = field(repr=False)
    payload_sha256: str
    request_sha256: str = _digest("{}")
    status: str = "complete"
    reason: str | None = None
    version: int = 1

    def __post_init__(self) -> None:
        if type(self.version) is not int or self.version != 1:
            raise ProviderContinuationError("unsupported_continuation_version")
        if self.profile not in _PROFILES.values():
            raise ProviderContinuationError("unsupported_continuation_profile")
        if any(not isinstance(value, str) or not value.strip() or len(value) > 1024 for value in (self.provider, self.model)):
            raise ProviderContinuationError("invalid_continuation_binding")
        if any(not isinstance(value, str) or re.fullmatch(r"[a-f0-9]{64}", value) is None for value in (self.scope_sha256, self.payload_sha256, self.request_sha256)):
            raise ProviderContinuationError("invalid_continuation_digest")
        if not isinstance(self.status, str) or (self.reason is not None and not isinstance(self.reason, str)):
            raise ProviderContinuationError("invalid_continuation_status")
        if self.status == "unavailable":
            if self.payload_json is not None or self.reason not in {"redacted_continuation", "incomplete_continuation", "compacted_continuation"}:
                raise ProviderContinuationError("invalid_unavailable_continuation")
            return
        if self.status != "complete" or self.reason is not None or not isinstance(self.payload_json, str):
            raise ProviderContinuationError("invalid_continuation_status")
        if len(self.payload_json.encode()) > _MAX_BYTES or _digest(self.payload_json) != self.payload_sha256:
            raise ProviderContinuationError("invalid_continuation_digest")
        try:
            payload = json.loads(self.payload_json)
        except (ValueError, RecursionError) as exc:
            raise ProviderContinuationError("invalid_continuation") from exc
        if _json(payload) != self.payload_json:
            raise ProviderContinuationError("invalid_continuation_encoding")
        _validate_payload(self.profile, payload)

    @classmethod
    def create(cls, provider: ModelProvider, payload: Any, *, model: str | None = None) -> ContinuationEnvelope:
        return cls.from_payload(continuation_binding(provider, model=model), payload)

    @classmethod
    def from_payload(cls, binding: dict[str, str], payload: Any) -> ContinuationEnvelope:
        """Use the detached binding captured before the request was dispatched."""
        encoded = _json(payload)
        return cls(provider=binding["provider"], model=binding["model"], profile=binding["profile"],
                   scope_sha256=binding["scope_sha256"], request_sha256=binding.get("request_sha256", _digest("{}")),
                   payload_json=encoded, payload_sha256=_digest(encoded))

    @classmethod
    def unavailable(cls, binding: dict[str, str]) -> ContinuationEnvelope:
        """Record an incomplete stream without pretending to retain its payload."""
        return cls(provider=binding["provider"], model=binding["model"], profile=binding["profile"],
                   scope_sha256=binding["scope_sha256"], request_sha256=binding.get("request_sha256", _digest("{}")),
                   payload_json=None, payload_sha256=_digest("null"), status="unavailable", reason="incomplete_continuation")

    @classmethod
    def from_dict(cls, value: Any) -> ContinuationEnvelope:
        if not isinstance(value, dict) or set(value) != {
            "provider", "model", "profile", "scope_sha256", "payload_json", "payload_sha256", "request_sha256", "status", "reason", "version",
        }:
            raise ProviderContinuationError("invalid_continuation_envelope")
        try:
            return cls(**value)
        except TypeError as exc:
            raise ProviderContinuationError("invalid_continuation_envelope") from exc

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def payload(self) -> Any:
        if self.status != "complete" or self.payload_json is None:
            raise ProviderContinuationError("unavailable_continuation")
        return json.loads(self.payload_json)

    def require_compatible(self, provider: ModelProvider, *, model: str | None = None, request_binding: dict[str, str] | None = None) -> None:
        if self.status != "complete":
            raise ProviderContinuationError("unavailable_continuation")
        binding = request_binding if request_binding is not None else continuation_binding(provider, model=model)
        if any(getattr(self, key) != value for key, value in binding.items()):
            raise ProviderContinuationError("incompatible_continuation")


def copy_continuation(value: Any) -> dict[str, Any] | None:
    return ContinuationEnvelope.from_dict(value).to_dict() if value is not None else None


def project_continuation(value: Any, redactor: EvidenceRedactor) -> dict[str, Any] | None:
    """Redaction invalidates replay instead of silently changing signed bytes."""
    if value is None:
        return None
    envelope = ContinuationEnvelope.from_dict(value)
    changed = False
    if envelope.status == "complete":
        changed = _json(redactor.redact(envelope.payload())) != envelope.payload_json
    safe_provider = redactor.text(envelope.provider)
    safe_model = redactor.text(envelope.model)
    changed = safe_provider != envelope.provider or safe_model != envelope.model or changed
    if changed:
        envelope = replace(envelope, provider=safe_provider or "[redacted]", model=safe_model or "[redacted]",
                           payload_json=None, status="unavailable", reason="redacted_continuation")
    return envelope.to_dict()


def validate_continuations(messages: list[Message], provider: ModelProvider, *, model: str | None = None, request_binding: dict[str, str] | None = None) -> None:
    """Reject unknown replay evidence before provider or model state changes."""
    for message in messages:
        if (message.role == "assistant" and message.tool_calls and message.reasoning_content is not None
                and message.continuation is None and getattr(provider, "name", None) in {"anthropic", "deepseek"}):
            raise ProviderContinuationError("unqualified_legacy_reasoning_content")
        if message.reasoning_details is not None:
            raise ProviderContinuationError("unqualified_legacy_reasoning_details")
        if message.continuation is not None:
            envelope = ContinuationEnvelope.from_dict(message.continuation)
            envelope.require_compatible(provider, model=model, request_binding=request_binding)
            validate_message_continuation(message)


def validate_message_continuation(message: Message) -> None:
    """A signed native block array must agree with its executable transcript."""
    if message.continuation is None:
        return
    envelope = ContinuationEnvelope.from_dict(message.continuation)
    if message.role != "assistant":
        raise ProviderContinuationError("invalid_continuation_role")
    payload = envelope.payload()
    if envelope.profile == _PROFILES["anthropic"]:
        text = "".join(block["text"] for block in payload if block["type"] == "text")
        thinking = "".join(block["thinking"] for block in payload if block["type"] == "thinking")
        calls = [(block["id"], block["name"], block["input"]) for block in payload if block["type"] == "tool_use"]
        actual = [(call.id, call.name, call.arguments) for call in message.tool_calls or []]
        if text != (message.content or "") or thinking != (message.reasoning_content or "") or calls != actual:
            raise ProviderContinuationError("continuation_transcript_mismatch")


def request_continuation_binding(provider: ModelProvider, params: dict[str, Any]) -> dict[str, str] | None:
    """Qualify only explicit adapter profiles and a verifiable request identity."""
    if provider.name not in _PROFILES:
        return None
    extra = params.get("extra_body") or {}
    if not isinstance(extra, dict):
        raise ProviderContinuationError("unverifiable_continuation_request")
    # Header overrides may change account or routing without a matching adapter.
    if params.get("extra_headers") or any(key in extra for key in ("messages", "system")):
        raise ProviderContinuationError("unverifiable_continuation_request")
    binding = continuation_binding(provider, model=extra.get("model", params.get("model", getattr(provider, "default_model", None))))
    options = {**params, **extra}
    required_settings = {key: options[key] for key in ("thinking", "reasoning", "reasoning_effort", "output_config", "betas") if key in options}
    binding["request_sha256"] = _digest(_json(required_settings))
    return binding


def validate_runtime_continuations(messages: list[Message], provider: ModelProvider, options: dict[str, Any] | None = None) -> None:
    """Preflight the actual runtime defaults before switches or compaction."""
    if not any(message.continuation is not None for message in messages):
        validate_continuations(messages, provider)
        return
    defaults = getattr(provider, "request_defaults", None)
    values = {**(defaults if isinstance(defaults, dict) else {}), **(options or {})}
    binding = request_continuation_binding(provider, values)
    validate_continuations(messages, provider, model=effective_continuation_model(provider, values), request_binding=binding)
