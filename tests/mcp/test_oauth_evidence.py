"""OAuth credential evidence is learned before validation, rotation and revocation."""

import json

import pytest

from henchman.mcp.auth import McpAuthService
from henchman.mcp.oauth_store import OAuthCredentials, OAuthStoreError
from henchman.utils.evidence_redaction import EvidenceRedactor
from tests.mcp.test_oauth_store import binding, credentials, ready, store


def test_facade_retains_one_store_and_historical_evidence(tmp_path):
    facade = McpAuthService(tmp_path)
    service = facade.oauth_store()
    assert facade.oauth_store() is service
    authority = ready(service)
    first = EvidenceRedactor()
    service.register_evidence(first)
    claim = service.begin_refresh(authority)
    current = service.complete(claim, credentials("new-access-canary", "new-refresh-canary"))
    service.logout("fixture")
    late = EvidenceRedactor()
    service.register_evidence(late)
    for policy in (first, late):
        assert policy.text("access-private-canary refresh-private-canary new-access-canary new-refresh-canary") == " ".join(["[REDACTED]"] * 4)
    with pytest.raises(OAuthStoreError):
        service.credentials(current)


def test_invalid_new_token_is_registered_before_completion_validation(tmp_path):
    service = store(tmp_path)
    policy = EvidenceRedactor()
    service.register_evidence(policy)
    claim = service.begin_login(service.bind(binding()))
    malformed = OAuthCredentials.model_construct(access_token="invalid-new-canary\r\n", refresh_token="invalid-refresh-canary",
                                                 token_endpoint="https://issuer.example/token", scopes=(), issued_at=100, expires_at=90)
    with pytest.raises(OAuthStoreError):
        service.complete(claim, malformed)
    assert policy.text("invalid-new-canary\r\n invalid-refresh-canary") == "[REDACTED] [REDACTED]"


def test_read_registers_external_credentials_before_invalid_record_diagnostic(tmp_path):
    service = store(tmp_path)
    ready(service)
    policy = EvidenceRedactor()
    service.register_evidence(policy)
    path = tmp_path / ".henchman/mcp/oauth.json"
    payload = json.loads(path.read_text())
    payload["records"]["fixture"]["credentials"]["access_token"] = "external-new-canary"
    payload["records"]["fixture"]["credentials"]["expires_at"] = -1
    path.write_text(json.dumps(payload))
    with pytest.raises(OAuthStoreError):
        service.status("fixture")
    assert policy.text("external-new-canary") == "[REDACTED]"


def test_sensitive_response_registration_propagates_to_bound_policy(tmp_path):
    service = store(tmp_path)
    policy = EvidenceRedactor()
    service.register_evidence(policy)
    service.remember_evidence({"access_token": "reply-access-canary", "refresh_token": "reply-refresh-canary"})
    assert policy.text("reply-access-canary reply-refresh-canary") == "[REDACTED] [REDACTED]"
