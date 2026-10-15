"""Tier 8 auto-update checks built on the safe update-plan contract."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from packaging.version import InvalidVersion, Version

from henchman.cli.system_info import SystemInfo, get_system_info
from henchman.cli.update_check import build_update_plan


class AutoUpdater:
    """Check whether an update is available without executing it."""

    def __init__(
        self,
        *,
        system_info_getter: Callable[[], SystemInfo] = get_system_info,
        latest_version_fetcher: Callable[[str], str] | None = None,
    ) -> None:
        """Initialize the updater helper.

        Args:
            system_info_getter: Shared system introspection hook.
            latest_version_fetcher: Optional version lookup hook.
        """
        self._system_info_getter = system_info_getter
        self._latest_version_fetcher = latest_version_fetcher

    def check(self) -> dict[str, Any]:
        """Return structured update status and upgrade guidance."""
        system_info = self._system_info_getter()
        latest_version = (
            self._latest_version_fetcher(system_info.package_name)
            if self._latest_version_fetcher is not None
            else system_info.version
        )
        plan = build_update_plan(system_info)
        return {
            "current_version": system_info.version,
            "latest_version": latest_version,
            "update_available": _is_newer_version(latest_version, system_info.version),
            "plan": plan,
        }


def _is_newer_version(candidate: str, current: str) -> bool:
    """Return whether a candidate version is newer than the current one."""
    try:
        return Version(candidate) > Version(current)
    except InvalidVersion:
        return candidate != current
