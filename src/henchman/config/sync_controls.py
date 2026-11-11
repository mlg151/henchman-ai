"""Explicit, lossless transfer of nonsecret operational settings.

These mappings carry configuration only: they cannot supply policy grants,
accounting/journal state, verification observations, or import acceptance.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from pydantic import BaseModel, ValidationError

from henchman.config.schema import OperationSettings, UsageSettings, VerificationSettings
from henchman.utils.evidence_redaction import PRESERVE_IDENTITY, EvidenceRedactor

CONTROL_GROUPS = frozenset({"usage", "operations", "verification"})
_MODELS: dict[str, type[BaseModel]] = {
    "usage": UsageSettings,
    "operations": OperationSettings,
    "verification": VerificationSettings,
}
# This schema is applied only after typed validation. Freeform labels and
# executable check arguments are evidence, never preserved protocol identities.
_CONTROL_SCHEMA = {
    "usage": {
        "persistence": PRESERVE_IDENTITY,
        "limits": dict.fromkeys(
            ("max_requests", "max_tokens", "max_seconds", "max_cost", "currency"),
            PRESERVE_IDENTITY,
        ),
        "prices": [
            {
                "provider": None,
                "model": None,
                "source": None,
                **dict.fromkeys(
                    (
                        "input_per_1k",
                        "output_per_1k",
                        "cache_read_per_1k",
                        "cache_write_per_1k",
                        "currency",
                        "as_of",
                    ),
                    PRESERVE_IDENTITY,
                ),
            }
        ],
    },
    "operations": {"persistence": PRESERVE_IDENTITY},
    "verification": {
        "checks": [
            {
                "kind": PRESERVE_IDENTITY,
                "path": None,
                "text": None,
                "argv": None,
                "inputs": None,
                "requirement_ids": None,
                "expected_exit": None,
                "timeout": None,
            }
        ]
    },
}


def normalize_controls(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Validate selected controls without inserting omitted defaults or evidence."""
    result: dict[str, Any] = {}
    for group, model in _MODELS.items():
        if group not in payload:
            continue
        value = payload[group]
        if not isinstance(value, Mapping):
            raise ValueError(f"Sync payload field '{group}' must be a mapping")
        try:
            validated = model.model_validate(deepcopy(dict(value)))
        except ValidationError:
            # Model errors can quote arbitrary argv, model identities or input
            # values. The group is fixed; no untrusted value enters this error.
            raise ValueError(f"Sync payload field '{group}' failed schema validation") from None
        result[group] = validated.model_dump(mode="python", exclude_unset=True)
    return result


def project_control_evidence(
    payload: Mapping[str, Any],
    *,
    redactor: EvidenceRedactor,
) -> dict[str, Any]:
    """Project validated control values for display without granting execution."""
    controls = normalize_controls(payload)
    projected: dict[str, Any] = redactor.redact(controls, schema=_CONTROL_SCHEMA)
    return projected


def require_nonsecret_controls(
    payload: Mapping[str, Any],
    *,
    redactor: EvidenceRedactor,
) -> dict[str, Any]:
    """Reject the whole transfer when redaction would change operational meaning."""
    controls = normalize_controls(payload)
    if project_control_evidence(controls, redactor=redactor) != controls:
        raise ValueError("Sync payload contains credential-bearing operational controls")
    return controls


def merge_controls(target: dict[str, Any], controls: Mapping[str, Any]) -> None:
    """Merge supplied mapping leaves; supplied lists replace complete old lists."""
    for key, value in controls.items():
        if isinstance(value, Mapping):
            existing = target.get(key)
            if not isinstance(existing, dict):
                existing = {}
                target[key] = existing
            merge_controls(existing, value)
        else:
            target[key] = deepcopy(value)
