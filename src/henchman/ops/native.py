"""Capability probing for optional native bindings."""

from __future__ import annotations

import importlib
from collections.abc import Callable, Mapping
from typing import Any


class NativeBindings:
    """Probe optional native bindings and expose safe fallbacks."""

    def __init__(
        self,
        *,
        module_loader: Callable[[str], Any] | None = None,
        modules: Mapping[str, str] | None = None,
    ) -> None:
        """Initialize the native capability probe.

        Args:
            module_loader: Optional import hook for tests.
            modules: Optional mapping of capability name to module path.
        """
        self._module_loader = module_loader or importlib.import_module
        self._modules = dict(
            modules
            or {
                "color_diff": "henchman_native.color_diff",
                "file_index": "henchman_native.file_index",
            }
        )

    def capabilities(self) -> dict[str, dict[str, Any]]:
        """Return availability metadata for native capabilities."""
        capabilities: dict[str, dict[str, Any]] = {}
        for capability_name, module_name in self._modules.items():
            try:
                self._module_loader(module_name)
                capabilities[capability_name] = {
                    "available": True,
                    "backend": "native",
                    "module": module_name,
                }
            except Exception as exc:  # noqa: BLE001
                capabilities[capability_name] = {
                    "available": False,
                    "backend": "python",
                    "module": module_name,
                    "error": str(exc),
                }
        return capabilities
