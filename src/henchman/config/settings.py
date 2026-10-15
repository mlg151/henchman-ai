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


class ConfigError(ValueError):
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
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def discover_settings_files(project_root: Path | None = None) -> list[Path]:
    """Discover settings files in order of precedence.

    Searches for settings.yaml or settings.json in:
    0. HENCHMAN_SETTINGS_PATH (if set)
    1. ~/.henchman/ (user settings)
    2. .henchman/ (workspace settings)

    Args:
        project_root: Optional project root to use for workspace settings discovery.
            When omitted, the current working directory is used.

    Returns:
        List of paths to settings files, ordered by precedence (user first).
    """
    files: list[Path] = []

    # Custom settings path
    if env_path := os.environ.get("HENCHMAN_SETTINGS_PATH"):
        path = Path(env_path)
        if path.exists():
            files.append(path)
            return files  # If explicit path is set, it overrides all others

    # User settings
    user_dir = Path.home() / ".henchman"
    if user_dir.exists():
        for name in ("settings.yaml", "settings.yml", "settings.json"):
            path = user_dir / name
            if path.exists():
                files.append(path)
                break

    # Workspace settings
    base_dir = (project_root or Path.cwd()).resolve()
    workspace_dir = base_dir / ".henchman"
    if workspace_dir.exists():
        for name in ("settings.yaml", "settings.yml", "settings.json"):
            path = workspace_dir / name
            if path.exists():
                files.append(path)
                break
    else:
        # Legacy project settings directory
        for legacy_dirname in (".hENCHMAN",):
            legacy_dir = base_dir / legacy_dirname
            if legacy_dir.exists():
                for name in ("settings.yaml", "settings.yml", "settings.json"):
                    path = legacy_dir / name
                    if path.exists():
                        files.append(path)
                        break
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
            yaml.safe_load(content) if path.suffix in (".yaml", ".yml") else json.loads(content)
        )
    except (yaml.YAMLError, json.JSONDecodeError) as e:
        msg = f"Failed to parse {path}: {e}"
        raise ConfigError(msg) from e
    else:
        return data or {}


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


def load_settings(project_root: Path | None = None) -> Settings:
    """Load settings with hierarchical merging.

    Precedence (later overrides earlier):
    1. Defaults (from Settings model)
    2. User settings (~/.henchman/settings.yaml)
    3. Workspace settings (.henchman/settings.yaml)
    4. Environment variables (HENCHMAN_PROVIDER, HENCHMAN_MODEL)

    Args:
        project_root: Optional project root for workspace settings discovery.
            When omitted, the current working directory is used.

    Returns:
        Merged Settings object.

    Raises:
        ConfigError: If settings files are invalid.
    """
    merged: dict[str, Any] = {}
    loaded_files: list[Path] = []

    # Load and merge files in order
    for path in discover_settings_files(project_root):
        try:
            file_settings = _load_file(path)
            merged = deep_merge(merged, file_settings)
            loaded_files.append(path)
        except ConfigError:
            raise

    # Apply environment overrides
    merged = _apply_env_overrides(merged)

    # Validate and create Settings
    try:
        return Settings(**merged)
    except ValidationError as e:
        source_hint = (
            f" in {loaded_files[-1]}" if loaded_files else ""
        )
        # Extract field path from the first validation error
        field_path = e.errors()[0]["loc"] if e.errors() else ()
        path_str = ".".join(str(p) for p in field_path) if field_path else "unknown"
        msg = f"Invalid settings{source_hint}: {path_str}"
        raise ConfigError(msg) from e


def save_settings(settings: Settings, path: Path | None = None) -> None:
    """Save settings to a file.

    Args:
        settings: Settings object to save.
        path: Path to save to. If None, uses ~/.henchman/settings.yaml.

    Returns:
        None
    """
    if path is None:
        path = Path.home() / ".henchman" / "settings.yaml"

    # Ensure directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    # Convert settings to dict, excluding defaults to keep file clean
    data = settings.model_dump(exclude_defaults=True, mode="json")

    # Write to file
    with open(path, "w") as f:
        if path.suffix in (".yaml", ".yml"):
            yaml.dump(data, f, default_flow_style=False)
        else:
            json.dump(data, f, indent=2)
