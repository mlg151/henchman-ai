"""Feature-flag helpers for Tier 8 runtime toggles."""

from __future__ import annotations

from collections.abc import Mapping

from henchman.ops.store import OpsStore

_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}


def _normalize_flag_name(name: str) -> str:
    """Normalize a feature-flag name to a stable identifier."""
    return name.strip().lower().replace("-", "_")


class FeatureFlagService:
    """Resolve feature flags from environment overrides and persisted state."""

    def __init__(
        self,
        *,
        store: OpsStore | None = None,
        env: Mapping[str, str] | None = None,
        defaults: Mapping[str, bool] | None = None,
    ) -> None:
        """Initialize the feature-flag service.

        Args:
            store: Optional operations store for persisted overrides.
            env: Optional environment mapping override.
            defaults: Default flag values.
        """
        self._store = store
        self._env = dict(env or {})
        self._defaults = {_normalize_flag_name(key): value for key, value in (defaults or {}).items()}

    def set_flag(self, name: str, enabled: bool, *, source: str = "runtime") -> None:
        """Persist a flag override.

        Args:
            name: Feature flag name.
            enabled: Enabled state.
            source: Metadata describing how the override was set.
        """
        if self._store is None:
            return
        self._store.set_feature_flag(_normalize_flag_name(name), enabled, source=source)

    def is_enabled(self, name: str) -> bool:
        """Return whether a feature flag is enabled.

        Args:
            name: Feature flag name.

        Returns:
            Resolved enabled state.
        """
        normalized_name = _normalize_flag_name(name)
        env_key = f"HENCHMAN_FLAG_{normalized_name.upper()}"
        env_value = self._env.get(env_key)
        if env_value is not None:
            lowered = env_value.strip().lower()
            if lowered in _TRUE_VALUES:
                return True
            if lowered in _FALSE_VALUES:
                return False

        if self._store is not None:
            stored = self._store.get_feature_flag(normalized_name)
            if stored is not None:
                return bool(stored["enabled"])

        return bool(self._defaults.get(normalized_name, False))
