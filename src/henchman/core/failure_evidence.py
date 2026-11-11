"""Resolve retained diagnostic policy without loading or creating run authority."""

from __future__ import annotations

from typing import Any

from henchman.core.runtime_operations import current_operation_run
from henchman.utils.evidence_redaction import EvidenceRedactor


def failure_evidence_redactor(
    runtime: Any = None, *, redactor: EvidenceRedactor | None = None,
) -> EvidenceRedactor:
    """Capture known values before work and refresh them before diagnostic output."""
    policy = redactor
    if not isinstance(policy, EvidenceRedactor):
        policy = getattr(runtime, "_failure_evidence_redactor", None)
    if not isinstance(policy, EvidenceRedactor):
        policy = EvidenceRedactor()
        if runtime is not None:
            runtime._failure_evidence_redactor = policy
    # A supplied destination must retain credentials observed by earlier streams
    # or diagnostic owners, including values since rotated off a bound provider.
    # Visit only these existing objects: no recursive discovery or lazy agents.
    for source in (runtime, getattr(runtime, "provider", None),
                   getattr(runtime, "default_provider", None)):
        for name in ("_failure_evidence_redactor", "evidence_redactor", "_evidence_redactor", "_budget_evidence_redactor"):
            candidate = getattr(source, name, None)
            if isinstance(candidate, EvidenceRedactor):
                policy.register_policy(candidate)
        key = getattr(source, "api_key", None)
        if isinstance(key, str):
            policy.register_secret(key)
    settings = getattr(runtime, "settings", None)
    dump = getattr(settings, "model_dump", None)
    if callable(dump):
        policy.register_config(dump())
    run = current_operation_run()
    session_policy = getattr(getattr(run, "session", None), "evidence_redactor", None)
    if isinstance(session_policy, EvidenceRedactor):
        policy.register_policy(session_policy)
    policy.register_environment()
    return policy
