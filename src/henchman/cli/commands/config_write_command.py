"""Click command factories for config mutations and local sync files."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final

import click
import yaml
from pydantic import ValidationError

from henchman.cli.commands.config_redaction import (
    is_secret_like_key_path,
    redact_config_mapping_for_display,
)
from henchman.config.repository import SettingsRepository, SettingsScope

_WRITE_SCOPE_CHOICES: Final[tuple[str, ...]] = (
    SettingsScope.GLOBAL.value,
    SettingsScope.PROJECT.value,
)
_OUTPUT_FORMATS: Final[tuple[str, ...]] = ("text", "json")
_SYNC_FILE_FORMATS: Final[dict[str, str]] = {
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
}
_REDACTED_VALUE: Final[str] = "<redacted>"
_PRD_FAILURE_MESSAGES: Final[dict[str, str]] = {
    "HMN_CFG_INVALID_VALUE": "Configuration value failed schema validation.",
    "HMN_CFG_KEY_NOT_FOUND": "Requested configuration key was not found.",
    "HMN_SYNC_FILE_INVALID": "Settings import file is invalid or incompatible with the current schema.",
}


def create_config_set_command(*, project_root: Path | None = None) -> click.Command:
    """Create the click command for ``config set``.

    Args:
        project_root: Optional project root used to resolve project-local settings.

    Returns:
        A click command that persists one config key to an explicit scope.
    """

    @click.command(name="set", help="Persist one config key to an explicit scope.")
    @click.argument("key_path")
    @click.argument("raw_value")
    @click.option(
        "--scope",
        "scope_value",
        type=click.Choice(_WRITE_SCOPE_CHOICES, case_sensitive=False),
        required=True,
        help="Select which persisted scope to update.",
    )
    @click.option(
        "--format",
        "output_format",
        type=click.Choice(_OUTPUT_FORMATS, case_sensitive=False),
        default="text",
        show_default=True,
        help="Render the result as text or JSON.",
    )
    def set_command(key_path: str, raw_value: str, scope_value: str, output_format: str) -> None:
        repository = SettingsRepository(project_root=project_root)
        scope = SettingsScope(scope_value)
        try:
            parsed_value = _parse_cli_value(raw_value)
        except (TypeError, ValueError, yaml.YAMLError, ValidationError) as error:
            _raise_prd_failure("HMN_CFG_INVALID_VALUE", error)
        try:
            repository.set(key_path, parsed_value, scope=scope)
        except (TypeError, ValueError, ValidationError) as error:
            _raise_prd_failure("HMN_CFG_INVALID_VALUE", error)

        payload = {
            "operation": "set",
            "key": key_path,
            "value": parsed_value,
            "scope": scope.value,
        }
        click.echo(_render_payload(payload, output_format=output_format), nl=False)

    return set_command


def create_config_unset_command(*, project_root: Path | None = None) -> click.Command:
    """Create the click command for ``config unset``.

    Args:
        project_root: Optional project root used to resolve project-local settings.

    Returns:
        A click command that removes one config key from an explicit scope.
    """

    @click.command(name="unset", help="Remove one config key from an explicit scope.")
    @click.argument("key_path")
    @click.option(
        "--scope",
        "scope_value",
        type=click.Choice(_WRITE_SCOPE_CHOICES, case_sensitive=False),
        required=True,
        help="Select which persisted scope to update.",
    )
    @click.option(
        "--format",
        "output_format",
        type=click.Choice(_OUTPUT_FORMATS, case_sensitive=False),
        default="text",
        show_default=True,
        help="Render the result as text or JSON.",
    )
    def unset_command(key_path: str, scope_value: str, output_format: str) -> None:
        repository = SettingsRepository(project_root=project_root)
        scope = SettingsScope(scope_value)
        try:
            removed = repository.unset(key_path, scope=scope)
        except ValueError as error:
            raise click.ClickException(str(error)) from error
        if not removed:
            message = (
                "HMN_CFG_KEY_NOT_FOUND: Requested configuration key was not found. "
                f"Missing key '{key_path}' in {scope.value} settings."
            )
            raise click.ClickException(message)

        payload = {
            "operation": "unset",
            "key": key_path,
            "removed": removed,
            "scope": scope.value,
        }
        click.echo(_render_payload(payload, output_format=output_format), nl=False)

    return unset_command


def create_config_import_command(*, project_root: Path | None = None) -> click.Command:
    """Create the click command for ``config import``.

    Args:
        project_root: Optional project root used to resolve project-local settings.

    Returns:
        A click command that imports a local sync file into an explicit scope.
    """

    @click.command(name="import", help="Import a local config sync file into one scope.")
    @click.argument(
        "source_path",
        type=click.Path(exists=True, dir_okay=False, path_type=Path),
    )
    @click.option(
        "--scope",
        "scope_value",
        type=click.Choice(_WRITE_SCOPE_CHOICES, case_sensitive=False),
        required=True,
        help="Select which persisted scope to update.",
    )
    @click.option(
        "--format",
        "output_format",
        type=click.Choice(_OUTPUT_FORMATS, case_sensitive=False),
        default="text",
        show_default=True,
        help="Render the result as text or JSON.",
    )
    def import_command(source_path: Path, scope_value: str, output_format: str) -> None:
        repository = SettingsRepository(project_root=project_root)
        scope = SettingsScope(scope_value)
        try:
            payload = _read_serialized_payload(source_path)
        except (TypeError, ValueError, json.JSONDecodeError, yaml.YAMLError) as error:
            _raise_prd_failure("HMN_SYNC_FILE_INVALID", error)
        try:
            repository.import_settings(payload, scope=scope)
        except (TypeError, ValueError, ValidationError) as error:
            failure_code = (
                "HMN_SYNC_FILE_INVALID"
                if _is_sync_payload_error(error)
                else "HMN_CFG_INVALID_VALUE"
            )
            _raise_prd_failure(failure_code, error)

        output_payload = {
            "operation": "import",
            "path": str(source_path),
            "scope": scope.value,
            "payload": payload,
        }
        click.echo(_render_payload(output_payload, output_format=output_format), nl=False)

    return import_command


def create_config_export_command(*, project_root: Path | None = None) -> click.Command:
    """Create the click command for ``config export``.

    Args:
        project_root: Optional project root used to resolve project-local settings.

    Returns:
        A click command that exports a local sync payload to a local file.
    """

    @click.command(name="export", help="Export one scope to a local config sync file.")
    @click.argument(
        "destination_path",
        type=click.Path(dir_okay=False, path_type=Path),
    )
    @click.option(
        "--scope",
        "scope_value",
        type=click.Choice(_WRITE_SCOPE_CHOICES, case_sensitive=False),
        required=True,
        help="Select which persisted scope to export.",
    )
    @click.option(
        "--format",
        "output_format",
        type=click.Choice(_OUTPUT_FORMATS, case_sensitive=False),
        default="text",
        show_default=True,
        help="Render the result as text or JSON.",
    )
    def export_command(destination_path: Path, scope_value: str, output_format: str) -> None:
        repository = SettingsRepository(project_root=project_root)
        scope = SettingsScope(scope_value)
        payload = repository.export_settings(scope=scope)
        try:
            _write_serialized_payload(destination_path, payload)
        except ValueError as error:
            _raise_prd_failure("HMN_SYNC_FILE_INVALID", error)

        output_payload = {
            "operation": "export",
            "path": str(destination_path),
            "scope": scope.value,
            "payload": payload,
        }
        click.echo(_render_payload(output_payload, output_format=output_format), nl=False)

    return export_command


def _parse_cli_value(raw_value: str) -> Any:
    """Parse a CLI value using YAML scalar and collection rules."""
    if raw_value == "":
        return ""
    return yaml.safe_load(raw_value)


def _render_payload(payload: dict[str, Any], *, output_format: str) -> str:
    """Render a command payload in either JSON or human-readable YAML."""
    if output_format == "json":
        return json.dumps(payload, sort_keys=True)
    return yaml.safe_dump(_redact_command_payload(payload), sort_keys=False)


def _raise_prd_failure(code: str, error: BaseException) -> None:
    """Raise a user-facing click failure tagged with a PRD error code."""
    summary = _PRD_FAILURE_MESSAGES[code]
    detail = _summarize_user_facing_error(error)
    message = f"{code}: {summary}"
    if detail:
        message = f"{message} {detail}"
    raise click.ClickException(message) from error


def _summarize_user_facing_error(error: BaseException) -> str:
    """Return a concise error detail suitable for CLI display."""
    if isinstance(error, ValidationError):
        messages = [
            str(message).removeprefix("Value error, ")
            for message in (
                entry.get("msg")
                for entry in error.errors()
                if isinstance(entry.get("msg"), str)
            )
        ]
        return "; ".join(dict.fromkeys(message for message in messages if message))
    return str(error).strip()


def _is_sync_payload_error(error: BaseException) -> bool:
    """Return whether an import failure was caused by the sync file payload shape."""
    message = _summarize_user_facing_error(error)
    return message.startswith(
        (
            "Unsupported sync payload keys:",
            "Unsupported sync payload ui keys:",
            "Sync payload field 'ui' must be a mapping",
            "Config payload must contain a mapping:",
            "Unsupported config sync file format ",
        )
    )


def _read_serialized_payload(path: Path) -> dict[str, Any]:
    """Read a local import payload from JSON or YAML."""
    raw_text = path.read_text(encoding="utf-8")
    serialization_format = _serialization_format_for_path(path)
    parsed: Any
    if serialization_format == "json":
        parsed = json.loads(raw_text) if raw_text.strip() else {}
    else:
        parsed = yaml.safe_load(raw_text) if raw_text.strip() else {}
    if parsed is None:
        return {}
    if not isinstance(parsed, dict):
        msg = f"Config payload must contain a mapping: {path}"
        raise ValueError(msg)
    return parsed


def _write_serialized_payload(path: Path, payload: Mapping[str, Any]) -> None:
    """Write a local export payload as YAML or JSON."""
    serialization_format = _serialization_format_for_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized_payload = (
        json.dumps(dict(payload), sort_keys=False, indent=2) + "\n"
        if serialization_format == "json"
        else yaml.safe_dump(dict(payload), sort_keys=False)
    )
    path.write_text(serialized_payload, encoding="utf-8")


def _serialization_format_for_path(path: Path) -> str:
    """Return the supported sync serialization format for a file path."""
    try:
        return _SYNC_FILE_FORMATS[path.suffix.lower()]
    except KeyError as error:
        msg = (
            "Unsupported config sync file format "
            f"for {path}: expected one of .json, .yaml, .yml"
        )
        raise ValueError(msg) from error


def _redact_command_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Return a human-readable payload with secret-like values redacted."""
    redacted = dict(payload)
    operation = redacted.get("operation")
    key_path = redacted.get("key")
    if operation == "set" and isinstance(key_path, str) and is_secret_like_key_path(key_path):
        redacted["value"] = _REDACTED_VALUE
    if operation in {"import", "export"}:
        raw_payload = redacted.get("payload")
        if isinstance(raw_payload, Mapping):
            redacted["payload"] = redact_config_mapping_for_display(raw_payload)
    return redacted


__all__ = [
    "create_config_export_command",
    "create_config_import_command",
    "create_config_set_command",
    "create_config_unset_command",
]
