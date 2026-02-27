"""Henchman-AI: A model-agnostic AI agent CLI in Python."""

from henchman.version import VERSION

__version__ = VERSION

__all__ = ["__version__"]

from henchman.utils.lazy_import import getattr_for_textual_app

__getattr__ = getattr_for_textual_app(__name__)
