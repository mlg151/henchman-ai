"""Label indexing with deduplication and normalization."""

from __future__ import annotations

import normalization


def unique_labels(values: list[str]) -> list[str]:
    """Return nonempty canonical labels once each, in first-seen order."""
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = normalization.normalize_label(value)
        if normalized and normalized not in seen:
            result.append(normalized)
            seen.add(normalized)
    return result
