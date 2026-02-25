"""Extensions module for Henchman-AI.

This module provides the extension system for adding third-party
tools, commands, and context to the CLI.
"""

from henchman.extensions.base import Extension
from henchman.extensions.manager import ExtensionManager
from henchman.extensions.models import (
    PluginCompatibility,
    PluginEntryPoints,
    PluginInstallation,
    PluginMetadata,
    PluginPermission,
    PluginSearchResult,
    PluginSource,
    PluginStats,
    PluginUpdateInfo,
    SecurityReport,
)
from henchman.extensions.plugin_manager import PluginManager

__all__ = [
    "Extension",
    "ExtensionManager",
    "PluginCompatibility",
    "PluginEntryPoints",
    "PluginInstallation",
    "PluginManager",
    "PluginMetadata",
    "PluginPermission",
    "PluginSearchResult",
    "PluginSource",
    "PluginStats",
    "PluginUpdateInfo",
    "SecurityReport",
]
