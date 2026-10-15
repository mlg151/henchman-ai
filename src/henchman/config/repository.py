"""Repository helpers for persisted Henchman settings."""

from __future__ import annotations

import json
from collections.abc import Mapping
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml

from henchman.config import load_settings
from henchman.config.paths import (
    resolve_legacy_project_settings_path,
    resolve_project_settings_path,
)
from henchman.config.schema import Settings

_SETTINGS_FILENAME = "settings.yaml"
_SUPPORTED_SETTINGS_FILENAMES = ("settings.yaml", "settings.yml", "settings.json")
_USER_SETTINGS_DIRNAME = ".henchman"
_SYNC_UI_KEYS = ("output_style", "theme", "keybindings")
_MISSING = object()


class SettingsScope(StrEnum):
    """Supported settings scopes for Tier 1 repository operations."""

    GLOBAL = "global"
    PROJECT = "project"
    MERGED = "merged"


class SettingsRepository:
    """Read and write validated Henchman settings by key path."""

    def __init__(self, project_root: Path | None = None) -> None:
        """Initialize the repository for a project workspace.

        Args:
            project_root: Optional project root used for project-local settings.
                When omitted, the current working directory is used.
        """
        self._project_root = project_root

    def view(self, *, scope: SettingsScope = SettingsScope.MERGED) -> dict[str, Any]:
        """Return settings for a selected scope.

        Args:
            scope: Which scope to read.

        Returns:
            A settings mapping for the requested scope. Merged reads include
            defaults plus user and project overlays; explicit scopes return only
            persisted values from that scope.
        """
        if scope is SettingsScope.MERGED:
            return load_settings(project_root=self._project_root).model_dump(mode="python")
        if scope is SettingsScope.GLOBAL:
            return _clone_mapping(self._read_settings_directory(self._user_settings_directory()))
        if scope is SettingsScope.PROJECT:
            return _clone_mapping(self._read_project_settings())
        msg = f"Unsupported settings scope: {scope}"
        raise ValueError(msg)

    def list(self, *, scope: SettingsScope = SettingsScope.MERGED) -> list[str]:
        """List flattened key paths available within a selected scope.

        Args:
            scope: Which scope to inspect.

        Returns:
            Sorted dotted key paths for leaf values in the selected scope.
        """
        return sorted(_flatten_key_paths(self.view(scope=scope)))

    def get(self, key_path: str, *, scope: SettingsScope = SettingsScope.MERGED) -> Any | None:
        """Return a setting value for a dotted key path.

        Args:
            key_path: Dotted key path such as ``ui.theme``.
            scope: Which scope to read.

        Returns:
            The resolved value for the key path, or ``None`` when the key is not
            present in the selected scope.
        """
        value = _get_key_path(self.view(scope=scope), key_path)
        return None if value is _MISSING else value

    def set(self, key_path: str, value: Any, *, scope: SettingsScope) -> None:
        """Persist a setting value to an explicit scope after validation.

        Args:
            key_path: Dotted key path such as ``ui.output_style``.
            value: Value to store at the key path.
            scope: Explicit global or project scope to update.

        Raises:
            ValueError: If the scope is merged, the key path is invalid, or the
                resulting settings document fails schema validation.
        """
        target_scope = _require_write_scope(scope)
        candidate = self.view(scope=target_scope)
        _set_key_path(candidate, key_path, value)
        self._write_scope_settings(target_scope, candidate)

    def unset(self, key_path: str, *, scope: SettingsScope) -> bool:
        """Remove a persisted setting value from an explicit scope.

        Args:
            key_path: Dotted key path such as ``ui.theme``.
            scope: Explicit global or project scope to update.

        Returns:
            ``True`` when a persisted value was removed; otherwise ``False``.

        Raises:
            ValueError: If the scope is merged or the key path is invalid.
        """
        target_scope = _require_write_scope(scope)
        candidate = self.view(scope=target_scope)
        removed = _unset_key_path(candidate, key_path)
        if not removed:
            return False
        self._write_scope_settings(target_scope, candidate)
        return True

    def export_settings(self, *, scope: SettingsScope = SettingsScope.MERGED) -> dict[str, Any]:
        """Export the Tier 1 local-sync settings payload for a selected scope."""
        return _build_sync_payload(self.view(scope=scope))

    def import_settings(self, payload: Mapping[str, Any], *, scope: SettingsScope) -> None:
        """Import a Tier 1 local-sync payload into an explicit persisted scope."""
        candidate = self.view(scope=_require_write_scope(scope))
        _merge_sync_payload(candidate, _normalize_sync_payload(payload))
        self._write_scope_settings(scope, candidate)

    def sync_ui_settings(
        self,
        *,
        output_style: str | None = None,
        theme: str | None = None,
        keybindings: Mapping[str, str] | None = None,
        scope: SettingsScope,
    ) -> None:
        """Persist Tier 1 UI sync values with one validated repository write."""
        sync_payload: dict[str, Any] = {}
        if output_style is not None:
            sync_payload["output_style"] = output_style
        if theme is not None:
            sync_payload["theme"] = theme
        if keybindings is not None:
            sync_payload["keybindings"] = dict(keybindings)
        self.import_settings({"ui": sync_payload}, scope=scope)

    def _read_project_settings(self) -> dict[str, Any]:
        """Return persisted project settings with legacy fallback for reads."""
        canonical_directory = resolve_project_settings_path(self._project_root)
        if canonical_directory.exists():
            return self._read_settings_directory(canonical_directory)

        legacy_directory = resolve_legacy_project_settings_path(self._project_root)
        if legacy_directory is None:
            return {}
        return self._read_settings_directory(legacy_directory)

    def _write_scope_settings(self, scope: SettingsScope, payload: dict[str, Any]) -> None:
        """Validate and persist a scope document."""
        validated_payload = Settings.model_validate(payload).model_dump(
            mode="python",
            exclude_defaults=True,
        )
        serialized_payload = _prune_empty_mappings(validated_payload)
        settings_directory = self._settings_directory_for_scope(scope)
        settings_directory.mkdir(parents=True, exist_ok=True)
        settings_file = settings_directory / _SETTINGS_FILENAME
        if not serialized_payload:
            if settings_file.exists():
                settings_file.unlink()
            return

        yaml_text = yaml.safe_dump(serialized_payload, sort_keys=True)
        temporary_file = settings_file.with_name(f"{settings_file.name}.tmp")
        temporary_file.write_text(yaml_text, encoding="utf-8")
        temporary_file.replace(settings_file)

    def _settings_directory_for_scope(self, scope: SettingsScope) -> Path:
        """Return the canonical directory used for writes in a scope."""
        if scope is SettingsScope.GLOBAL:
            return self._user_settings_directory()
        if scope is SettingsScope.PROJECT:
            return resolve_project_settings_path(self._project_root)
        msg = f"Unsupported write scope: {scope}"
        raise ValueError(msg)

    def _user_settings_directory(self) -> Path:
        """Return the canonical user-scoped settings directory."""
        return Path.home() / _USER_SETTINGS_DIRNAME

    def _read_settings_directory(self, settings_directory: Path) -> dict[str, Any]:
        """Read the first supported settings file from a directory."""
        settings_file = _resolve_settings_file(settings_directory)
        if settings_file is None:
            return {}
        return _read_settings_file(settings_file)


