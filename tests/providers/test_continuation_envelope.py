"""Provider-bound continuation is immutable protocol data, never display text."""

from dataclasses import replace
from types import SimpleNamespace

import pytest

from henchman.providers.continuation import (
    ContinuationEnvelope,
    ProviderContinuationError,
    continuation_binding,
    project_continuation,
)
from henchman.utils.evidence_redaction import EvidenceRedactor


def provider(name="anthropic", model="model-a", endpoint="https://offline.invalid/v1", key="offline-test"):
    return SimpleNamespace(name=name, default_model=model, api_key=key,
                           _client=SimpleNamespace(base_url=endpoint))


def native_payload():
    return [{"type": "thinking", "thinking": "inspect state", "signature": "offline-signature"},
            {"type": "redacted_thinking", "data": "offline-opaque"},
            {"type": "text", "text": "Checking."},
            {"type": "tool_use", "id": "call", "name": "inspect", "input": {}}]


def test_envelope_detaches_payload_and_roundtrips_exact_order():
    payload = native_payload()
    envelope = ContinuationEnvelope.create(provider(), payload)
    payload[0]["signature"] = "mutated"
    assert envelope.payload() == native_payload()
    restored = ContinuationEnvelope.from_dict(envelope.to_dict())
    assert restored == envelope
    output = restored.payload()
    output.reverse()
    assert restored.payload() == native_payload()


@pytest.mark.parametrize("changed", [provider(model="model-b"), provider(endpoint="https://other.invalid/v1"),
                                     provider(key="other-key"), provider(name="openrouter")])
def test_binding_rejects_model_endpoint_credential_and_provider_changes(changed):
    envelope = ContinuationEnvelope.create(provider(), native_payload())
    with pytest.raises(ProviderContinuationError, match="incompatible"):
        envelope.require_compatible(changed)


def test_alias_identity_is_exact_and_secret_is_absent_from_binding():
    source = provider()
    source._accounting_provider_name = "configured-native"
    binding = continuation_binding(source)
    assert binding["provider"] == "configured-native"
    assert "offline-test" not in str(binding) and "https://" not in str(binding)


def test_unknown_version_or_modified_payload_is_not_replayable():
    envelope = ContinuationEnvelope.create(provider(), native_payload()).to_dict()
    for field, value in (("version", 2), ("payload_json", "[]"), ("profile", "invented.v1")):
        with pytest.raises(ProviderContinuationError):
            ContinuationEnvelope.from_dict({**envelope, field: value})


def test_redaction_marks_signed_payload_unavailable_without_mutating_live_bytes():
    source = ContinuationEnvelope.create(provider(), native_payload())
    policy = EvidenceRedactor()
    policy.register_secret("offline-signature")
    saved = project_continuation(source.to_dict(), policy)
    assert saved["status"] == "unavailable" and saved["payload_json"] is None
    assert saved["reason"] == "redacted_continuation"
    assert "offline-signature" not in str(saved)
    assert source.payload() == native_payload()
    with pytest.raises(ProviderContinuationError, match="unavailable"):
        ContinuationEnvelope.from_dict(saved).require_compatible(provider())


def test_incomplete_thinking_signature_cannot_be_qualified():
    payload = native_payload()
    payload[0]["signature"] = ""
    with pytest.raises(ProviderContinuationError, match="incomplete"):
        ContinuationEnvelope.create(provider(), payload)


def test_openrouter_array_and_deepseek_text_profiles_keep_distinct_shapes():
    details = [{"type": "reasoning.encrypted", "data": "opaque", "id": None, "index": 0,
                "format": "anthropic-claude-v1"}]
    assert ContinuationEnvelope.create(provider(name="openrouter"), details).payload() == details
    assert ContinuationEnvelope.create(provider(name="deepseek"), "reason").payload() == "reason"
    with pytest.raises(ProviderContinuationError):
        ContinuationEnvelope.create(provider(name="openai-compatible"), details)
    with pytest.raises(ProviderContinuationError):
        ContinuationEnvelope.create(provider(name="deepseek"), details)


def test_unavailable_payload_cannot_claim_complete_status():
    envelope = ContinuationEnvelope.create(provider(), native_payload())
    with pytest.raises(ProviderContinuationError):
        replace(envelope, payload_json=None)


@pytest.mark.parametrize("field", ["provider", "model"])
def test_redaction_removes_known_credential_from_binding_labels_and_invalidates_payload(field):
    source = provider(model="model-a")
    if field == "provider":
        source._accounting_provider_name = "alias-binding-secret"
    else:
        source.default_model = "model-binding-secret"
    envelope = ContinuationEnvelope.create(source, native_payload())
    policy = EvidenceRedactor()
    policy.register_secret("binding-secret")
    safe = project_continuation(envelope.to_dict(), policy)
    assert "binding-secret" not in str(safe)
    assert safe["status"] == "unavailable" and safe["payload_json"] is None
    assert safe[field]
    assert envelope.payload() == native_payload()


@pytest.mark.parametrize("kind", ["depth", "cycle", "nodes", "label"])
def test_envelope_limits_apply_before_json_serialization(kind):
    source = provider()
    payload = native_payload()
    if kind == "label":
        source.default_model = "m" * 1025
    elif kind == "nodes":
        payload[3]["input"] = {"values": [None] * 65537}
    elif kind == "cycle":
        payload[3]["input"]["self"] = payload
    else:
        nested = payload[3]["input"]
        for _ in range(65):
            nested["child"] = {}
            nested = nested["child"]
    with pytest.raises(ProviderContinuationError):
        ContinuationEnvelope.create(source, payload)
