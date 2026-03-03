"""Lazy import utilities for Textual dev mode and other dynamic imports."""

from typing import Any


def getattr_for_textual_app(module_name: str) -> Any:
    """Standard __getattr__ implementation for Textual app lazy loading.

    This function should be assigned to __getattr__ in modules that need
    lazy loading of the HenchmanTextualApp class for Textual dev mode.

    Args:
        module_name: The name of the module where this is used (for error messages)

    Returns:
        A __getattr__ function that lazily imports HenchmanTextualApp when 'app'
        attribute is accessed.

    Example:
        __getattr__ = getattr_for_textual_app(__name__)
    """

    def __getattr__(name: str) -> Any:
        """Lazy import for Textual dev mode (``textual run henchman``)."""
        if name == "app":
            from henchman.cli.textual_app import HenchmanTextualApp

            return HenchmanTextualApp
        msg = f"module {module_name!r} has no attribute {name!r}"
        raise AttributeError(msg)

    return __getattr__
