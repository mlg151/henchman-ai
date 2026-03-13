"""Tests for henchman.__init__ module."""

import pytest


def test_version() -> None:
    """Test that version is accessible."""
    from henchman import __version__

    assert __version__ is not None
    assert isinstance(__version__, str)


def test_getattr_app() -> None:
    """Test __getattr__ for 'app' attribute (Textual dev mode)."""
    import henchman

    app_class = henchman.app
    from henchman.cli.textual_app import HenchmanTextualApp

    assert app_class is HenchmanTextualApp


def test_getattr_other() -> None:
    """Test __getattr__ raises AttributeError for other attributes."""
    import henchman

    with pytest.raises(AttributeError, match="module 'henchman' has no attribute 'nonexistent'"):
        _ = henchman.nonexistent


def test_all() -> None:
    """Test __all__ export."""
    from henchman import __all__

    assert "__version__" in __all__
    assert len(__all__) == 1
