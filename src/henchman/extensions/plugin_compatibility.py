"""Plugin compatibility checking."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from henchman.extensions.models import PluginMetadata


class PluginCompatibilityChecker:
    """Checks plugin compatibility with current system."""

    @staticmethod
    async def check_compatibility(metadata: PluginMetadata) -> bool:
        """Check if plugin is compatible with current system.

        Args:
            metadata: Plugin metadata.

        Returns:
            True if compatible, False otherwise.
        """
        try:
            # Check Henchman version
            if not PluginCompatibilityChecker._check_henchman_compatibility(
                metadata.compatibility.henchman,
            ):
                return False

            # Check Python version
            if not PluginCompatibilityChecker._check_python_compatibility(
                metadata.compatibility.python,
            ):
                return False

            # Check OS compatibility
            if metadata.compatibility.os:
                if not PluginCompatibilityChecker._check_os_compatibility(
                    metadata.compatibility.os,
                ):
                    return False

            return True

        except (ValueError, ImportError):
            # If we can't parse version specifiers, assume incompatible
            return False

    @staticmethod
    def _check_henchman_compatibility(henchman_spec: str) -> bool:
        """Check Henchman version compatibility.

        Args:
            henchman_spec: Version specifier for Henchman.

        Returns:
            True if compatible, False otherwise.
        """
        from packaging.specifiers import SpecifierSet
        from packaging.version import Version

        from henchman.version import VERSION

        current_henchman = Version(VERSION)
        return SpecifierSet(henchman_spec).contains(current_henchman)

    @staticmethod
    def _check_python_compatibility(python_spec: str) -> bool:
        """Check Python version compatibility.

        Args:
            python_spec: Version specifier for Python.

        Returns:
            True if compatible, False otherwise.
        """
        from packaging.specifiers import SpecifierSet
        from packaging.version import Version

        current_python = Version(
            f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        )
        return SpecifierSet(python_spec).contains(current_python)

    @staticmethod
    def _check_os_compatibility(supported_os_list: list[str]) -> bool:
        """Check OS compatibility.

        Args:
            supported_os_list: List of supported operating systems.

        Returns:
            True if compatible, False otherwise.
        """
        platform_map = {
            "linux": "linux",
            "win32": "windows",
            "darwin": "macos",
        }
        current_os = platform_map.get(sys.platform, sys.platform)
        return current_os in supported_os_list
