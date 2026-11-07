"""Validated session overlays on a retained startup settings snapshot."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ValidationError

from henchman.config.key_paths import flatten_key_paths
from henchman.config.schema import Settings
from henchman.config.settings import ConfigError, SettingOrigin, SettingsSnapshot, deep_merge


@dataclass(frozen=True)
class _PreparedSettings:
    owner: RuntimeSettingsState
    revision: int
    snapshot: SettingsSnapshot


def _validated_settings(values: dict[str, Any]) -> Settings:
    try:
        return Settings.model_validate(values)
    except ValidationError as exc:
        path = ".".join(str(part) for part in exc.errors()[0]["loc"])
        # Validation input can contain credentials; never embed it in an error.
        raise ConfigError(f"Invalid setting '{path}' in session overrides") from None


def _copy_model_values(target: BaseModel, source: BaseModel) -> None:
    """Keep models already held by runtime consumers alive during a commit."""
    for name in type(source).model_fields:
        value, previous = getattr(source, name), getattr(target, name)
        if isinstance(value, BaseModel) and isinstance(previous, BaseModel):
            _copy_model_values(previous, value)
        elif isinstance(value, dict) and isinstance(previous, dict):
            previous.clear()
            previous.update(deepcopy(value))
        else:
            setattr(target, name, deepcopy(value))
    target.__pydantic_fields_set__.update(source.model_fields_set)


class RuntimeSettingsState:
    """Own live settings and origins without reloading or writing file scopes.

    Runtime consumers retain ``settings`` and its nested model identities. Reads
    return detached snapshots; callers can validate an overlay before applying
    provider/context side effects, then commit synchronously after success.
    """

    def __init__(self, snapshot: SettingsSnapshot) -> None:
        self.settings = snapshot.settings
        self._origins = {
            path: snapshot.origins.get(path, SettingOrigin("default"))
            for path in flatten_key_paths(self.settings.model_dump())
        }
        self._revision = 0

    @classmethod
    def from_settings(cls, settings: Settings) -> RuntimeSettingsState:
        """Treat explicitly supplied values as session input, never guessed files."""
        _validated_settings(settings.model_dump())
        supplied = set(flatten_key_paths(settings.model_dump(exclude_unset=True)))
        origins = {
            path: SettingOrigin("session" if path in supplied else "default")
            for path in flatten_key_paths(settings.model_dump())
        }
        return cls(SettingsSnapshot(settings, origins))

    def snapshot(self) -> SettingsSnapshot:
        """Return values and origins from the same live revision."""
        return SettingsSnapshot(self.settings.model_copy(deep=True), dict(self._origins))

    def prepare(
        self, overrides: Mapping[str, Any], *, origin: SettingOrigin | None = None,
    ) -> _PreparedSettings:
        """Validate an overlay without mutating any live runtime object."""
        overlay = deepcopy(dict(overrides))
        settings = _validated_settings(deep_merge(self.settings.model_dump(), overlay))
        origins = dict(self._origins)
        for path in flatten_key_paths(overlay):
            origins[path] = origin or SettingOrigin("session")
        origins = {
            path: origins.get(path, SettingOrigin("default"))
            for path in flatten_key_paths(settings.model_dump())
        }
        return _PreparedSettings(self, self._revision, SettingsSnapshot(settings, origins))

    def commit(self, prepared: _PreparedSettings) -> None:
        """Commit a prepared change once; reject another state's or stale work."""
        if prepared.owner is not self or prepared.revision != self._revision:
            raise ValueError("Cannot commit a stale settings update")
        values = _validated_settings(prepared.snapshot.settings.model_dump())
        _copy_model_values(self.settings, values)
        self._origins = dict(prepared.snapshot.origins)
        self._revision += 1

    def update(
        self, overrides: Mapping[str, Any], *, origin: SettingOrigin | None = None,
    ) -> None:
        """Validate and commit a synchronous settings-only change."""
        self.commit(self.prepare(overrides, origin=origin))


def runtime_settings_state(runtime: Any) -> RuntimeSettingsState:
    """Reuse a runtime's state, including older callers that inject only Settings."""
    state = getattr(runtime, "settings_state", None)
    if isinstance(state, RuntimeSettingsState):
        return state
    settings = getattr(runtime, "settings", None)
    if settings is None:
        settings = getattr(getattr(runtime, "orchestrator", None), "settings", None)
    state = RuntimeSettingsState.from_settings(settings if isinstance(settings, Settings) else Settings())
    runtime.settings_state = state
    runtime.settings = state.settings
    return state
