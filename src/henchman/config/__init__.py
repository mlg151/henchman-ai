"""Configuration management.

This module provides configuration loading and context file discovery.
"""

from henchman.config.context import DEFAULT_FILENAMES, ContextLoader, ContextSnapshot
from henchman.config.environment import (
    EnvironmentContext,
    format_environment_block,
    gather_environment,
)
from henchman.config.schema import (
    ContextSettings,
    LayoutSettings,
    McpServerConfig,
    ProviderSettings,
    RagSettings,
    Settings,
    ToolSettings,
    UISettings,
)
from henchman.config.settings import ConfigError, deep_merge, load_settings

__all__ = [
    "DEFAULT_FILENAMES",
    "ConfigError",
    "ContextLoader",
    "ContextSnapshot",
    "LayoutSettings",
    "ContextSettings",
    "EnvironmentContext",
    "McpServerConfig",
    "ProviderSettings",
    "RagSettings",
    "Settings",
    "ToolSettings",
    "UISettings",
    "deep_merge",
    "format_environment_block",
    "gather_environment",
    "load_settings",
]
