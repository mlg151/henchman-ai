"""Tests for BUG-020: Extension Loading Failures Lose Traceback.

Verifies that logger.warning calls in extension manager include exc_info=True
so full tracebacks are captured.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from henchman.extensions.base import Extension
from henchman.extensions.manager import (
    ExtensionManager,
    _load_entry_point_extension,
    _load_extension_from_file_impl,
    _try_instantiate_ext_class,
    _try_load_extension_dir,
)


class _ValidExtension(Extension):
    """Minimal extension for testing."""

    @property
    def name(self) -> str:
        return "test_ext"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "Test extension"


def test_load_entry_point_uses_exc_info() -> None:
    """_load_entry_point_extension should log with exc_info=True on failure."""
    ep = MagicMock()
    ep.load.side_effect = ImportError("missing dependency")
    ep.name = "test_ep"
    manager = MagicMock(spec=ExtensionManager)

    with patch("henchman.extensions.manager.logger") as mock_logger:
        _load_entry_point_extension(ep, manager)

    mock_logger.warning.assert_called_once()
    _, kwargs = mock_logger.warning.call_args
    assert kwargs.get("exc_info") is True, "exc_info=True must be passed to logger.warning"


def test_try_load_extension_dir_uses_exc_info() -> None:
    """_try_load_extension_dir should log with exc_info=True on failure."""
    ext_dir = Path("/fake/ext/dir")
    load_fn = MagicMock(side_effect=OSError("permission denied"))

    with (
        patch("henchman.extensions.manager.Path.is_dir", return_value=True),
        patch("henchman.extensions.manager.Path.exists") as mock_exists,
        patch("henchman.extensions.manager.logger") as mock_logger,
    ):
        mock_exists.return_value = True
        _try_load_extension_dir(ext_dir, load_fn)

    mock_logger.warning.assert_called_once()
    _, kwargs = mock_logger.warning.call_args
    assert kwargs.get("exc_info") is True, "exc_info=True must be passed to logger.warning"


def test_try_instantiate_ext_class_uses_exc_info() -> None:
    """_try_instantiate_ext_class should log with exc_info=True on failure."""

    class _BrokenExt(_ValidExtension):
        def __init__(self) -> None:
            raise TypeError("missing required argument")

    with patch("henchman.extensions.manager.logger") as mock_logger:
        result = _try_instantiate_ext_class(_BrokenExt, "broken")

    assert result is None
    mock_logger.warning.assert_called_once()
    _, kwargs = mock_logger.warning.call_args
    assert kwargs.get("exc_info") is True, "exc_info=True must be passed to logger.warning"


def test_load_extension_from_file_uses_exc_info() -> None:
    """_load_extension_from_file_impl should log with exc_info=True on failure."""
    # Patch spec_from_file_location to return a valid spec
    spec = MagicMock()
    spec.loader = MagicMock()
    spec.loader.exec_module = MagicMock(side_effect=SyntaxError("invalid syntax"))
    spec.name = "henchman_ext_test_broken"

    with (
        patch("henchman.extensions.manager.importlib.util.spec_from_file_location", return_value=spec),
        patch("henchman.extensions.manager.logger") as mock_logger,
    ):
        result = _load_extension_from_file_impl(Path("/fake/ext.py"), "test_broken")

    assert result is None
    mock_logger.warning.assert_called_once()
    _, kwargs = mock_logger.warning.call_args
    assert kwargs.get("exc_info") is True, "exc_info=True must be passed to logger.warning"
