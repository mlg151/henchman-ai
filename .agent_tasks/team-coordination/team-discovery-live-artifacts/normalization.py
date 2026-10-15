def normalize_label(value: str) -> str:
    """Canonical project labels: casefold and join whitespace with hyphens."""
    return "-".join(value.casefold().split())
