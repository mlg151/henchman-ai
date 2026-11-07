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
