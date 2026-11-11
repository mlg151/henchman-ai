"""Resolve one runtime's shared display and persistence credential policy."""

from __future__ import annotations

from typing import Any

from henchman.utils.evidence_redaction import EvidenceRedactor
from henchman.utils.exception_evidence import exception_text


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
    return exception_text(error, policy, include_traceback=include_traceback)
