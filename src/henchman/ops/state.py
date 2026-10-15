"""App-state selectors built on the Tier 8 operations store."""

from __future__ import annotations

from typing import Any

from henchman.ops.store import OpsStore


class AppStateStore:
    """Typed helpers for application-level state persisted in the ops store."""

    def __init__(self, *, store: OpsStore) -> None:
        """Initialize the state store.

        Args:
            store: Shared operations store instance.
        """
        self._store = store

    def set(self, key: str, value: Any) -> None:
        """Persist a state value.

        Args:
            key: Dotted state key.
            value: JSON-serializable value.
        """
        self._store.put_state(key, value)

    def get(self, key: str, default: Any | None = None) -> Any | None:
        """Load one state value.

        Args:
            key: Dotted state key.
            default: Fallback value when the key is missing.

        Returns:
            Persisted value or the provided default.
        """
        return self._store.get_state(key, default)

    def select(self, *, prefix: str | None = None) -> dict[str, Any]:
        """Select state values by key prefix.

        Args:
            prefix: Optional dotted key prefix.

        Returns:
            Mapping of matching keys to values.
        """
        return self._store.select_state(prefix)
