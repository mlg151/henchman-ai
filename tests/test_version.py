"""Tests for mlg package initialization and version."""

from henchman import __version__
from henchman.version import VERSION, VERSION_TUPLE


def test_version_string_format() -> None:
    """Test that version string is in semver format."""
    parts = VERSION.split(".")
    assert len(parts) == 3
    assert all(part.isdigit() for part in parts)


def test_version_tuple() -> None:
    """Test that version tuple matches version string."""
    assert VERSION_TUPLE == (0, 1, 7)
    assert ".".join(str(v) for v in VERSION_TUPLE) == VERSION


def test_package_version_exported() -> None:
    """Test that __version__ is exported from package."""
    assert __version__ == VERSION
