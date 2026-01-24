"""Extension manager for discovering and loading extensions."""

from __future__ import annotations

import importlib.util
import logging
import sys
from importlib.metadata import entry_points
from pathlib import Path
from typing import TYPE_CHECKING

from henchman.extensions.base import Extension

if TYPE_CHECKING:
    from henchman.cli.commands import Command
    from henchman.tools.base import Tool

logger = logging.getLogger(__name__)

ENTRY_POINT_GROUP = "mlg.extensions"


class ExtensionManager:
    """Manages extension discovery, loading, and registration.

    The ExtensionManager handles:
    - Manual extension registration
    - Entry point-based discovery (pyproject.toml)
    - Directory-based discovery (~/.henchman/extensions/)

    Example:
        >>> manager = ExtensionManager()
        >>> manager.discover_entry_points()
        >>> manager.discover_directory(Path.home() / ".henchman" / "extensions")
        >>> for name in manager.list_extensions():
        ...     print(name)
    """

    def __init__(self) -> None:
        """Initialize an empty extension manager."""
        self._extensions: dict[str, Extension] = {}

    def register(self, extension: Extension) -> None:
        """Register an extension.

        Args:
            extension: Extension instance to register.
        """
        self._extensions[extension.name] = extension
        logger.debug("Registered extension: %s v%s", extension.name, extension.version)

    def unregister(self, name: str) -> bool:
        """Unregister an extension by name.

        Args:
            name: Extension name to unregister.

        Returns:
            True if extension was removed, False if not found.
        """
        if name in self._extensions:
            del self._extensions[name]
            logger.debug("Unregistered extension: %s", name)
            return True
        return False

    def get(self, name: str) -> Extension | None:
        """Get an extension by name.

        Args:
            name: Extension name.

        Returns:
            Extension instance or None if not found.
        """
        return self._extensions.get(name)

    def list_extensions(self) -> list[str]:
        """List all registered extension names.

        Returns:
            List of extension names.
        """
        return list(self._extensions.keys())

    def get_all_tools(self) -> list[Tool]:
        """Get all tools from all registered extensions.

        Returns:
            List of Tool instances from all extensions.
        """
        tools: list[Tool] = []
        for ext in self._extensions.values():
            tools.extend(ext.get_tools())
        return tools

    def get_all_commands(self) -> list[Command]:
        """Get all commands from all registered extensions.

        Returns:
            List of Command instances from all extensions.
        """
        commands: list[Command] = []
        for ext in self._extensions.values():
            commands.extend(ext.get_commands())
        return commands

    def get_combined_context(self) -> str:
        """Get combined context from all extensions.

        Returns:
            Combined context string from all extensions.
        """
        contexts = [ext.get_context() for ext in self._extensions.values()]
        return "\n\n".join(c for c in contexts if c)

    def discover_entry_points(self) -> None:
        """Discover and load extensions from entry points.

        Looks for entry points in the "mlg.extensions" group.
        Each entry point should point to an Extension subclass.
        """
        try:
            eps = entry_points(group=ENTRY_POINT_GROUP)
        except TypeError:
            # Python < 3.10 compatibility
            all_eps = entry_points()
            eps = all_eps.get(ENTRY_POINT_GROUP, [])  # type: ignore[arg-type]

        for ep in eps:
            try:
                ext_class = ep.load()
                if isinstance(ext_class, type) and issubclass(ext_class, Extension):
                    self.register(ext_class())
                    logger.info("Loaded extension from entry point: %s", ep.name)
                else:
                    logger.warning("Entry point %s is not an Extension subclass", ep.name)
            except Exception as e:
                logger.warning("Failed to load extension %s: %s", ep.name, e)

    def discover_directory(self, directory: Path) -> None:
        """Discover and load extensions from a directory.

        Looks for subdirectories containing an extension.py file
        with an Extension subclass.

        Args:
            directory: Directory to search for extensions.
        """
        if not directory.exists() or not directory.is_dir():
            return

        for ext_dir in directory.iterdir():
            if not ext_dir.is_dir():
                continue

            ext_file = ext_dir / "extension.py"
            if not ext_file.exists():
                continue

            try:
                self._load_extension_from_file(ext_file, ext_dir.name)
            except Exception as e:
                logger.warning("Failed to load extension from %s: %s", ext_dir.name, e)

    def _load_extension_from_file(self, ext_file: Path, ext_name: str) -> None:
        """Load an extension from a Python file.

        Args:
            ext_file: Path to extension.py file.
            ext_name: Name of the extension directory.
        """
        spec = importlib.util.spec_from_file_location(f"mlg_ext_{ext_name}", ext_file)
        if spec is None or spec.loader is None:
            logger.warning("Could not load spec for %s", ext_file)
            return

        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module

        try:
            spec.loader.exec_module(module)
        except Exception as e:
            logger.warning("Error executing extension module %s: %s", ext_name, e)
            del sys.modules[spec.name]
            return

        # Find Extension subclass in module
        ext_class = None
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if isinstance(attr, type) and issubclass(attr, Extension) and attr is not Extension:
                ext_class = attr
                break

        if ext_class is None:
            logger.warning("No Extension subclass found in %s", ext_file)
            return

        try:
            self.register(ext_class())
            logger.info("Loaded extension from directory: %s", ext_name)
        except Exception as e:
            logger.warning("Failed to instantiate extension %s: %s", ext_name, e)
