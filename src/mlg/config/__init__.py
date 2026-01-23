"""Configuration management.

This module provides configuration loading and context file discovery.
"""

from mlg.config.context import ContextLoader
from mlg.config.schema import (
    McpServerConfig,
    ProviderSettings,
    Settings,
    ToolSettings,
    UISettings,
)
from mlg.config.settings import ConfigError, deep_merge, load_settings

__all__ = [
    "ConfigError",
    "ContextLoader",
    "McpServerConfig",
    "ProviderSettings",
    "Settings",
    "ToolSettings",
    "UISettings",
    "deep_merge",
    "load_settings",
]
