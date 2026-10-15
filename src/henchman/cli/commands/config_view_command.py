"""Click command factories for read-only config inspection."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import click
import yaml

from henchman.cli.commands.config_redaction import redact_config_value_for_display
from henchman.config.repository import SettingsRepository, SettingsScope

_DEFAULT_SCOPE_LABEL: Final[str] = "default"
_SCOPE_CHOICES: Final[tuple[str, ...]] = tuple(scope.value for scope in SettingsScope)
_MISSING_KEY_ERROR_CODE: Final[str] = "HMN_CFG_KEY_NOT_FOUND"
_MISSING_KEY_ERROR_MESSAGE: Final[str] = "Requested configuration key was not found."


@dataclass(frozen=True)
class ConfigValuePayload:
    """Structured result for a single config value lookup."""

    key: str
    value: Any
    requested_scope: str
    resolved_scope: str

    def as_mapping(self) -> dict[str, Any]:
        """Return the payload as a serializer-friendly mapping."""
        return {
            "key": self.key,
            "value": self.value,
            "requested_scope": self.requested_scope,
            "resolved_scope": self.resolved_scope,
        }


@dataclass(frozen=True)
class ConfigListEntry:
    """Structured metadata for a listed config key."""

    key: str
    resolved_scope: str

    def as_mapping(self) -> dict[str, str]:
        """Return the entry as a serializer-friendly mapping."""
        return {
            "key": self.key,
            "resolved_scope": self.resolved_scope,
        }


@dataclass(frozen=True)
class ConfigListPayload:
    """Structured result for listing config keys."""

    requested_scope: str
    entries: tuple[ConfigListEntry, ...]

    def as_mapping(self) -> dict[str, Any]:
        """Return the payload as a serializer-friendly mapping."""
        return {
            "requested_scope": self.requested_scope,
            "entries": [entry.as_mapping() for entry in self.entries],
        }


def create_config_view_command(*, project_root: Path | None = None) -> click.Command:
    """Create the click command for ``config view``."""
    return _create_read_command(
        name="view",
        help_text="Read a config value using the shared merged settings rules.",
        project_root=project_root,
    )


def create_config_get_command(*, project_root: Path | None = None) -> click.Command:
    """Create the click command for ``config get``."""
    return _create_read_command(
        name="get",
        help_text="Alias for config view.",
        project_root=project_root,
    )


def create_config_list_command(*, project_root: Path | None = None) -> click.Command:
    """Create the click command for ``config list``."""

    @click.command(name="list", help="List config keys for a selected scope.")
    @click.option(
        "--scope",
        "scope_value",
        type=click.Choice(_SCOPE_CHOICES, case_sensitive=False),
        default=SettingsScope.MERGED.value,
        show_default=True,
        help="Select which settings scope to read.",
    )
    def list_command(scope_value: str) -> None:
        repository = SettingsRepository(project_root=project_root)
        requested_scope = SettingsScope(scope_value)
        payload = _build_list_payload(repository=repository, scope=requested_scope)
        click.echo(_format_payload(payload.as_mapping()), nl=False)

    return list_command


def _create_read_command(
    *,
    name: str,
    help_text: str,
    project_root: Path | None,
) -> click.Command:
    """Create a click command for reading one config key."""

    @click.command(name=name, help=help_text)
    @click.argument("key_path")
    @click.option(
        "--scope",
        "scope_value",
        type=click.Choice(_SCOPE_CHOICES, case_sensitive=False),
        default=SettingsScope.MERGED.value,
        show_default=True,
        help="Select which settings scope to read.",
    )
    def read_command(key_path: str, scope_value: str) -> None:
        repository = SettingsRepository(project_root=project_root)
        requested_scope = SettingsScope(scope_value)
        payload = _build_value_payload(
            repository=repository,
            key_path=key_path,
            scope=requested_scope,
        )
        click.echo(_format_payload(payload.as_mapping()), nl=False)

    return read_command


def _build_value_payload(
    *,
    repository: SettingsRepository,
    key_path: str,
    scope: SettingsScope,
) -> ConfigValuePayload:
    """Build a structured payload for a single config key lookup."""
    available_keys = _list_keys(repository, scope=scope)
    if key_path not in available_keys:
        raise _missing_key_exception(key_path=key_path, scope=scope)

    value = repository.get(key_path, scope=scope)
    return ConfigValuePayload(
        key=key_path,
        value=redact_config_value_for_display(key_path=key_path, value=value),
        requested_scope=scope.value,
        resolved_scope=_resolve_scope_label(repository=repository, key_path=key_path, scope=scope),
    )


def _build_list_payload(
    *,
    repository: SettingsRepository,
    scope: SettingsScope,
) -> ConfigListPayload:
    """Build a structured payload for listing config keys."""
    entries = tuple(
        ConfigListEntry(
            key=key_path,
            resolved_scope=_resolve_scope_label(repository=repository, key_path=key_path, scope=scope),
        )
        for key_path in _list_keys(repository, scope=scope)
    )
    return ConfigListPayload(requested_scope=scope.value, entries=entries)


def _resolve_scope_label(
    *,
    repository: SettingsRepository,
    key_path: str,
    scope: SettingsScope,
) -> str:
    """Resolve the active source label for a config key."""
    if scope is SettingsScope.GLOBAL:
        return SettingsScope.GLOBAL.value
    if scope is SettingsScope.PROJECT:
        return SettingsScope.PROJECT.value
    if key_path in _list_keys(repository, scope=SettingsScope.PROJECT):
        return SettingsScope.PROJECT.value
    if key_path in _list_keys(repository, scope=SettingsScope.GLOBAL):
        return SettingsScope.GLOBAL.value
    return _DEFAULT_SCOPE_LABEL


def _list_keys(repository: SettingsRepository, *, scope: SettingsScope) -> tuple[str, ...]:
    """Return a stable key listing for one repository scope."""
    return tuple(repository.list(scope=scope))


def _missing_key_exception(*, key_path: str, scope: SettingsScope) -> click.ClickException:
    """Build the PRD-aligned missing-key failure for config reads."""
    msg = (
        f"{_MISSING_KEY_ERROR_CODE}: {_MISSING_KEY_ERROR_MESSAGE} "
        f"Missing key '{key_path}' in {scope.value} settings."
    )
    return click.ClickException(msg)


def _format_payload(payload: dict[str, Any]) -> str:
    """Serialize a command payload as deterministic YAML text."""
    return yaml.safe_dump(payload, sort_keys=False)


__all__ = [
    "ConfigListEntry",
    "ConfigListPayload",
    "ConfigValuePayload",
    "create_config_get_command",
    "create_config_list_command",
    "create_config_view_command",
]
