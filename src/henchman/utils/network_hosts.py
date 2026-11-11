"""Canonical exact HTTP authority names for trusted host restrictions."""

from __future__ import annotations

import ipaddress
import re
from collections.abc import Sequence

from yarl import URL

MAX_NETWORK_HOSTS = 128
_LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?")


def canonical_network_host(value: str) -> str:
    """Normalize an exact IDNA/DNS/IP name, rejecting URL and alias syntax."""
    if (not isinstance(value, str) or not value or len(value) > 1024 or value != value.strip()
        or any(ord(char) <= 32 or ord(char) == 127 or char in "/\\@?#%[]" for char in value)):
        raise ValueError("Network hosts must be exact DNS or IP names without URL syntax")
    try:
        return ipaddress.ip_address(value).compressed
    except ValueError:
        pass
    if ":" in value or value.endswith(".."):
        raise ValueError("Network hosts cannot contain ports or empty DNS labels")
    hostname = value.removesuffix(".")
    labels = hostname.split(".")
    if all(re.fullmatch(r"(?:[0-9]+|0[xX][0-9a-fA-F]+)", label) for label in labels):
        raise ValueError("Network IP literals must use canonical address syntax")
    try:
        parsed = URL.build(scheme="https", host=hostname)
        # Decode too: yarl's ASCII fast path can retain invalid A-labels.
        decoded = parsed.host
        canonical = parsed.raw_host
        if decoded is None or canonical is None or parsed.raw_authority != canonical:
            # IDNA normalization must never turn the host input into userinfo
            # or a port (for example full-width @ and colon characters).
            raise ValueError
    except (ValueError, UnicodeError):
        raise ValueError("Network host has invalid IDNA syntax") from None
    # UTS-46 can turn full-width digits/hex into legacy numeric address aliases.
    if all(re.fullmatch(r"(?:[0-9]+|0[xX][0-9a-fA-F]+)", label) for label in canonical.split(".")):
        raise ValueError("Network IP literals must use canonical address syntax")
    if len(canonical) > 253 or any(_LABEL.fullmatch(label) is None for label in canonical.split(".")):
        raise ValueError("Network host has invalid or oversized DNS labels")
    return canonical


def canonical_network_hosts(values: Sequence[str] | None) -> tuple[str, ...] | None:
    """Preserve null/empty meaning while bounding exact, distinct host entries."""
    if values is None:
        return None
    if isinstance(values, str | bytes) or len(values) > MAX_NETWORK_HOSTS:
        raise ValueError("Network host restrictions accept at most 128 exact names")
    result = tuple(canonical_network_host(value) for value in values)
    if len(set(result)) != len(result):
        raise ValueError("Network hosts must be distinct after normalization")
    return result
