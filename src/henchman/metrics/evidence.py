"""Evidence copies for metric persistence and exports; execution stays separate."""

from __future__ import annotations

import json
from dataclasses import fields
from typing import Any

from henchman.metrics.models import (
    BaseMetric,
    CostMetric,
    PerformanceMetric,
    TokenMetric,
    ToolMetric,
    UsageMetric,
)
from henchman.utils.evidence_redaction import PRESERVE_IDENTITY, EvidenceRedactor

_IDENTITIES = {"id", "timestamp", "metric_type", "session_id", "agent_id", "user_id"}
METRIC_SCHEMA = {
    field.name: PRESERVE_IDENTITY if field.name in _IDENTITIES else None
    for kind in (BaseMetric, TokenMetric, CostMetric, ToolMetric, UsageMetric, PerformanceMetric)
    for field in fields(kind)
}


def project_metrics(rows: list[dict[str, Any]], policy: EvidenceRedactor) -> list[dict[str, Any]]:
    """Collect marked credentials across the result before projecting any row.

    Keep the storage API's serialized metadata shape. Malformed legacy metadata
    fails explicitly rather than exporting unparsed credential-bearing content.
    """
    unpacked = []
    serialized = []
    for row in rows:
        item = dict(row)
        metadata = item.get("metadata")
        serialized.append(isinstance(metadata, str))
        if isinstance(metadata, str):
            try:
                item["metadata"] = json.loads(metadata)
            except (ValueError, RecursionError):
                raise ValueError("Stored metric metadata is invalid") from None
        unpacked.append(item)
    projected: list[dict[str, Any]] = policy.redact(unpacked, schema=[METRIC_SCHEMA])
    for item, was_serialized in zip(projected, serialized, strict=True):
        if was_serialized:
            item["metadata"] = json.dumps(item["metadata"])
    return projected


def project_summary(value: Any, policy: EvidenceRedactor) -> Any:
    """Project trusted aggregate shapes while preserving their structural keys."""
    def schema(item: Any) -> Any:
        if isinstance(item, dict):
            return {key: PRESERVE_IDENTITY if key in _IDENTITIES else schema(nested)
                    for key, nested in item.items()}
        if isinstance(item, list) and item:
            return [schema(item[0])]
        return None

    return policy.redact(value, schema=schema(value))
