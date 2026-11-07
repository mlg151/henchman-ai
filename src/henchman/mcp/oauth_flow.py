"""Explicit bounded OAuth flows; no default browser, runtime activation or RPC replay."""

from __future__ import annotations

import math
import re
import secrets
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from http.cookiejar import CookieJar
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import anyio
import httpx2
from mcp.client.auth import PKCEParameters

from henchman.config.mcp import oauth_origin
from henchman.mcp.diagnostics import http_diagnostics
from henchman.mcp.http_transport import _NoCookies
from henchman.mcp.oauth import (
    OAUTH_DOCUMENT_BYTES,
    OAUTH_HEADER_BYTES,
    OAuthBinding,
    OAuthDiscovery,
    OAuthError,
    _scopes,
    bounded_oauth_json,
    discover_oauth,
)
from henchman.mcp.oauth_callback import OAuthCallback
from henchman.mcp.oauth_store import (
    OAuthAuthority,
    OAuthClaim,
    OAuthCredentials,
    OAuthCredentialStore,
    OAuthStoreError,
)
from henchman.utils.evidence_redaction import EvidenceRedactor

OAUTH_LOGIN_TIMEOUT = 300.0
OAUTH_TOKEN_TIMEOUT = 30.0
OAUTH_AUTHORIZATION_URL_BYTES = 8192


@dataclass
class _Attempt:
    dispatched: bool = False


def _time(clock: Callable[[], float]) -> float:
    value = clock()
    if isinstance(value, bool) or not math.isfinite(value) or value < 0:
        raise OAuthError("OAuth credential clock is invalid")
    return value


def _endpoint(url: str) -> httpx2.URL:
    try:
        parsed = urlsplit(url)
        endpoint = httpx2.URL(url)
        expected_path = (parsed.path or "/") + ("?" + parsed.query if parsed.query else "")
        if endpoint.raw_path.decode("ascii") != expected_path:
            raise ValueError
        return endpoint
    except (ValueError, httpx2.InvalidURL):
        raise OAuthError("OAuth endpoint changes during HTTP transport normalization") from None


def _authorization_url(
    discovery: OAuthDiscovery, *, redirect_uri: str, state: str, code_challenge: str, scopes: tuple[str, ...],
) -> str:
    discovery.binding.check_destination(discovery.authorization_endpoint)
    _endpoint(discovery.authorization_endpoint)
    parsed = urlsplit(discovery.authorization_endpoint)
    try:
        if re.search(r"%(?![0-9a-fA-F]{2})", parsed.query):
            raise ValueError
        existing = parse_qsl(parsed.query, keep_blank_values=True, strict_parsing=True, errors="strict", max_num_fields=32)
        if len(dict(existing)) != len(existing):
            raise ValueError
        parameters = {"response_type": "code", "client_id": discovery.binding.client_id, "redirect_uri": redirect_uri,
                      "state": state, "code_challenge": code_challenge, "code_challenge_method": "S256",
                      "resource": discovery.binding.resource}
        if scopes:
            parameters["scope"] = " ".join(scopes)
        if set(dict(existing)) & (set(parameters) | {"scope", "code_verifier", "client_secret"}):
            raise ValueError
        result = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode([*existing, *parameters.items()]), ""))
        if len(result.encode()) > OAUTH_AUTHORIZATION_URL_BYTES:
            raise ValueError
        return result
    except (ValueError, UnicodeError):
        raise OAuthError("OAuth authorization URL parameters are invalid or exceed their bound") from None


def _token_credentials(
    payload: dict[str, object], *, endpoint: str, issued_at: float, scopes: tuple[str, ...], previous_refresh: str | None,
) -> OAuthCredentials:
    try:
        token_type = payload.get("token_type")
        if not isinstance(token_type, str) or token_type.lower() != "bearer":
            raise ValueError
        expiry = payload.get("expires_in")
        if "expires_in" in payload and (type(expiry) is not int or not 0 <= expiry <= 2**31 - 1):
            raise ValueError
        if "scope" in payload:
            value = payload["scope"]
            if not isinstance(value, str):
                raise ValueError
            scopes = _scopes(value.split(" "))
        refresh = payload.get("refresh_token", previous_refresh)
        if "refresh_token" in payload and not isinstance(refresh, str):
            raise ValueError
        return OAuthCredentials.model_validate({
            "access_token": payload.get("access_token"), "refresh_token": refresh, "token_endpoint": endpoint,
            "scopes": scopes, "issued_at": issued_at,
            "expires_at": issued_at + expiry if isinstance(expiry, int) else None,
        })
    except (ValueError, TypeError, OverflowError, OAuthError):
        raise OAuthError("OAuth token response is invalid; credential values withheld") from None


