"""Extension manager for discovering and loading extensions."""

from __future__ import annotations

import importlib.util
import logging
import sys
from importlib.metadata import EntryPoint, entry_points
from typing import TYPE_CHECKING, TypeVar

from henchman.extensions.base import Extension

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from henchman.cli.commands import Command
    from henchman.tools.base import Tool

logger = logging.getLogger(__name__)

ENTRY_POINT_GROUP = "henchman.extensions"

_T = TypeVar("_T")


def _collect_from_extensions(
    extensions: dict[str, Extension],
    getter: Callable[[Extension], list[_T]],
) -> list[_T]:
    """Collect items from all extensions using a getter callable.

    Eliminates the duplicate accumulation pattern shared by get_all_tools
    and get_all_commands.
    """
    result: list[_T] = []
    for ext in extensions.values():
        result.extend(getter(ext))
    return result


def _register_extension(
    registry: dict[str, Extension],
    extension: Extension,
) -> None:
    """Register an extension in the given registry dict."""
    registry[extension.name] = extension
    logger.debug("Registered extension: %s v%s", extension.name, extension.version)


def _load_entry_point_extension(ep: EntryPoint, manager: ExtensionManager) -> None:
    """Load and register an extension from a single entry point."""
    try:
        ext_class = ep.load()
        if isinstance(ext_class, type) and issubclass(ext_class, Extension):
            manager.register(ext_class())
            logger.info("Loaded extension from entry point: %s", ep.name)
        else:
            logger.warning("Entry point %s is not an Extension subclass", ep.name)
    except Exception as e:  # noqa: BLE001
        logger.warning("Failed to load extension %s: %s", ep.name, e)


def _try_load_extension_dir(ext_dir: Path, manager: ExtensionManager) -> None:
    """Try to load an extension from a candidate directory, handling errors gracefully."""
    if not ext_dir.is_dir():
        return
    ext_file = ext_dir / "extension.py"
    if not ext_file.exists():
        return
    try:
        manager._load_extension_from_file(ext_file, ext_dir.name)  # noqa: SLF001
    except Exception as e:  # noqa: BLE001
        logger.warning("Failed to load extension from %s: %s", ext_dir.name, e)


def _try_instantiate_ext_class(
    ext_class: type[Extension],
    ext_name: str,
) -> Extension | None:
    """Attempt to instantiate *ext_class*, returning ``None`` on failure."""
    try:
        return ext_class()
    except Exception as e:  # noqa: BLE001
        logger.warning("Failed to instantiate extension %s: %s", ext_name, e)
        return None


def _load_extension_from_file_impl(ext_file: Path, ext_name: str) -> Extension | None:
    """Load and instantiate an Extension subclass from a Python file.

    Returns:
        Instantiated Extension, or None if loading or instantiation fails.
    """
    spec = importlib.util.spec_from_file_location(f"henchman_ext_{ext_name}", ext_file)
    if spec is None or spec.loader is None:
        logger.warning("Could not load spec for %s", ext_file)
        return None

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module

    try:
        spec.loader.exec_module(module)
    except Exception as e:  # noqa: BLE001
        logger.warning("Error executing extension module %s: %s", ext_name, e)
        del sys.modules[spec.name]
        return None

    # Find Extension subclass in module
    for attr_name in dir(module):
        attr = getattr(module, attr_name)
        if isinstance(attr, type) and issubclass(attr, Extension) and attr is not Extension:
            return _try_instantiate_ext_class(attr, ext_name)

    logger.warning("No Extension subclass found in %s", ext_file)
    return None


def _discover_extensions_in_directory(
    directory: Path,
    manager: ExtensionManager,
) -> None:
    """Scan *directory* for extension sub-directories and register each one.

    Skips *directory* gracefully when it does not exist or is not a directory.
    """
    if not directory.exists() or not directory.is_dir():
        return
    for ext_dir in directory.iterdir():
        _try_load_extension_dir(ext_dir, manager)


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

    def __init__(self: ExtensionManager) -> None:
        """Initialize an empty extension manager."""
        self._extensions: dict[str, Extension] = {}

    def register(self: ExtensionManager, extension: Extension) -> None:
        """Register an extension.

        Args:
            extension: Extension instance to register.
        """
        _register_extension(self._extensions, extension)

    def unregister(self: ExtensionManager, name: str) -> bool:
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

    def get(self: ExtensionManager, name: str) -> Extension | None:
        """Get an extension by name.

        Args:
            name: Extension name.

        Returns:
            Extension instance or None if not found.
        """
        return self._extensions.get(name)

    def list_extensions(self: ExtensionManager) -> list[str]:
        """List all registered extension names.

        Returns:
            List of extension names.
        """
        return list(self._extensions.keys())

    def get_all_tools(self: ExtensionManager) -> list[Tool]:
        """Get all tools from all registered extensions.

        Returns:
            List of Tool instances from all extensions.
        """
        return [t for ext in self._extensions.values() for t in ext.get_tools()]

    def get_all_commands(self: ExtensionManager) -> list[Command]:
        """Get all commands from all registered extensions.

        Returns:
            List of Command instances from all extensions.
        """
        return _collect_from_extensions(self._extensions, lambda ext: ext.get_commands())

    def get_combined_context(self: ExtensionManager) -> str:
        """Get combined context from all extensions.

        Returns:
            Combined context string from all extensions.
        """
        contexts = [ext.get_context() for ext in self._extensions.values()]
        return "\n\n".join(c for c in contexts if c)

    def discover_entry_points(self: ExtensionManager) -> None:
        """Discover and load extensions from entry points.

        Looks for entry points in the "henchman.extensions" group.
        Each entry point should point to an Extension subclass.
        """
        try:
            eps = entry_points(group=ENTRY_POINT_GROUP)
        except TypeError:
            # Python < 3.10 compatibility
            all_eps = entry_points()
            eps = all_eps.get(ENTRY_POINT_GROUP, [])  # type: ignore[arg-type]

        for ep in eps:
            _load_entry_point_extension(ep, self)

    def discover_directory(self: ExtensionManager, directory: Path) -> None:
        """Discover and load extensions from a directory.

        Looks for subdirectories containing an extension.py file
        with an Extension subclass.

        Args:
            directory: Directory to search for extensions.
        """
        _discover_extensions_in_directory(directory, self)

    def _load_extension_from_file(self: ExtensionManager, ext_file: Path, ext_name: str) -> None:
        """Load an extension from a Python file.

        Args:
            ext_file: Path to extension.py file.
            ext_name: Name of the extension directory.
        """
        ext = _load_extension_from_file_impl(ext_file, ext_name)
        if ext is not None:
            self.register(ext)
            logger.info("Loaded extension from directory: %s", ext_name)
