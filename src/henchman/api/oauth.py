"""Minimal OAuth primitives for remote Tier 8 integrations."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode
from uuid import uuid4

from henchman.ops.store import OpsStore


@dataclass(frozen=True, slots=True)
class AuthorizationRequest:
    """An authorization request payload returned to a client."""

    state: str
    client_id: str
    redirect_uri: str
    scopes: tuple[str, ...]
    authorization_url: str


@dataclass(frozen=True, slots=True)
class AccessToken:
    """A simple bearer-token response."""

    access_token: str
    token_type: str
    client_id: str
    scopes: tuple[str, ...]


class OAuthService:
    """Persist and exchange minimal OAuth authorization state."""

    def __init__(
        self,
        *,
        store: OpsStore | None = None,
        issuer: str = "https://henchman.local",
        state_factory: Callable[[], str] | None = None,
        token_factory: Callable[[], str] | None = None,
    ) -> None:
        """Initialize the OAuth service.

        Args:
            store: Optional operations store for persisted request state.
            issuer: Issuer string included in metadata.
            state_factory: Optional test hook for state generation.
            token_factory: Optional test hook for token generation.
        """
        self._store = store
        self._issuer = issuer.rstrip("/")
        self._state_factory = state_factory or (lambda: uuid4().hex)
        self._token_factory = token_factory or (lambda: uuid4().hex)
        self._pending: dict[str, dict[str, Any]] = {}

    def create_authorization_request(
        self,
        *,
        client_id: str,
        redirect_uri: str,
        scopes: Sequence[str],
    ) -> AuthorizationRequest:
        """Create and persist a pending authorization request.

        Args:
            client_id: Remote client identifier.
            redirect_uri: Redirect URI that will receive the state token.
            scopes: Requested scopes.

        Returns:
            Authorization request metadata for the client.
        """
        state = self._state_factory()
        normalized_scopes = tuple(scopes)
        payload = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scopes": list(normalized_scopes),
            "issuer": self._issuer,
        }
        self._persist(state, payload)

        query = urlencode(
            {
                "state": state,
                "client_id": client_id,
                "scope": " ".join(normalized_scopes),
                "issuer": self._issuer,
            }
        )
        authorization_url = f"{redirect_uri}?{query}"
        return AuthorizationRequest(
            state=state,
            client_id=client_id,
            redirect_uri=redirect_uri,
            scopes=normalized_scopes,
            authorization_url=authorization_url,
        )

    def exchange_code(self, *, client_id: str, state: str, code: str) -> AccessToken:
        """Exchange an authorization code for a bearer token.

        Args:
            client_id: Remote client identifier.
            state: Previously issued authorization state.
            code: Authorization code returned by the client.

        Returns:
            Bearer token metadata.

        Raises:
            ValueError: If the state is unknown, mismatched, or the code is blank.
        """
        if not code.strip():
            msg = "OAuth code must not be blank"
            raise ValueError(msg)

        pending_request = self._load(state)
        if pending_request is None:
            msg = "Unknown OAuth state"
            raise ValueError(msg)
        if pending_request.get("client_id") != client_id:
            msg = "OAuth client mismatch"
            raise ValueError(msg)

        token_value = self._token_factory()
        pending_request["code"] = code
        pending_request["access_token"] = token_value
        self._persist(state, pending_request)
        scopes = tuple(str(scope) for scope in pending_request.get("scopes", []))
        return AccessToken(
            access_token=token_value,
            token_type="bearer",
            client_id=client_id,
            scopes=scopes,
        )

    def _persist(self, state: str, payload: dict[str, Any]) -> None:
        """Persist a pending authorization request."""
        if self._store is not None:
            self._store.put_oauth_request(state, payload)
            return
        self._pending[state] = dict(payload)

    def _load(self, state: str) -> dict[str, Any] | None:
        """Load a pending authorization request."""
        if self._store is not None:
            return self._store.get_oauth_request(state)
        payload = self._pending.get(state)
        return dict(payload) if payload is not None else None
