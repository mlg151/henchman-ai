"""Credential-safe exception snapshots shared by runtime and frontend diagnostics."""

from __future__ import annotations

import traceback

from henchman.utils.evidence_redaction import EvidenceRedactor


def exception_text(
    error: BaseException, policy: EvidenceRedactor, *, include_traceback: bool = False,
) -> str:
    """Project messages, notes and chains before formatting; never capture locals."""
    snapshot = traceback.TracebackException.from_exception(error, capture_locals=False)
    pending = [snapshot]
    snapshots: list[tuple[traceback.TracebackException, list[str]]] = []
    visited = set()
    while pending:
        current = pending.pop()
        if id(current) in visited:
            continue
        visited.add(id(current))
        notes = getattr(current, "__notes__", None)
        note_values = notes if isinstance(notes, (list, tuple)) else (() if notes is None else (notes,))
        snapshots.append((current, [str(note) for note in note_values]))
        pending.extend(item for item in (current.__cause__, current.__context__) if item is not None)
        pending.extend(current.exceptions or ())
    # Explicit header values are credentials, including when repeated in a
    # source-code line. Ordinary exception text must never become a secret.
    for current, notes in snapshots:
        for value in (current._str, getattr(current, "msg", ""), *notes):  # type: ignore[attr-defined]
            for line in str(value).splitlines():
                name, separator, content = line.partition(":")
                if separator and name.strip().lower() in (
                    "authorization", "proxy-authorization", "cookie", "set-cookie",
                ):
                    policy.register_config({name.strip(): content.strip()})
    for current, notes in snapshots:
        current._str = policy.text(current._str)  # type: ignore[attr-defined]
        if getattr(current, "msg", None) is not None:
            current.msg = policy.text(str(current.msg))
        if getattr(current, "__notes__", None) is not None:
            current.__notes__ = [policy.text(note) for note in notes]
    lines = snapshot.format() if include_traceback else snapshot.format_exception_only()
    return policy.text("".join(lines).rstrip())
