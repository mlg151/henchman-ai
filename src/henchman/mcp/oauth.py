"""Explicit OAuth authority and bounded discovery; no login, token exchange or replay."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Callable
from dataclasses import asdict, dataclass
from http.cookiejar import CookieJar
from typing import Any
from urllib.parse import urlsplit

import anyio
import httpx2
from mcp.client.auth.utils import (
    build_oauth_authorization_server_metadata_discovery_urls,
    build_protected_resource_metadata_discovery_urls,
)

from henchman.config.mcp import canonical_oauth_resource, oauth_origin, validate_oauth_url
from henchman.config.schema import McpServerConfig
from henchman.mcp.diagnostics import http_diagnostics
from henchman.mcp.http_transport import _NoCookies

OAUTH_REQUEST_TIMEOUT = 10.0
OAUTH_DISCOVERY_TIMEOUT = 30.0
OAUTH_DOCUMENT_BYTES = 65536
OAUTH_HEADER_BYTES = 8192


class OAuthError(RuntimeError):
    """Value-free OAuth foundation diagnostic."""


@dataclass(frozen=True, repr=False)
class OAuthBinding:
    """Detached configured authority; issuer comparison always uses the original string."""

    server: str
    endpoint: str
    issuer: str
    resource: str
    client_id: str
    allowed_endpoint_origins: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        from henchman.config.schema import McpOAuthConfig

        try:
            validated = McpOAuthConfig(issuer=self.issuer, client_id=self.client_id, resource=self.resource,
                                      allowed_endpoint_origins=list(self.allowed_endpoint_origins))
            if (not isinstance(self.server, str) or not self.server or len(self.server) > 256
                or any(ord(char) < 32 for char in self.server)
                or not isinstance(self.allowed_endpoint_origins, tuple)
                or tuple(validated.allowed_endpoint_origins) != self.allowed_endpoint_origins):
                raise ValueError
            endpoint, resource = canonical_oauth_resource(self.endpoint), canonical_oauth_resource(self.resource)
            root_path, path = urlsplit(resource).path, urlsplit(endpoint).path
            if (endpoint != self.endpoint or resource != self.resource or oauth_origin(resource) != oauth_origin(endpoint)
                or (root_path and path != root_path and not path.startswith(root_path.rstrip("/") + "/"))):
                raise ValueError
        except (TypeError, ValueError):
            raise OAuthError("OAuth configured authority is invalid") from None

    @classmethod
    def from_config(cls, server: str, config: McpServerConfig) -> OAuthBinding:
        try:
            config = McpServerConfig.model_validate(config.model_dump())
            oauth = config.oauth
            if config.transport != "streamable_http" or config.url is None or oauth is None:
                raise ValueError
            if not server or len(server) > 256 or any(ord(char) < 32 for char in server):
                raise ValueError
            endpoint = canonical_oauth_resource(config.url)
            resource = oauth.resource or endpoint
            root_path = urlsplit(resource).path
            path = urlsplit(endpoint).path
            if (oauth_origin(resource) != oauth_origin(endpoint)
                or (root_path and path != root_path and not path.startswith(root_path.rstrip("/") + "/"))):
                raise ValueError
            return cls(server, endpoint, oauth.issuer, resource, oauth.client_id, tuple(oauth.allowed_endpoint_origins))
        except (TypeError, ValueError):
            raise OAuthError("OAuth configured authority is invalid") from None

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True, ensure_ascii=True).encode()).hexdigest()

    def check_destination(self, url: str, *, resource_metadata: bool = False) -> None:
        """Authorize a discovered destination before I/O; metadata never expands authority."""
        try:
            validate_oauth_url(url, allow_query=True)
            origins = {oauth_origin(self.issuer), *self.allowed_endpoint_origins}
            if resource_metadata:
                origins.add(oauth_origin(self.endpoint))
            if oauth_origin(url) not in origins:
                raise ValueError
        except ValueError:
            raise OAuthError("OAuth destination is not authorized by configured origins") from None


@dataclass(frozen=True, repr=False)
class OAuthChallenge:
    resource_metadata: str | None = None
    scopes: tuple[str, ...] | None = None


def _scopes(value: object) -> tuple[str, ...]:
    if (not isinstance(value, list) or len(value) > 128
        or any(not isinstance(item, str) or not item or len(item) > 256
               or any(not 33 <= ord(char) <= 126 or char in {'"', "\\"} for char in item) for item in value)):
        raise OAuthError("OAuth scope declaration is invalid")
    return tuple(dict.fromkeys(value))


def parse_oauth_challenge(header: str) -> OAuthChallenge:
    """Accept one bounded Bearer challenge, rejecting ambiguous or duplicate parameters."""
    if (len(header) > OAUTH_HEADER_BYTES or not header.isascii()
        or any(ord(char) < 32 or ord(char) == 127 for char in header)):
        raise OAuthError("OAuth challenge is invalid")
    scheme, separator, remainder = header.partition(" ")
    if scheme.lower() != "bearer" or not separator:
        raise OAuthError("OAuth challenge scheme is unsupported")
    fields: dict[str, str] = {}
    pattern = re.compile(r'\s*([A-Za-z][A-Za-z0-9_-]*)\s*=\s*(?:"((?:[^"\\]|\\[\x20-\x7e])*)"|([^\s,]+))\s*(,|$)')
    while remainder:
        match = pattern.match(remainder)
        if match is None or match.group(1).lower() in fields:
            raise OAuthError("OAuth challenge parameters are invalid")
        fields[match.group(1).lower()] = re.sub(r"\\(.)", r"\1", match.group(2)) if match.group(2) is not None else match.group(3)
        remainder = remainder[match.end():]
        if match.group(4) and not remainder.strip():
            raise OAuthError("OAuth challenge parameters are invalid")
    metadata = fields.get("resource_metadata")
    if metadata == "":
        raise OAuthError("OAuth challenge metadata URL is invalid")
    scopes = _scopes(fields["scope"].split(" ")) if "scope" in fields else None
    return OAuthChallenge(metadata, scopes)


def _object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError
        result[key] = value
    return result


def bounded_oauth_json(raw: bytes, *, limit: int = OAUTH_DOCUMENT_BYTES) -> dict[str, Any]:
    """Parse bounded JSON without leaking rejected values, duplicates or nonfinite numbers."""
    try:
        if len(raw) > limit:
            raise ValueError
        parsed = json.loads(raw, object_pairs_hook=_object_pairs, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        stack = [(parsed, 0)]
        nodes = 0
        while stack:
            value, depth = stack.pop()
            nodes += 1
            if depth > 16 or nodes > 4096:
                raise ValueError
            if isinstance(value, float) and not math.isfinite(value):
                raise ValueError
            if isinstance(value, dict):
                stack.extend((child, depth + 1) for child in value.values())
            elif isinstance(value, list):
                stack.extend((child, depth + 1) for child in value)
        if not isinstance(parsed, dict):
            raise ValueError
        return parsed
    except (ValueError, TypeError, RecursionError, UnicodeError):
        raise OAuthError("OAuth JSON document is invalid or exceeds its bounds") from None


@dataclass(frozen=True, repr=False)
class OAuthDiscovery:
    binding: OAuthBinding
    authorization_endpoint: str
    token_endpoint: str
    scopes: tuple[str, ...]
    authorization_response_iss_required: bool


async def discover_oauth(
    binding: OAuthBinding, *, authorize: Callable[[], None], challenge: str | None = None,
) -> OAuthDiscovery:
    """Discover one configured issuer without credentials, browser launch or mutating RPCs."""
    parsed_challenge = parse_oauth_challenge(challenge) if challenge is not None else OAuthChallenge()

    async def fetch(client: httpx2.AsyncClient, url: str, *, resource_metadata: bool = False) -> dict[str, Any] | None:
        binding.check_destination(url, resource_metadata=resource_metadata)
        with anyio.fail_after(OAUTH_REQUEST_TIMEOUT):
            request = client.build_request("GET", url, headers={"accept": "application/json", "accept-encoding": "identity"})
            if oauth_origin(str(request.url)) != oauth_origin(url):
                raise OAuthError("OAuth destination changed before dispatch")
            authorize()
            response = await client.send(request, stream=True, follow_redirects=False)
            try:
                if sum(len(key) + len(value) for key, value in response.headers.multi_items()) > OAUTH_HEADER_BYTES:
                    raise OAuthError("OAuth response headers exceed their bound")
                if response.status_code in (404, 405):
                    return None
                if response.status_code != 200:
                    raise OAuthError("OAuth metadata request was rejected; no redirect or retry")
                if (response.headers.get("content-encoding", "identity").lower() != "identity"
                    or response.headers.get("content-type", "").split(";")[0].strip().lower() != "application/json"):
                    raise OAuthError("OAuth metadata response encoding is unsupported")
                raw = bytearray()
                async for part in response.aiter_raw():
                    if len(raw) + len(part) > OAUTH_DOCUMENT_BYTES:
                        raise OAuthError("OAuth metadata exceeds its byte bound")
                    raw.extend(part)
                return bounded_oauth_json(bytes(raw))
            finally:
                await response.aclose()

    try:
        with http_diagnostics(), anyio.fail_after(OAUTH_DISCOVERY_TIMEOUT):
            async with httpx2.AsyncClient(trust_env=False, follow_redirects=False,
                                          cookies=CookieJar(policy=_NoCookies()), timeout=OAUTH_REQUEST_TIMEOUT) as client:
                urls = build_protected_resource_metadata_discovery_urls(parsed_challenge.resource_metadata, binding.endpoint)
                resource = None
                for url in dict.fromkeys(urls):
                    resource = await fetch(client, url, resource_metadata=True)
                    if resource is not None:
                        break
                if resource is None:
                    raise OAuthError("OAuth protected resource metadata is unavailable")
                if resource.get("resource") != binding.resource:
                    raise OAuthError("OAuth resource metadata does not match configured resource")
                issuers = resource.get("authorization_servers")
                if (not isinstance(issuers, list) or not 1 <= len(issuers) <= 32
                    or any(not isinstance(item, str) or len(item) > 4096 for item in issuers)
                    or binding.issuer not in issuers):
                    raise OAuthError("OAuth resource does not advertise the configured issuer")
                resource_scopes = _scopes(resource["scopes_supported"]) if "scopes_supported" in resource else ()
                metadata = None
                for url in build_oauth_authorization_server_metadata_discovery_urls(binding.issuer, binding.endpoint):
                    metadata = await fetch(client, url)
                    if metadata is not None:
                        break
                if metadata is None or metadata.get("issuer") != binding.issuer:
                    raise OAuthError("OAuth authorization metadata issuer does not match configured issuer")
                methods = metadata.get("code_challenge_methods_supported")
                if (not isinstance(methods, list) or len(methods) > 32 or "S256" not in methods
                    or any(not isinstance(method, str) or len(method) > 128 for method in methods)):
                    raise OAuthError("OAuth authorization server must advertise S256 PKCE support")
                for key, required in (("response_types_supported", "code"), ("grant_types_supported", "authorization_code"),
                                      ("token_endpoint_auth_methods_supported", "none")):
                    # An omitted auth-method list defaults to client_secret_basic, not public-client "none".
                    if key == "grant_types_supported" and key not in metadata:
                        continue
                    entries = metadata.get(key)
                    if (not isinstance(entries, list) or len(entries) > 32 or required not in entries
                        or any(not isinstance(entry, str) or len(entry) > 128 for entry in entries)):
                        raise OAuthError("OAuth authorization server does not support the public native-client profile")
                authorization_endpoint = metadata.get("authorization_endpoint")
                token_endpoint = metadata.get("token_endpoint")
                if not isinstance(authorization_endpoint, str) or not isinstance(token_endpoint, str):
                    raise OAuthError("OAuth authorization metadata lacks required endpoints")
                binding.check_destination(authorization_endpoint)
                binding.check_destination(token_endpoint)
                iss_required = metadata.get("authorization_response_iss_parameter_supported", False)
                if not isinstance(iss_required, bool):
                    raise OAuthError("OAuth issuer-response requirement is malformed")
                return OAuthDiscovery(binding, authorization_endpoint, token_endpoint,
                                      parsed_challenge.scopes if parsed_challenge.scopes is not None else resource_scopes,
                                      iss_required)
    except OAuthError:
        raise
    except Exception:
        raise OAuthError("OAuth discovery failed or exceeded its deadline") from None