async def _token_request(
    store: OAuthCredentialStore, claim: OAuthClaim, *, endpoint: str, fields: dict[str, str], scopes: tuple[str, ...],
    authorize: Callable[[], None], clock: Callable[[], float], attempt: _Attempt,
) -> OAuthAuthority:
    binding = claim.authority.binding
    binding.check_destination(endpoint)
    target = _endpoint(endpoint)
    body = urlencode(fields).encode("ascii")
    if len(body) > OAUTH_DOCUMENT_BYTES:
        raise OAuthError("OAuth token request exceeds its bound")
    with anyio.fail_after(OAUTH_TOKEN_TIMEOUT):
        async with httpx2.AsyncClient(trust_env=False, follow_redirects=False, timeout=OAUTH_TOKEN_TIMEOUT,
                                      cookies=CookieJar(policy=_NoCookies())) as client:
            request = client.build_request("POST", target, content=body, headers={
                "content-type": "application/x-www-form-urlencoded", "accept": "application/json", "accept-encoding": "identity",
            })
            if request.url != target:
                raise OAuthError("OAuth token destination changed before dispatch")
            authorize()
            store.check_claim(claim)
            binding.check_destination(endpoint)
            issued_at = _time(clock)
            attempt.dispatched = True
            response = await client.send(request, stream=True, follow_redirects=False)
            try:
                store.remember_evidence(dict(response.headers))
                if sum(len(key) + len(value) for key, value in response.headers.raw) > OAUTH_HEADER_BYTES:
                    raise OAuthError("OAuth token response headers exceed their bound")
                if (response.headers.get("content-encoding", "identity").strip().lower() != "identity"
                    or response.headers.get("content-type", "").split(";")[0].strip().lower() != "application/json"):
                    raise OAuthError("OAuth token response encoding is unsupported")
                raw = bytearray()
                async for part in response.aiter_raw():
                    if len(raw) + len(part) > OAUTH_DOCUMENT_BYTES:
                        raise OAuthError("OAuth token response exceeds its bound")
                    raw.extend(part)
                payload = bounded_oauth_json(bytes(raw))
                store.remember_evidence(payload)
                if response.status_code != 200:
                    raise OAuthError("OAuth token exchange was rejected; no redirect or retry")
                credentials = _token_credentials(payload, endpoint=endpoint, issued_at=issued_at, scopes=scopes,
                                                 previous_refresh=claim.refresh_token)
                authorize()
                store.check_claim(claim)
                return store.complete(claim, credentials)
            finally:
                await response.aclose()


def _failed_claim(store: OAuthCredentialStore, claim: OAuthClaim | None, attempt: _Attempt, error: BaseException) -> None:
    if claim is not None and not attempt.dispatched:
        try:
            store.abandon(claim)
        except OAuthStoreError:
            error.add_note("OAuth claim could not be settled; inspect its current state before retrying.")


async def login_oauth(
    binding: OAuthBinding, store: OAuthCredentialStore, *, authorize: Callable[[], None],
    browser_opener: Callable[[str], Awaitable[None]], evidence: EvidenceRedactor,
    challenge: str | None = None, clock: Callable[[], float] = time.time,
) -> OAuthAuthority:
    """Perform one explicit native login, using only a caller-owned async browser opener."""
    claim = None
    attempt = _Attempt()
    try:
        with http_diagnostics(), anyio.fail_after(OAUTH_LOGIN_TIMEOUT):
            store.register_evidence(evidence)
            authorize()
            authority = store.bind(binding)

            def guard() -> None:
                authorize()
                if claim is None:
                    store.check_authority(authority)
                else:
                    store.check_claim(claim)

            discovery = await discover_oauth(binding, authorize=guard, challenge=challenge)
            guard()
            claim = store.begin_login(authority)
            scopes = _scopes(list(dict.fromkeys((*claim.previous_scopes, *discovery.scopes))))
            pkce = PKCEParameters.generate()
            state = secrets.token_urlsafe(32)
            store.remember_evidence({"secret": [pkce.code_verifier, state]})
            async with OAuthCallback(state=state, issuer=binding.issuer,
                                     require_iss=discovery.authorization_response_iss_required,
                                     authorization_origin=oauth_origin(discovery.authorization_endpoint),
                                     evidence=evidence, authorize=guard) as callback:
                url = _authorization_url(discovery, redirect_uri=callback.redirect_uri, state=state,
                                         code_challenge=pkce.code_challenge, scopes=scopes)
                guard()
                await browser_opener(url)
                code = await callback.wait_code()
                store.remember_evidence({"secret": code.code})
                fields = {"grant_type": "authorization_code", "client_id": binding.client_id, "resource": binding.resource,
                          "code": code.code, "code_verifier": pkce.code_verifier, "redirect_uri": callback.redirect_uri}
                if scopes:
                    fields["scope"] = " ".join(scopes)
                return await _token_request(store, claim, endpoint=discovery.token_endpoint, fields=fields, scopes=scopes,
                                            authorize=guard, clock=clock, attempt=attempt)
    except BaseException as error:
        _failed_claim(store, claim, attempt, error)
        if isinstance(error, OAuthError) or not isinstance(error, Exception):
            raise
        raise OAuthError("OAuth login failed or exceeded its deadline; no automatic retry") from None


async def refresh_oauth(
    store: OAuthCredentialStore, authority: OAuthAuthority, *, authorize: Callable[[], None],
    evidence: EvidenceRedactor, clock: Callable[[], float] = time.time,
) -> OAuthAuthority:
    """Use a persisted refresh claim exactly once, without discovery or browser fallback."""
    claim = None
    attempt = _Attempt()
    try:
        with http_diagnostics(), anyio.fail_after(OAUTH_TOKEN_TIMEOUT):
            store.register_evidence(evidence)
            authorize()
            store.check_authority(authority)
            claim = store.begin_refresh(authority)
            if claim.token_endpoint is None or claim.refresh_token is None:
                raise OAuthError("OAuth refresh claim lacks its bound endpoint or credential")
            fields = {"grant_type": "refresh_token", "client_id": authority.binding.client_id,
                      "resource": authority.binding.resource, "refresh_token": claim.refresh_token}
            if claim.previous_scopes:
                fields["scope"] = " ".join(claim.previous_scopes)
            return await _token_request(store, claim, endpoint=claim.token_endpoint, fields=fields,
                                        scopes=claim.previous_scopes, authorize=authorize, clock=clock, attempt=attempt)
    except BaseException as error:
        _failed_claim(store, claim, attempt, error)
        if isinstance(error, OAuthError) or not isinstance(error, Exception):
            raise
        raise OAuthError("OAuth refresh failed or exceeded its deadline; outcome may be unknown; no automatic retry") from None
