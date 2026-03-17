"""UI Plugin System for extending the CLI.

This module provides the base class for UI plugins and the manager for loading them.
Plugins can register new slash commands and render custom UI elements.
"""

from __future__ import annotations

import importlib.util
import sys
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

    from henchman.cli.repl import Repl


try:
    from typing import Self
except ImportError:  # pragma: no cover
    from typing_extensions import Self


class UIPlugin(ABC):
    """Base class for UI plugins.

    Plugins must implement the `name` property and `register` method.
    """

    @property
    @abstractmethod
    def name(self: Self) -> str:
        """Name of the plugin."""

    @property
    def description(self: Self) -> str:
        """Description of the plugin."""
        return ""

    @abstractmethod
    def register(self: Self, repl: Repl) -> None:
        """Register the plugin with the REPL.

        Args:
            repl: The REPL instance.

        Returns:
            None
        """

    def render(self: Self, data: Any) -> None:
        """Render data using this plugin (optional).

        Args:
            data: Data to render.

        Returns:
            None
        """


class PluginManager:
    """Manages loading and registration of UI plugins."""

    def __init__(self: Self, repl: Repl | None) -> None:
        """Initialize the plugin manager.

        Args:
            repl: The REPL instance, or None if not yet available.

        Returns:
            None
        """
        self.repl = repl
        self.plugins: dict[str, UIPlugin] = {}

    def load_plugins_from_directory(self: Self, directory: Path) -> None:
        """Load plugins from a directory.

        Args:
            directory: Directory containing plugin python files.

        Returns:
            None
        """
        if not directory.exists() or not directory.is_dir():
            return

        for path in directory.glob("*.py"):
            if path.name.startswith("__"):
                continue

            try:
                self._load_plugin_from_file(path)
            except Exception as e:
                # Log error but continue loading other plugins
                if self.repl and self.repl.settings and self.repl.settings.ui.mcp_logging:
                    self.repl.renderer.warning(f"Failed to load plugin {path.name}: {e}")

    def _try_register_plugin_class(self: Self, attr_name: str, attr: object) -> bool:
        """Attempt to instantiate and register a single plugin class.

        Args:
            attr_name: Attribute name being examined.
            attr: The attribute value (expected to be a type).

        Returns:
            True if the plugin was registered, False otherwise.
        """
        if not (isinstance(attr, type) and issubclass(attr, UIPlugin) and attr is not UIPlugin):
            return False
        try:
            self.register_plugin(attr())
        except Exception as e:
            if self.repl and self.repl.settings and self.repl.settings.ui.mcp_logging:
                self.repl.renderer.warning(f"Failed to instantiate plugin {attr_name}: {e}")
            return False
        else:
            return True

    def _load_plugin_from_file(self: Self, path: Path) -> None:
        """Load a plugin from a python file.

        Args:
            path: Path to python file.

        Returns:
            None
        """
        module_name = f"henchman_plugin_{path.stem}"
        spec = importlib.util.spec_from_file_location(module_name, path)
        if not spec or not spec.loader:
            return

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        # Find UIPlugin subclasses
        found_plugin = any(
            self._try_register_plugin_class(attr_name, getattr(module, attr_name))
            for attr_name in dir(module)
        )

        if found_plugin and self.repl and self.repl.settings and self.repl.settings.ui.mcp_logging:
            self.repl.renderer.info(f"Loaded plugins from {path.name}")

    def register_plugin(self: Self, plugin: UIPlugin) -> None:
        """Register a plugin instance.

        Args:
            plugin: Plugin instance.

        Returns:
            None
        """
        if plugin.name in self.plugins:
            return

        if self.repl:
            plugin.register(self.repl)
        self.plugins[plugin.name] = plugin
