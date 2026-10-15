import normalization


def unique_labels(values: list[str]) -> list[str]:
    """Return nonempty canonical labels once each, in first-seen order."""
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = normalization.normalize_label(value)
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return result