def _require_write_scope(scope: SettingsScope) -> SettingsScope:
    """Validate that a mutation targets an explicit persisted scope."""
    if scope is SettingsScope.MERGED:
        msg = "Writes require an explicit global or project scope"
        raise ValueError(msg)
    return scope


def _build_sync_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Extract the Tier 1 local-sync payload shape from a settings mapping."""
    ui_value = payload.get("ui")
    if not isinstance(ui_value, Mapping):
        return {}

    exported_ui: dict[str, Any] = {}
    for key in _SYNC_UI_KEYS:
        if key not in ui_value:
            continue
        value = ui_value[key]
        if isinstance(value, Mapping):
            exported_ui[key] = _clone_mapping(value)
            continue
        exported_ui[key] = value
    if not exported_ui:
        return {}
    return {"ui": exported_ui}


def _normalize_sync_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and normalize an imported Tier 1 local-sync payload."""
    unsupported_top_level_keys = sorted(set(payload) - {"ui"})
    if unsupported_top_level_keys:
        unsupported = ", ".join(unsupported_top_level_keys)
        msg = f"Unsupported sync payload keys: {unsupported}"
        raise ValueError(msg)

    ui_value = payload.get("ui")
    if ui_value is None:
        return {}
    if not isinstance(ui_value, Mapping):
        msg = "Sync payload field 'ui' must be a mapping"
        raise ValueError(msg)

    unsupported_ui_keys = sorted(set(ui_value) - set(_SYNC_UI_KEYS))
    if unsupported_ui_keys:
        unsupported = ", ".join(unsupported_ui_keys)
        msg = f"Unsupported sync payload ui keys: {unsupported}"
        raise ValueError(msg)

    normalized_ui: dict[str, Any] = {}
    for key in _SYNC_UI_KEYS:
        if key not in ui_value:
            continue
        value = ui_value[key]
        if isinstance(value, Mapping):
            normalized_ui[key] = _clone_mapping(value)
            continue
        normalized_ui[key] = value
    if not normalized_ui:
        return {}
    return {"ui": normalized_ui}


