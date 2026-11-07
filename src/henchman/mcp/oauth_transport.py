"""Immutable OAuth HTTP authority and leases; credentials remain execution-only data."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from importlib.metadata import version

import httpx2

from henchman.mcp.oauth import OAuthBinding, OAuthError
from henchman.mcp.oauth_store import OAuthAuthority, OAuthCredentialStore
from henchman.utils.evidence_redaction import EvidenceRedactor


def require_oauth_http_profile() -> None:
    """Qualify the trace event immediately before HTTP/1.1 header transmission."""
    if version("httpx2") != "2.16.0" or version("httpcore2") != "2.16.0":
        raise OAuthError("Unsupported OAuth HTTP runtime profile; expected httpx2/httpcore2 2.16.0")


def authorize_http_request(
    request: httpx2.Request, *, lease: Callable[[], OAuthAccessLease], authorize: Callable[[], None],
) -> OAuthAccessLease:
    """Check after capacity; recheck after connection setup at the pre-header trace."""
    require_oauth_http_profile()
    authorize()
    captured = lease()
    if "authorization" in request.headers or "proxy-authorization" in request.headers:
        raise OAuthError("OAuth HTTP request cannot override authentication headers")
    request.headers["authorization"] = captured.authorization

    async def trace(event: str, _info: dict[str, object]) -> None:
        if event == "http11.send_request_headers.started":
            authorize()
            current = lease()
            if current != captured:
                raise OAuthError("OAuth HTTP credential changed before header dispatch")
        elif event.startswith("http2."):
            raise OAuthError("OAuth HTTP/2 dispatch is not qualified")

    request.extensions["trace"] = trace
    return captured


@dataclass(frozen=True, repr=False)
class OAuthAccessLease:
    """One checked access token and the exact authority a rejection may affect."""

    authorization: str
    _store: OAuthCredentialStore
    _authority: OAuthAuthority
    _token_sha256: str

    def reject(self) -> bool:
        return self._store.reject_access(self._authority, self._token_sha256)


@dataclass(frozen=True, repr=False)
class OAuthHttpAuthority:
    """Captured project/config/store authority; capturing it does not release a token."""

    binding: OAuthBinding
    _store: OAuthCredentialStore
    _authority: OAuthAuthority
    _common_guard: Callable[[], None]
    _active_guard: Callable[[], None]

    def for_client(self, owner: object) -> OAuthHttpPermit:
        return OAuthHttpPermit(self, owner)

    def register_evidence(self, policy: EvidenceRedactor) -> None:
        self._store.register_evidence(policy)

    def _lease(self, endpoint: str, *, closing: bool = False) -> OAuthAccessLease:
        if endpoint != self.binding.endpoint:
            raise OAuthError("OAuth HTTP destination does not match its captured resource")
        self._common_guard()
        if not closing:
            self._active_guard()
        credentials = self._store.credentials(self._authority)
        if credentials is None:
            raise OAuthError("OAuth access credential is unavailable or expired; explicit refresh or login is required")
        return OAuthAccessLease("Bearer " + credentials.access_token, self._store, self._authority,
                                hashlib.sha256(credentials.access_token.encode()).hexdigest())


@dataclass(frozen=True, repr=False)
class OAuthHttpPermit:
    """Normal request authority associated with one exact client owner."""

    authority: OAuthHttpAuthority
    _owner: object

    def check(self) -> None:
        self.authority._common_guard()
        self.authority._active_guard()
        self.authority._store.check_authority(self.authority._authority)

    def request(self, method: str, endpoint: str) -> OAuthAccessLease:
        if method != "POST":
            raise OAuthError("OAuth request permit does not authorize this HTTP method")
        return self.authority._lease(endpoint)

    def closing(self, owner: object, session_id: str) -> OAuthClosingPermit:
        if owner is not self._owner or not session_id:
            raise OAuthError("OAuth closing permit does not match its client and session")
        return OAuthClosingPermit(self.authority, self._owner, session_id)


@dataclass(frozen=True, repr=False)
class OAuthClosingPermit:
    """Exact legacy session deletion, retaining common guards after registration closes."""

    _authority: OAuthHttpAuthority
    _owner: object
    _session_id: str

    def request(self, method: str, endpoint: str, session_id: str) -> OAuthAccessLease:
        if method != "DELETE" or session_id != self._session_id:
            raise OAuthError("OAuth closing permit does not authorize this HTTP request")
        return self._authority._lease(endpoint, closing=True)
