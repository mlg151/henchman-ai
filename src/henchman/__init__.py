"""Henchman-AI: A model-agnostic AI agent CLI in Python."""

from henchman.version import VERSION

__version__ = VERSION

__all__ = ["__version__"]


def __getattr__(name: str) -> object:
    """Lazy import for Textual dev mode (``textual run henchman``)."""
    if name == "app":
        from henchman.cli.textual_app import HenchmanTextualApp

        return HenchmanTextualApp
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