def _merge_sync_payload(target: dict[str, Any], sync_payload: Mapping[str, Any]) -> None:
    """Apply a normalized local-sync payload onto a persisted settings document."""
    ui_value = sync_payload.get("ui")
    if not isinstance(ui_value, Mapping):
        return

    target_ui: dict[str, Any]
    existing_ui = target.get("ui")
    if isinstance(existing_ui, dict):
        target_ui = existing_ui
    else:
        target_ui = {}
        target["ui"] = target_ui

    for key, value in ui_value.items():
        if isinstance(value, Mapping):
            target_ui[key] = _clone_mapping(value)
            continue
        target_ui[key] = value


def _read_settings_file(settings_file: Path) -> dict[str, Any]:
    """Parse a JSON or YAML settings file into a mapping."""
    raw_text = settings_file.read_text(encoding="utf-8")
    parsed: Any
    if settings_file.suffix == ".json":
        parsed = json.loads(raw_text) if raw_text.strip() else {}
    else:
        parsed = yaml.safe_load(raw_text) if raw_text.strip() else {}

    if parsed is None:
        return {}
    if not isinstance(parsed, dict):
        msg = f"Settings file must contain a mapping: {settings_file}"
        raise ValueError(msg)
    return parsed


def _resolve_settings_file(settings_directory: Path) -> Path | None:
    """Return the first supported settings file within a settings directory."""
    for filename in _SUPPORTED_SETTINGS_FILENAMES:
        candidate = settings_directory / filename
        if candidate.is_file():
            return candidate
    return None


def _get_key_path(payload: Mapping[str, Any], key_path: str) -> Any:
    """Resolve a dotted key path from a mapping."""
    path_segments = _parse_key_path(key_path)
    current: Any = payload
    for segment in path_segments:
        if not isinstance(current, Mapping) or segment not in current:
            return _MISSING
        current = current[segment]
    return current


def _set_key_path(payload: dict[str, Any], key_path: str, value: Any) -> None:
    """Assign a dotted key path inside a mutable mapping."""
    path_segments = _parse_key_path(key_path)
    current = payload
    for segment in path_segments[:-1]:
        next_value = current.get(segment)
        if next_value is None:
            nested_value: dict[str, Any] = {}
            current[segment] = nested_value
            current = nested_value
            continue
        if not isinstance(next_value, dict):
            msg = f"Cannot set nested key beneath non-mapping path: {key_path}"
            raise ValueError(msg)
        current = next_value
    current[path_segments[-1]] = value


def _unset_key_path(payload: dict[str, Any], key_path: str) -> bool:
    """Remove a dotted key path from a mutable mapping."""
    path_segments = _parse_key_path(key_path)
    stack: list[tuple[dict[str, Any], str]] = []
    current = payload
    for segment in path_segments[:-1]:
        next_value = current.get(segment)
        if not isinstance(next_value, dict):
            return False
        stack.append((current, segment))
        current = next_value

    leaf = path_segments[-1]
    if leaf not in current:
        return False
    del current[leaf]

    while stack and not current:
        parent, segment = stack.pop()
        del parent[segment]
        current = parent
    return True


def _parse_key_path(key_path: str) -> list[str]:
    """Split and validate a dotted key path."""
    path_segments = [segment.strip() for segment in key_path.split(".")]
    if not key_path.strip() or any(not segment for segment in path_segments):
        msg = f"Invalid key path: {key_path!r}"
        raise ValueError(msg)
    return path_segments


def _flatten_key_paths(payload: Mapping[str, Any], prefix: str = "") -> list[str]:
    """Return dotted key paths for each leaf in a nested mapping."""
    key_paths: list[str] = []
    for key, value in payload.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, Mapping) and value:
            key_paths.extend(_flatten_key_paths(value, path))
            continue
        key_paths.append(path)
    return key_paths


def _clone_mapping(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Return a deep-enough copy for nested dictionary payloads."""
    cloned: dict[str, Any] = {}
    for key, value in payload.items():
        if isinstance(value, Mapping):
            cloned[key] = _clone_mapping(value)
            continue
        cloned[key] = value
    return cloned


def _prune_empty_mappings(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Remove empty nested mappings from a serialized settings payload."""
    pruned: dict[str, Any] = {}
    for key, value in payload.items():
        if isinstance(value, Mapping):
            nested_value = _prune_empty_mappings(value)
            if nested_value:
                pruned[key] = nested_value
            continue
        pruned[key] = value
    return pruned
