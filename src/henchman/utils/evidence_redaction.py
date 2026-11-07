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
_AUTH_NAMES = ("authorization", "proxy-authorization", "cookie", "set-cookie")
_STREAM_AUTH = re.compile(r"(?:authorization|proxy-authorization|cookie|set-cookie)[^\S\r\n]*:", re.I)
_MAX_HEADER_PREFIX = 1024


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


class EvidenceStreamRedactor:
    """Mask credentials across chunks while immediately releasing safe text.

    A possible credential prefix is held until it can be resolved. Closing a
    stream masks an unresolved prefix, including on cancellation. Header values
    are discarded as they arrive; they cannot grow the pending text buffer.
    Instances belong to one logical content/thought channel, sharing a policy.
    """

    def __init__(self, redactor: EvidenceRedactor) -> None:
        self.redactor = redactor
        self._pending = ""
        self._line_start = True
        self._header_value = False

    def feed(self, text: str) -> str:
        """Return the safe prefix of newly received text without changing it."""
        self._pending += text
        return self._drain(final=False, interrupted=False)

    def finish(self, *, interrupted: bool = True) -> str:
        """Flush safely at an actual stream boundary, including interruption."""
        result = self._drain(final=True, interrupted=interrupted)
        self._line_start = True
        self._header_value = False
        return result

    def _drain(self, *, final: bool, interrupted: bool) -> str:
        self.redactor.register_environment()
        secrets = sorted(self.redactor._secrets, key=len, reverse=True)
        tokens = [*secrets, REDACTED]
        output: list[str] = []
        value = self._pending
        position = 0
        special = re.compile("[" + re.escape("\r\n[" + "".join(secret[0] for secret in secrets)) + "]")

        def consume(length: int) -> None:
            nonlocal position
            part = value[position:position + length]
            last_newline = max(part.rfind("\r"), part.rfind("\n"))
            if last_newline >= 0:
                self._line_start = not part[last_newline + 1:].strip()
            elif self._line_start and part.strip():
                self._line_start = False
            position += length

        def is_prefix(token: str, start: int) -> bool:
            # Copy only a bounded candidate suffix, never the remaining large
            # output on every character. This keeps scanning linear in length.
            return len(value) - start < len(token) and token.startswith(value[start:])

        while position < len(value):
            if self._header_value:
                newline = re.compile(r"[\r\n]").search(value, position)
                position = newline.start() if newline else len(value)
                if newline is None:
                    break
                self._header_value = False
                continue
            # A complete shorter secret must wait if a longer one is still
            # possible, otherwise its remainder could be published separately.
            possible = any(is_prefix(token, position) for token in tokens)
            if possible and not final:
                break
            if self._line_start:
                header = _STREAM_AUTH.match(value, position)
                if header is not None:
                    safe_header = self.redactor._text(header[0])
                    output.append(safe_header if safe_header.endswith(REDACTED) else safe_header + " " + REDACTED)
                    consume(header.end() - position)
                    self._header_value = True
                    continue
                possible_header = any(
                    name.startswith(value[position:].lower())
                    if len(value) - position <= len(name) else (
                        value[position:position + len(name)].lower() == name
                        and re.fullmatch(r"[^\S\r\n]+", value[position + len(name):]) is not None
                    )
                    for name in _AUTH_NAMES
                )
                if not final and possible_header:
                    if len(value) - position > _MAX_HEADER_PREFIX:
                        # An unbounded pre-colon whitespace stream must not
                        # grow retained output or force repeated full rescans.
                        # Conservatively mask this overlong candidate line.
                        output.append(REDACTED)
                        consume(len(value) - position)
                        self._header_value = True
                        continue
                    break
            matched = next((secret for secret in secrets if value.startswith(secret, position)), None)
            if value.startswith(REDACTED, position) and (matched is None or len(matched) <= len(REDACTED)):
                crossings = [
                    (offset, value.startswith(secret, position + offset))
                    for offset in range(1, len(REDACTED)) for secret in secrets
                    if (
                        len(secret) > len(REDACTED) - offset
                        and (value.startswith(secret, position + offset) or is_prefix(secret, position + offset))
                    )
                ]
                complete = next((offset for offset, found in crossings if found), None)
                if complete is not None:
                    output.append(value[position:position + complete])
                    consume(complete)
                    continue
                if crossings:
                    if not final:
                        break
                    if interrupted:
                        output.append(value[position:position + crossings[0][0]] + REDACTED)
                        consume(len(value) - position)
                        continue
                output.append(REDACTED)
                consume(len(REDACTED))
                continue
            if matched is not None:
                output.append(REDACTED)
                consume(len(matched))
                continue
            if interrupted and any(is_prefix(secret, position) for secret in secrets):
                output.append(REDACTED)
                consume(len(value) - position)
                continue
            # At line starts, consume whitespace separately so header names
            # following indentation are still recognized. Otherwise batch text
            # up to the next possible credential/marker/newline boundary.
            if value[position] in "\r\n" or (self._line_start and value[position].isspace()):
                end = position + 1
            else:
                next_special = special.search(value, position + 1)
                end = next_special.start() if next_special else len(value)
            output.append(value[position:end])
            consume(end - position)
        self._pending = value[position:]
        return "".join(output)
