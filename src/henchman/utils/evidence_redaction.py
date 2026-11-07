"""Redact known credentials and explicitly credential-bearing evidence fields.

This is an output policy, not arbitrary secret detection or execution isolation.
Keep executable arguments separate from the returned evidence projection.
"""

from __future__ import annotations

import json
import os
import re
from bisect import bisect_right
from collections.abc import Iterable, Mapping
from typing import Any

REDACTED = "[REDACTED]"
PRESERVE_IDENTITY = object()
"""Trusted serializer schema marker for protocol identities, never evidence text."""
_CREDENTIAL_FIELDS = frozenset({
    "api_key", "api_keys", "authorization", "proxy_authorization", "cookie", "set_cookie",
    "password", "passwd", "passphrase", "private_key", "secret", "token",
})
_AUTH_LINE = re.compile(
    r"(?im)^(\s*(?:authorization|proxy-authorization|cookie|set-cookie)\s*:)\s*[^\r\n]*"
)
_REFERENCE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def _credential_field(name: str) -> bool:
    normalized = name.lower().replace("-", "_")
    return normalized in _CREDENTIAL_FIELDS or normalized.endswith(
        ("_api_key", "_access_key", "_private_key", "_secret", "_password", "_token")
    )


class EvidenceRedactor:
    """Runtime-scoped credentials retained across rotation for stale evidence."""

    def __init__(self, secrets: Iterable[str] = ()) -> None:
        self._secrets: set[str] = set()
        self._environment_references: set[str] = set()
        self._pattern: re.Pattern[str] | None = None
        for secret in secrets:
            self.register_secret(secret)

    def register_secret(self, value: str) -> None:
        """Mark an exact nonempty value sensitive, including JSON-escaped echoes."""
        if not value or value == REDACTED:
            return
        variants = {
            value,
            json.dumps(value, ensure_ascii=True)[1:-1],
            json.dumps(value, ensure_ascii=False)[1:-1],
        }
        if variants - self._secrets:
            self._secrets.update(variants)
            self._pattern = None

    def register_config(self, value: Any) -> None:
        """Collect named credentials without retaining or mutating configuration."""
        if isinstance(value, Mapping):
            for key, nested in value.items():
                if _credential_field(str(key)):
                    self._register_credential(nested)
                else:
                    self.register_config(nested)
        elif isinstance(value, (list, tuple)):
            for nested in value:
                self.register_config(nested)

    def _register_credential(self, value: Any) -> None:
        if isinstance(value, str):
            reference = _REFERENCE.fullmatch(value)
            if reference:
                self._environment_references.add(reference.group(1))
                self.register_secret(os.environ.get(reference.group(1), ""))
            else:
                self.register_secret(value)
                parts = value.split(maxsplit=1)
                if len(parts) == 2 and parts[0].lower() in {"bearer", "basic"}:
                    self.register_secret(parts[1].strip())
        elif isinstance(value, (list, tuple)):
            for nested in value:
                self._register_credential(nested)
        else:
            self.register_config(value)

    def register_environment(self) -> None:
        """Refresh credential-named environment values without forgetting old ones."""
        self.register_config(os.environ)
        for name in self._environment_references:
            self.register_secret(os.environ.get(name, ""))

    def text(self, value: str) -> str:
        """Mask exact known values and complete standard authentication header lines."""
        self.register_environment()
        return self._text(value)

    def _text(self, value: str) -> str:
        if self._secrets:
            if self._pattern is None:
                alternatives = sorted(self._secrets, key=len, reverse=True)
                self._pattern = re.compile("|".join(re.escape(secret) for secret in alternatives))
            markers = [match.span() for match in re.finditer(re.escape(REDACTED), value)]
            marker_starts = [start for start, _ in markers]

            def replacement(match: re.Match[str]) -> str:
                # Existing placeholders are stable, but a credential spanning
                # their boundaries must still be matched as one complete value.
                marker_index = bisect_right(marker_starts, match.start()) - 1
                if marker_index >= 0 and match.end() <= markers[marker_index][1]:
                    return match[0]
                return REDACTED

            value = self._pattern.sub(replacement, value)
        return _AUTH_LINE.sub(lambda match: f"{match[1]} {REDACTED}", value)

    def redact(self, value: Any, *, schema: Any = None) -> Any:
        """Project evidence; a trusted schema protects field names and identities."""
        self.register_environment()
        # Collect first so echoes before their marked field are also masked.
        self.register_config(value)
        return self._project(value, schema)

    def _project(self, value: Any, schema: Any = None) -> Any:
        if schema is PRESERVE_IDENTITY:
            if value is None or isinstance(value, (str, int, float, bool)):
                return value
            if isinstance(value, (list, tuple)):
                return [self._project(item, PRESERVE_IDENTITY) for item in value]
            raise ValueError("Protocol identity must contain only scalar values")
        if isinstance(value, str):
            return self._text(value)
        if isinstance(value, Mapping):
            fields = schema if isinstance(schema, Mapping) else {}
            return {
                str(key) if key in fields else self._text(str(key)):
                self._project(nested, fields[key]) if key in fields else (
                    REDACTED if _credential_field(str(key)) and isinstance(nested, str) and nested
                    else self._project(nested)
                )
                for key, nested in value.items()
            }
        if isinstance(value, (list, tuple)):
            item_schema = schema[0] if isinstance(schema, list) and len(schema) == 1 else None
            return [self._project(nested, item_schema) for nested in value]
        return value
