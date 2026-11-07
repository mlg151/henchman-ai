"""Redaction is explicit, reusable, and separate from executable inputs."""

import pytest

from henchman.utils.evidence_redaction import EvidenceRedactor


def test_registered_secrets_and_marked_fields_are_redacted_without_mutation() -> None:
    redactor = EvidenceRedactor(["configured-secret"])
    payload = {
        "arguments": {"api_key": "marked-secret"},
        "result": "configured-secret and marked-secret",
        "count": 2,
        "tokens": 300,
        "key": "ordinary dictionary key",
    }
    safe = redactor.redact(payload)
    assert safe["arguments"]["api_key"] == "[REDACTED]"
    assert safe["result"] == "[REDACTED] and [REDACTED]"
    assert safe["tokens"] == 300
    assert safe["key"] == payload["key"]
    assert payload["arguments"]["api_key"] == "marked-secret"


def test_auth_headers_and_encoded_known_values() -> None:
    redactor = EvidenceRedactor(['private-"quoted"-secret'])
    assert "unregistered-header-value" not in redactor.text(
        "Authorization: Bearer unregistered-header-value\nContent-Type: text/plain"
    )
    assert "Content-Type: text/plain" in redactor.text("Authorization: token\nContent-Type: text/plain")
    assert "private-" not in redactor.text(r'private-\"quoted\"-secret')


def test_settings_environment_references_and_rotation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CUSTOM_LOGIN", "referenced-secret")
    redactor = EvidenceRedactor()
    redactor.register_config({"providers": {"custom": {"api_key": "${CUSTOM_LOGIN}"}}})
    redactor.register_config({"providers": {"custom": {"api_key": "rotated-secret"}}})
    assert redactor.text("referenced-secret rotated-secret") == "[REDACTED] [REDACTED]"
    monkeypatch.setenv("CUSTOM_LOGIN", "new-environment-secret")
    assert redactor.text("referenced-secret new-environment-secret") == "[REDACTED] [REDACTED]"


def test_marked_credential_lists_and_header_token_echoes() -> None:
    redactor = EvidenceRedactor()
    payload = {
        "api_keys": ["first-key-canary", "second-key-canary"],
        "Authorization": "Bearer header-token-canary",
        "result": "first-key-canary second-key-canary header-token-canary",
    }
    assert redactor.redact(payload)["result"] == "[REDACTED] [REDACTED] [REDACTED]"


@pytest.mark.parametrize("secret", ["secret-[REDACTED]-canary", "REDACTED]-canary"])
def test_marker_inside_a_credential_does_not_make_it_public(secret: str) -> None:
    redactor = EvidenceRedactor([secret, "RED"])
    safe = redactor.text(f"Echo: {secret}")
    assert secret not in safe
    assert redactor.text("[REDACTED]") == "[REDACTED]"
    assert redactor.text(safe) == safe


@pytest.mark.parametrize("spacing", ["  ", "\t", " \t "])
def test_bearer_whitespace_does_not_expose_token_echoes(spacing: str) -> None:
    redactor = EvidenceRedactor()
    safe = redactor.redact({
        "Authorization": f"Bearer{spacing}marked-secret-canary",
        "echo": "marked-secret-canary",
    })
    assert safe["echo"] == "[REDACTED]"


def test_non_json_evidence_objects_are_projected_without_changing_inputs() -> None:
    from pathlib import Path

    path = Path("private-canary")
    error = RuntimeError("transport private-canary")
    payload = {"path": path, "error": error, "count": 3, "enabled": True, "missing": None}
    safe = EvidenceRedactor(["private-canary"]).redact(payload)
    assert safe == {"path": "[REDACTED]", "error": "transport [REDACTED]", "count": 3, "enabled": True, "missing": None}
    assert payload["path"] is path and payload["error"] is error


def test_marked_non_json_credential_registers_its_display_echo() -> None:
    from pathlib import Path

    payload = {"api_key": Path("marked-canary"), "echo": "marked-canary"}
    safe = EvidenceRedactor().redact(payload)
    assert safe["api_key"] == "[REDACTED]" and safe["echo"] == "[REDACTED]"
