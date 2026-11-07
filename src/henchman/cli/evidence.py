"""Resolve one runtime's shared display and persistence credential policy."""

from __future__ import annotations

import traceback
from typing import Any

from henchman.utils.evidence_redaction import EvidenceRedactor


def runtime_evidence_redactor(runtime: Any) -> EvidenceRedactor:
    """Bind to session evidence, retaining a fallback for embedded renderers."""
    context = getattr(runtime, "core_context", None)
    policy = None
    for manager in (
        getattr(context, "session_manager", None), getattr(runtime, "session_manager", None),
    ):
        core_manager = getattr(manager, "session_manager", manager)
        candidate = getattr(core_manager, "evidence_redactor", None)
        if isinstance(candidate, EvidenceRedactor):
            policy = candidate
            break
    if not isinstance(policy, EvidenceRedactor):
        policy = getattr(runtime, "_evidence_redactor", None)
    if not isinstance(policy, EvidenceRedactor):
        policy = EvidenceRedactor()
        runtime._evidence_redactor = policy
    settings = getattr(runtime, "settings", None)
    dump = getattr(settings, "model_dump", None)
    if callable(dump):
        policy.register_config(dump())
    key = getattr(getattr(runtime, "provider", None), "api_key", None)
    if isinstance(key, str):
        policy.register_secret(key)
    for manager in (getattr(context, "mcp_manager", None), getattr(runtime, "mcp_manager", None)):
        register = getattr(manager, "register_evidence", None)
        if callable(register):
            register(policy)
    return policy


def runtime_exception_text(
    runtime: Any, error: BaseException, *, include_traceback: bool = False,
) -> str:
    """Project an exception for output without exposing its raw traceback to loggers.

    Project a traceback snapshot before formatting adds exception-name prefixes
    to authentication headers. Original messages, notes and chains stay intact.
    """
    policy = runtime_evidence_redactor(runtime)
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
