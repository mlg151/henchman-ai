"""Validate explicit MCP HTTP destinations without resolving or contacting them."""

from __future__ import annotations

import ipaddress
from urllib.parse import urlsplit


def validate_mcp_endpoint(value: str) -> str:
    """Require HTTPS, or a literal loopback HTTP address, without URL credentials."""
    diagnostic = "MCP HTTP endpoint must be an absolute HTTPS URL or literal loopback HTTP URL without credentials/query/fragment"
    if (not value or len(value) > 4096 or any(character.isspace() or ord(character) < 32 for character in value)
        or any(character in value for character in ("\\", "?", "#"))):
        raise ValueError(diagnostic)
    try:
        parsed = urlsplit(value)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError:
        raise ValueError(diagnostic) from None
    if (parsed.scheme not in {"http", "https"} or not hostname or parsed.username is not None
        or parsed.password is not None or "%" in parsed.netloc or port == 0):
        raise ValueError(diagnostic)
    if parsed.scheme == "http":
        try:
            loopback = ipaddress.ip_address(hostname).is_loopback
        except ValueError:
            loopback = False
        if not loopback:
            raise ValueError(diagnostic)
    return value


def validate_oauth_url(value: str, *, allow_query: bool = False) -> str:
    """Validate an explicit HTTPS OAuth destination without normalizing its issuer."""
    diagnostic = "OAuth requires an absolute HTTPS URL without credentials or fragments"
    if (not value or len(value) > 4096 or not value.isascii()
        or any(character.isspace() or ord(character) < 32 or ord(character) == 127 for character in value)
        or "\\" in value or "#" in value or (not allow_query and "?" in value)):
        raise ValueError(diagnostic)
    try:
        parsed = urlsplit(value)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username is not None
            or parsed.password is not None or "%" in parsed.netloc or parsed.port == 0):
            raise ValueError(diagnostic)
    except ValueError:
        raise ValueError(diagnostic) from None
    return value


def oauth_origin(value: str) -> str:
    """Return a comparison origin; never use this to compare issuer identifiers."""
    parsed = urlsplit(value)
    host = parsed.hostname or ""
    if ":" in host:
        host = f"[{host}]"
    port = parsed.port
    suffix = f":{port}" if port is not None and port != (443 if parsed.scheme == "https" else 80) else ""
    return f"{parsed.scheme}://{host}{suffix}"


def validate_oauth_origin(value: str) -> str:
    """Require an exact additional HTTPS authority, with no path or query."""
    validate_oauth_url(value)
    if urlsplit(value).path not in {"", "/"}:
        raise ValueError("OAuth endpoint origins must not contain a path")
    return oauth_origin(value)


def canonical_oauth_resource(value: str) -> str:
    """Normalize only URI authority, retaining a resource's significant path."""
    import httpx2

    validate_mcp_endpoint(value)
    if not value.isascii():
        raise ValueError("OAuth resource URI encoding is unsupported")
    path = urlsplit(value).path
    resource = oauth_origin(value) + path
    try:
        # HTTPX removes literal dot segments before dispatch. Refuse to derive
        # authority from a lexical path that differs from the actual wire path.
        if httpx2.URL(resource).raw_path.decode("ascii") != (path or "/"):
            raise ValueError
    except (httpx2.InvalidURL, ValueError):
        raise ValueError("OAuth resource path must not change during HTTP transport normalization") from None
    return resource
