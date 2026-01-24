"""Settings loading and file discovery.

This module handles loading settings from YAML/JSON files and environment
variables with hierarchical merging.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from henchman.config.schema import Settings


class ConfigError(Exception):
    """Error loading or parsing configuration."""


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Deep merge two dictionaries.

    Values from override take precedence. Nested dicts are merged recursively.
    Does not mutate input dictionaries.

    Args:
        base: Base dictionary.
        override: Dictionary with overriding values.

    Returns:
        New merged dictionary.
    """
    result = base.copy()
    for key, value in override.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def discover_settings_files() -> list[Path]:
    """Discover settings files in order of precedence.

    Searches for settings.yaml or settings.json in:
    1. ~/.henchman/ (user settings)
    2. .henchman/ (workspace settings)

    Returns:
        List of paths to settings files, ordered by precedence (user first).
    """
    files: list[Path] = []

    # User settings
    user_dir = Path.home() / ".henchman"
    if user_dir.exists():
        for name in ("settings.yaml", "settings.yml", "settings.json"):
            path = user_dir / name
            if path.exists():
                files.append(path)
                break

    # Workspace settings
    workspace_dir = Path.cwd() / ".henchman"
    if workspace_dir.exists():
        for name in ("settings.yaml", "settings.yml", "settings.json"):
            path = workspace_dir / name
            if path.exists():
                files.append(path)
                break

    return files


def _load_file(path: Path) -> dict[str, Any]:
    """Load a settings file (YAML or JSON).

    Args:
        path: Path to the settings file.

    Returns:
        Parsed settings dictionary.

    Raises:
        ConfigError: If the file cannot be parsed.
    """
    content = path.read_text()
    try:
        data: dict[str, Any] = (
            yaml.safe_load(content)
            if path.suffix in (".yaml", ".yml")
            else json.loads(content)
        )
        return data if data else {}
    except (yaml.YAMLError, json.JSONDecodeError) as e:
        raise ConfigError(f"Failed to parse {path}: {e}") from e


def _apply_env_overrides(settings: dict[str, Any]) -> dict[str, Any]:
    """Apply environment variable overrides to settings.

    Supported environment variables:
    - HENCHMAN_PROVIDER: Override default provider
    - HENCHMAN_MODEL: Override model for default provider

    Args:
        settings: Current settings dictionary.

    Returns:
        Settings with environment overrides applied.
    """
    result = settings.copy()

    if provider := os.environ.get("HENCHMAN_PROVIDER"):
        result.setdefault("providers", {})["default"] = provider

    if model := os.environ.get("HENCHMAN_MODEL"):
        providers = result.setdefault("providers", {})
        default = providers.get("default", "deepseek")
        providers.setdefault(default, {})["model"] = model

    return result


def load_settings() -> Settings:
    """Load settings with hierarchical merging.

    Precedence (later overrides earlier):
    1. Defaults (from Settings model)
    2. User settings (~/.henchman/settings.yaml)
    3. Workspace settings (.henchman/settings.yaml)
    4. Environment variables (HENCHMAN_PROVIDER, HENCHMAN_MODEL)

    Returns:
        Merged Settings object.

    Raises:
        ConfigError: If settings files are invalid.
    """
    merged: dict[str, Any] = {}

    # Load and merge files in order
    for path in discover_settings_files():
        try:
            file_settings = _load_file(path)
            merged = deep_merge(merged, file_settings)
        except ConfigError:
            raise

    # Apply environment overrides
    merged = _apply_env_overrides(merged)

    # Validate and create Settings
    try:
        return Settings(**merged)
    except ValidationError as e:
        raise ConfigError(f"Invalid settings: {e}") from e
