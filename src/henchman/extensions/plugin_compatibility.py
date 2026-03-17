"""Plugin compatibility checking."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from packaging.specifiers import SpecifierSet
from packaging.version import Version

from henchman.version import VERSION

if TYPE_CHECKING:
    from henchman.extensions.models import PluginMetadata

PLATFORM_MAP = {
    "linux": "linux",
    "win32": "windows",
    "darwin": "macos",
}


def _check_compatibility(metadata: PluginMetadata) -> bool:
    """Return whether metadata is compatible with the current environment."""
    try:
        compatibility = metadata.compatibility
        if not _check_henchman_compatibility(compatibility.henchman):
            return False
        if not _check_python_compatibility(compatibility.python):
            return False
        return not compatibility.os or _check_os_compatibility(compatibility.os)
    except (ImportError, ValueError):
        return False


def _check_henchman_compatibility(henchman_spec: str) -> bool:
    """Check Henchman version compatibility."""
    return SpecifierSet(henchman_spec).contains(Version(VERSION))


def _check_python_compatibility(python_spec: str) -> bool:
    """Check Python version compatibility."""
    current_python = Version(
        f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
    )
    return SpecifierSet(python_spec).contains(current_python)


def _check_os_compatibility(supported_os_list: list[str]) -> bool:
    """Check OS compatibility."""
    current_os = PLATFORM_MAP.get(sys.platform, sys.platform)
    return current_os in supported_os_list


class PluginCompatibilityChecker:
    """Checks plugin compatibility with current system."""

    @staticmethod
    async def check_compatibility(metadata: PluginMetadata) -> bool:
        """Check if plugin is compatible with current system.
        
        Args:
            metadata: Plugin metadata containing compatibility requirements.
                The metadata should include Henchman version, Python version,
                and OS compatibility specifications.
        
        Returns:
            True if the plugin is compatible with the current system,
            False otherwise. Compatibility is checked against:
            - Henchman-AI version (from metadata.compatibility.henchman)
            - Python version (from metadata.compatibility.python)
            - Operating system (from metadata.compatibility.os, if specified)
        
        Raises:
            ImportError: If required dependencies cannot be imported.
            ValueError: If version specifications are malformed.
        """
        return _check_compatibility(metadata)

    @staticmethod
    def _check_henchman_compatibility(henchman_spec: str) -> bool:
        """Check Henchman version compatibility."""
        return _check_henchman_compatibility(henchman_spec)

    @staticmethod
    def _check_python_compatibility(python_spec: str) -> bool:
        """Check Python version compatibility."""
        return _check_python_compatibility(python_spec)

    @staticmethod
    def _check_os_compatibility(supported_os_list: list[str]) -> bool:
        """Check OS compatibility."""
        return _check_os_compatibility(supported_os_list)
